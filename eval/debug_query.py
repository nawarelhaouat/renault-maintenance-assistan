import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import MIN_RERANK_SCORE, USE_RERANKER  # noqa: E402
from app.nlp.language import normalize_query  # noqa: E402
from app.rag.retriever import search  # noqa: E402
from app.tools.combined import PROMPT_SYMPTOM, generate  # noqa: E402
from app.tools.rag_search import SYMPTOM  # noqa: E402

q = normalize_query(sys.argv[1])["french"]
qs = f"{q} code d'erreur dépannage" if SYMPTOM.search(q) else q
print(f"FR : {q} | reranker={USE_RERANKER} | seuil={MIN_RERANK_SCORE}")
docs = search(qs, source=sys.argv[2], k=4)
for d in docs:
    print(f"\n[{d['source']} p.{d['page']}] score={d['score']:.2f}\n{d['text'][:200]}")
raw, _ = generate(q, docs, PROMPT_SYMPTOM)
print("\n--- Réponse brute du LLM ---\n" + raw)