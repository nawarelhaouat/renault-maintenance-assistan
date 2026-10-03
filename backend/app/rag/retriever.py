import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from sentence_transformers import SentenceTransformer

from app.config import COLLECTION, EMBED_MODEL, LLM_MODEL, QDRANT_URL, TOP_K

_client = QdrantClient(url=QDRANT_URL)
_embedder = SentenceTransformer(EMBED_MODEL)

SYSTEM_PROMPT = """Tu es un assistant de maintenance industrielle pour une usine automobile.
Règles :
- Réponds UNIQUEMENT à partir des extraits fournis. Si l'information n'y est pas, dis-le clairement.
- Réponds dans la langue de la question, de façon courte et sous forme d'étapes numérotées.
- Cite tes sources à la fin de chaque étape sous la forme [fichier, p.X].
- Rappelle les consignes de sécurité (consignation, EPI) quand elles apparaissent dans les extraits."""


def search(query: str, source: str | None = None, k: int = TOP_K):
    vec = _embedder.encode(query, normalize_embeddings=True).tolist()
    flt = None
    if source:
        flt = Filter(must=[FieldCondition(key="source", match=MatchValue(value=source))])
    hits = _client.query_points(COLLECTION, query=vec, limit=k, query_filter=flt).points
    return [{"text": h.payload["text"], "source": h.payload["source"],
             "page": h.payload["page"], "score": h.score} for h in hits]


def answer(query: str, source: str | None = None):
    docs = search(query, source)
    context = "\n\n".join(f"[{d['source']}, p.{d['page']}]\n{d['text']}" for d in docs)
    resp = ollama.chat(model=LLM_MODEL, messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Extraits :\n{context}\n\nQuestion : {query}"},
    ])
    return resp["message"]["content"], docs