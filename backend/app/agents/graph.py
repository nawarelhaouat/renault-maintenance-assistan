import json
import re

from app.config import LLM_MODEL
from app.db import query
from app.ml.predict import risk_report
from app.nlp.language import normalize_query
from app.tools.combined import diagnose_failure
from app.tools.machine_db import get_failure_stats, get_machine_info, get_maintenance_history
from app.tools.rag_search import search_manuals
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

TOOLS = [get_machine_info, get_maintenance_history, get_failure_stats, search_manuals]

SYSTEM = """Tu es un assistant de maintenance pour une usine automobile.
Règles strictes :
- La FICHE GMAO du message fait foi. Ne compte JAMAIS toi-même les lignes d'un historique.
- Tu n'as pas besoin de fournir asset_tag : la machine sélectionnée est utilisée automatiquement.
- Historique : get_maintenance_history. Pannes fréquentes : get_failure_stats.
- Toute question de procédure, symptôme, graissage, sécurité, pièce : search_manuals (réponse finale).
- Réponds en français, de façon courte. Si un outil ne renvoie rien, dis-le au lieu de deviner."""

llm = ChatOllama(model=LLM_MODEL, temperature=0, num_ctx=4096, keep_alive="30m")
agent = create_react_agent(llm, TOOLS, prompt=SYSTEM)   # utilisé seulement pour les questions multi-intentions

CODE_RE = re.compile(r"\bE\d{3}\b", re.IGNORECASE)
LAST_RE = re.compile(r"derni(?:er|ère|ere)s?\s+(?:panne|d[eé]faillance|incident)|last\s+failure", re.IGNORECASE)
HISTORY_RE = re.compile(r"historique|derni[eè]res?\s+interventions?|interventions?\s+r[eé]centes?", re.IGNORECASE)
STATS_RE = re.compile(r"pannes?\s+(?:les\s+)?plus\s+fr[eé]quentes?|statistiques?\s+(?:de|des)\s+pannes?|top\s+pannes", re.IGNORECASE)
COUNT_RE = re.compile(r"combien|nombre|total|how\s+many", re.IGNORECASE)
RISK_RE = re.compile(r"risque\s+de\s+panne|probabilit[eé]\s+de\s+panne|prochaine\s+panne|tomber\s+en\s+panne|"
                     r"pr[eé]diction|pr[eé]dire|failure\s+risk", re.IGNORECASE)
TOPIC_RE = re.compile(r"intervention|maintenance|fois|panne|corrective|pr[eé]ventive|arr[eê]t|mttr", re.IGNORECASE)
NEED_MACHINE = "Sélectionne ou identifie d'abord une machine."


def _intents(text: str) -> list[str]:
    out = []
    if CODE_RE.search(text) or LAST_RE.search(text):
        out.append("diagnose")
    if HISTORY_RE.search(text):
        out.append("history")
    if STATS_RE.search(text):
        out.append("stats")
    if RISK_RE.search(text):
        out.append("risk")
    if COUNT_RE.search(text) and TOPIC_RE.search(text) and not STATS_RE.search(text):
        out.append("count")
    return out


def _fmt_count(tag: str) -> str:
    r = query("SELECT * FROM machine_summary WHERE asset_tag = %s", (tag,))[0]
    return (f"**{r['asset_tag']}** : {r['total_interventions']} interventions au total "
            f"({r['corrective_count']} correctives, {r['preventive_count']} préventives), "
            f"arrêt cumulé {float(r['total_downtime_min']) / 60:.1f} h, MTTR {r['mttr_min']} min, "
            f"dernière intervention le {str(r['last_intervention'])[:10]}.")


def _fmt_history(raw: str) -> str:
    d = json.loads(raw)
    lines = [f"**{d['asset_tag']}** : {d['total_interventions']} interventions au total, {d['shown']} affichées.\n",
             "| Date | Type | Panne | Technicien | Arrêt (min) | Coût (MAD) |", "|---|---|---|---|---|---|"]
    for r in d["interventions"]:
        cost = f"{float(r['cost_mad']):,.0f}".replace(",", " ")
        lines.append(f"| {r['opened_at'][:10]} | {r['wo_type']} | {r['failure'] or '-'} | "
                     f"{r['technician'] or '-'} | {r['downtime_minutes']} | {cost} |")
    return "\n".join(lines)


def _fmt_stats(raw: str) -> str:
    try:
        rows = json.loads(raw)
    except ValueError:
        return raw
    lines = ["| Code | Panne | Occurrences | Arrêt cumulé (min) |", "|---|---|---|---|"]
    lines += [f"| {r['failure_code']} | {r['description']} | {r['occurrences']} | {r['downtime_min']} |" for r in rows]
    return "\n".join(lines)


def run(question: str, asset_tag: str | None = None, history: list[tuple[str, str]] | None = None):
    nq = normalize_query(question)       # Darija / arabe -> français
    q_fr = nq["french"]
    text = f"{question} {q_fr}"
    intents = _intents(text)

    def done(out: str, tool_name: str, args: dict):
        return out, [{"tool": tool_name, "args": args, "result": out}], nq

    # 1) Une seule intention SQL connue : réponse déterministe, sans LLM
    if len(intents) == 1:
        if not asset_tag:
            return NEED_MACHINE, [], nq
        it = intents[0]
        if it == "diagnose":
            code = CODE_RE.search(text)
            args = {"asset_tag": asset_tag, "failure_code": code.group().upper() if code else ""}
            return done(diagnose_failure.invoke(args), "diagnose_failure", args)
        if it == "history":
            n = re.search(r"\b(\d{1,2})\b", text)
            args = {"asset_tag": asset_tag, "limit": min(int(n.group(1)), 20) if n else 5}
            return done(_fmt_history(get_maintenance_history.invoke(args)), "get_maintenance_history", args)
        if it == "stats":
            args = {"asset_tag": asset_tag}
            return done(_fmt_stats(get_failure_stats.invoke(args)), "get_failure_stats", args)
        if it == "risk":
            return done(risk_report(asset_tag), "predict_failure_risk", {"asset_tag": asset_tag})        
        return done(_fmt_count(asset_tag), "machine_summary", {"asset_tag": asset_tag})

    # 2) Aucune intention SQL : toujours le manuel (jamais de réponse libre du LLM)
    if not intents:
        args = {"question": q_fr, "asset_tag": asset_tag or ""}
        out = search_manuals.invoke(args, config={"configurable": {"asset_tag": asset_tag, "question": q_fr}})
        return done(out, "search_manuals", args)

    # 3) Plusieurs intentions : agent LLM avec outils
    ctx = "Aucune machine sélectionnée"
    if asset_tag:
        rows = query("SELECT * FROM machine_summary WHERE asset_tag = %s", (asset_tag,))
        if rows:
            ctx = (f"Machine sélectionnée : {asset_tag}\n"
                   f"FICHE GMAO (source de vérité) : {json.dumps(rows[0], default=str, ensure_ascii=False)}")
    messages = list(history or [])[-4:] + [("user", f"[{ctx}]\n{q_fr}")]
    result = agent.invoke(
        {"messages": messages},
        config={"recursion_limit": 10, "configurable": {"asset_tag": asset_tag, "question": q_fr}},
    )
    msgs = result["messages"]
    calls = [tc for m in msgs if m.type == "ai" for tc in (m.tool_calls or [])]
    outputs = [m for m in msgs if m.type == "tool"]
    trace = [{"tool": c["name"], "args": c["args"], "result": o.content} for c, o in zip(calls, outputs)]
    return msgs[-1].content.strip(), trace, nq