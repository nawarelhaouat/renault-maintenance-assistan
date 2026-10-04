import re
import unicodedata
from functools import lru_cache

from app.config import COLLECTION, EMBED_MODEL, N_CANDIDATES, QDRANT_URL, RERANKER_MODEL, RRF_K, TOP_K, USE_RERANKER
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from rank_bm25 import BM25Okapi

_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


@lru_cache(maxsize=1)
def _client():
    return QdrantClient(url=QDRANT_URL)


@lru_cache(maxsize=1)
def _embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(EMBED_MODEL, device="cpu")


def tokenize(text: str) -> list[str]:
    """Minuscules, sans accents ; garde les codes entiers (rf-cab-330) ET leurs morceaux."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    toks = _TOKEN.findall(text)
    return toks + [p for t in toks if "-" in t for p in t.split("-")]


def _key(d: dict) -> int:
    return hash((d["source"], d["page"], d["text"]))


@lru_cache(maxsize=1)
def _corpus():
    chunks, offset = [], None
    while True:
        points, offset = _client().scroll(COLLECTION, limit=500, offset=offset,
                                          with_payload=True, with_vectors=False)
        chunks += [{"text": p.payload["text"], "source": p.payload["source"],
                    "page": p.payload["page"]} for p in points]
        if offset is None:
            break
    return chunks, BM25Okapi([tokenize(c["text"]) for c in chunks])


def _dense(query: str, source: str | None, n: int) -> list[dict]:
    vec = _embedder().encode(query, normalize_embeddings=True).tolist()
    flt = Filter(must=[FieldCondition(key="source", match=MatchValue(value=source))]) if source else None
    hits = _client().query_points(COLLECTION, query=vec, limit=n, query_filter=flt).points
    return [{"text": h.payload["text"], "source": h.payload["source"],
             "page": h.payload["page"], "score": h.score} for h in hits]


def _sparse(query: str, source: str | None, n: int) -> list[dict]:
    chunks, bm25 = _corpus()
    scores = bm25.get_scores(tokenize(query))
    out = []
    for i in sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True):
        if scores[i] <= 0:
            break
        if source and chunks[i]["source"] != source:
            continue
        out.append(dict(chunks[i], score=float(scores[i])))
        if len(out) >= n:
            break
    return out


def _rrf(*rankings: list[dict]) -> list[dict]:
    fused, docs = {}, {}
    for ranking in rankings:
        for rank, d in enumerate(ranking):
            k = _key(d)
            fused[k] = fused.get(k, 0.0) + 1.0 / (RRF_K + rank + 1)
            docs[k] = d
    return [dict(docs[k], score=s) for k, s in sorted(fused.items(), key=lambda x: x[1], reverse=True)]


@lru_cache(maxsize=1)
def _reranker():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(RERANKER_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(RERANKER_MODEL).eval()
    return tok, model


def _rerank(query: str, docs: list[dict], k: int) -> list[dict]:
    import torch
    if not docs:
        return docs
    tok, model = _reranker()
    scores = []
    with torch.no_grad():
        for i in range(0, len(docs), 8):
            batch = docs[i:i + 8]
            enc = tok([query] * len(batch), [d["text"] for d in batch], padding=True,
                      truncation=True, max_length=512, return_tensors="pt")
            scores += model(**enc).logits.view(-1).float().tolist()
    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    return [dict(d, score=float(s)) for d, s in ranked[:k]]


def search(query: str, source: str | None = None, k: int = TOP_K, mode: str | None = None) -> list[dict]:
    """mode : 'dense' | 'hybrid' | 'rerank' (défaut selon USE_RERANKER)."""
    mode = mode or ("rerank" if USE_RERANKER else "hybrid")
    if mode == "dense":
        return _dense(query, source, k)
    fused = _rrf(_dense(query, source, N_CANDIDATES), _sparse(query, source, N_CANDIDATES))
    if mode == "hybrid":
        return fused[:k]
    return _rerank(query, fused[:N_CANDIDATES], k)