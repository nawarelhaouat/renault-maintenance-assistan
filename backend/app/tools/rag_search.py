import re

from app.config import MIN_RERANK_SCORE, USE_RERANKER
from app.rag.retriever import search
from app.tools.combined import NOT_FOUND, PROMPT_SYMPTOM, answer_from, manual_of, raw_extracts
from app.tools.machine_db import resolve_tag
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

SYMPTOM = re.compile(
    r"probl[eè]me|panne|d[eé]faut|erreur|ne (?:marche|fonctionne)|fuite|surchauffe|bruit|"
    r"arr[eê]t|alarme|coup[eé]|perte|r[eé]seau|anormal", re.IGNORECASE)


@tool(return_direct=True)
def search_manuals(question: str, asset_tag: str = "", config: RunnableConfig = None) -> str:
    """Répond à une question de procédure ou de symptôme à partir du manuel de la machine sélectionnée.
    La réponse est finale, ancrée dans le manuel, avec sources."""
    cfg = (config or {}).get("configurable") or {}
    q = cfg.get("question") or question
    tag = resolve_tag(asset_tag, config)
    source = manual_of(tag) if tag else None
    not_found = f"{NOT_FOUND} (manuel consulté : {source or 'tous'})"

    q_search = f"{q} code d'erreur dépannage" if SYMPTOM.search(q) else q
    docs = search(q_search, source=source, k=4)
    if not docs or (USE_RERANKER and docs[0]["score"] < MIN_RERANK_SCORE):
        return not_found                          # recherche non confiante : pas dans ce manuel

    safety = not re.search(r"consign|loto|s[ée]curit", q, re.IGNORECASE)
    out, status = answer_from(q, docs, PROMPT_SYMPTOM, safety)
    # recherche confiante mais LLM hésitant : on montre le manuel au lieu d'affirmer qu'il n'y a rien
    return out if status == "ok" else raw_extracts(docs)