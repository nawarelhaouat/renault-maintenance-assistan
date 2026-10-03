import uuid

import fitz  # PyMuPDF
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from app.config import (CHUNK_OVERLAP, CHUNK_SIZE, COLLECTION, EMBED_DIM,
                        EMBED_MODEL, MANUALS_DIR, QDRANT_URL)


def chunk_text(text: str):
    text = " ".join(text.split())
    step = CHUNK_SIZE - CHUNK_OVERLAP
    return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), step) if text[i:i + CHUNK_SIZE].strip()]


def main():
    client = QdrantClient(url=QDRANT_URL)
    if client.collection_exists(COLLECTION):
        client.delete_collection(COLLECTION)
    client.create_collection(COLLECTION, vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE))

    embedder = SentenceTransformer(EMBED_MODEL)
    pdfs = sorted(MANUALS_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"Aucun PDF dans {MANUALS_DIR}")

    total = 0
    for pdf in pdfs:
        chunks = []
        with fitz.open(pdf) as doc:
            for page_no, page in enumerate(doc, start=1):
                for c in chunk_text(page.get_text()):
                    chunks.append({"text": c, "source": pdf.name, "page": page_no})
        if not chunks:
            print(f"[!] {pdf.name}: aucun texte (PDF scanné ? OCR nécessaire)")
            continue
        vectors = embedder.encode([c["text"] for c in chunks], batch_size=32,
                                  normalize_embeddings=True, show_progress_bar=True)
        points = [PointStruct(id=str(uuid.uuid4()), vector=v.tolist(), payload=c)
                  for v, c in zip(vectors, chunks)]
        client.upsert(COLLECTION, points=points)
        total += len(points)
        print(f"{pdf.name}: {len(points)} chunks")
    print(f"OK: {total} chunks indexés")


if __name__ == "__main__":
    main()