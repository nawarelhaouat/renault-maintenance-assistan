from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent

from app.config import LLM_MODEL
from app.tools.machine_db import get_failure_stats, get_machine_info, get_maintenance_history
from app.tools.rag_search import search_manuals

TOOLS = [get_machine_info, get_maintenance_history, get_failure_stats, search_manuals]

SYSTEM = """Tu es un assistant de maintenance pour une usine automobile.
Règles strictes :
- Pour toute donnée sur une machine (numéro de série, modèle, nombre d'interventions, historique, pannes),
  utilise les outils SQL. N'invente JAMAIS un chiffre ou une date.
- Pour une procédure (dépannage, graissage, codes d'erreur, sécurité), utilise search_manuals en passant
  l'asset_tag de la machine sélectionnée quand il existe.
- Tu peux combiner plusieurs outils (ex. historique des pannes puis procédure correspondante).
- Réponds dans la langue de la question, de façon courte, avec des étapes numérotées.
- Cite les sources des procédures sous la forme [fichier, p.X].
- Rappelle la consignation (LOTO) avant toute intervention mécanique ou électrique.
- Si un outil ne renvoie rien, dis-le clairement au lieu de deviner.
Le message utilisateur commence par la machine sélectionnée entre crochets."""

llm = ChatOllama(model=LLM_MODEL, temperature=0)
agent = create_react_agent(llm, TOOLS, prompt=SYSTEM)


def run(question: str, asset_tag: str | None = None, history: list[tuple[str, str]] | None = None):
    ctx = f"Machine sélectionnée : {asset_tag}" if asset_tag else "Aucune machine sélectionnée"
    messages = list(history or []) + [("user", f"[{ctx}]\n{question}")]
    result = agent.invoke({"messages": messages}, config={"recursion_limit": 10})
    msgs = result["messages"]

    calls = [tc for m in msgs if m.type == "ai" for tc in (m.tool_calls or [])]
    outputs = [m for m in msgs if m.type == "tool"]
    trace = [{"tool": c["name"], "args": c["args"], "result": o.content} for c, o in zip(calls, outputs)]
    return msgs[-1].content, trace