from langchain_core.tools import tool

from app.db import query as db_query
from app.rag.retriever import search


@tool
def search_manuals(question: str, asset_tag: str = "") -> str:
    """Cherche une procédure (dépannage, graissage, sécurité, codes d'erreur) dans les manuels
    techniques. Si asset_tag est fourni, la recherche est limitée au manuel du modèle de cette machine."""
    source = None
    if asset_tag:
        rows = db_query(
            "SELECT manual_file FROM machine_summary WHERE asset_tag = %s",
            (asset_tag.strip().upper(),),
        )
        if rows:
            source = rows[0]["manual_file"]
    docs = search(question, source=source)
    if not docs:
        return "Aucun extrait trouvé."
    return "\n\n".join(f"[{d['source']}, p.{d['page']}]\n{d['text']}" for d in docs)