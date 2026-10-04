import json

from app.db import query
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool


def _dump(x) -> str:
    return json.dumps(x, default=str, ensure_ascii=False)


def resolve_tag(arg: str | None, config: RunnableConfig | None) -> str:
    """La machine sélectionnée dans l'interface est prioritaire sur ce que le LLM écrit."""
    forced = ((config or {}).get("configurable") or {}).get("asset_tag")
    return (forced or arg or "").strip().upper()


@tool
def get_machine_info(asset_tag: str = "", config: RunnableConfig = None) -> str:
    """Fiche de la machine : modèle, ligne, statut, numéro de série, nombre TOTAL d'interventions,
    préventives, correctives, temps d'arrêt, MTTR. À utiliser pour toute question de comptage.
    Laisse asset_tag vide si une machine est déjà sélectionnée."""
    rows = query("SELECT * FROM machine_summary WHERE asset_tag = %s", (resolve_tag(asset_tag, config),))
    return _dump(rows[0]) if rows else "Machine introuvable."


@tool
def get_maintenance_history(asset_tag: str = "", limit: int = 5, config: RunnableConfig = None) -> str:
    """Dernières interventions (type, date, panne, technicien, arrêt, coût MAD).
    Le champ total_interventions donne le vrai nombre : ne compte jamais les lignes toi-même."""
    tag = resolve_tag(asset_tag, config)
    limit = max(1, min(int(limit), 20))
    total = query("SELECT COUNT(*) AS n FROM work_orders w JOIN machines m USING (machine_id) "
                  "WHERE m.asset_tag = %s", (tag,))[0]["n"]
    rows = query(
        """SELECT w.wo_id, w.wo_type, w.opened_at, w.downtime_minutes, w.failure_code,
                  f.description AS failure, t.full_name AS technician, w.cost_mad
           FROM work_orders w
           JOIN machines m USING (machine_id)
           LEFT JOIN failure_codes f ON f.code = w.failure_code
           LEFT JOIN technicians t ON t.technician_id = w.technician_id
           WHERE m.asset_tag = %s ORDER BY w.opened_at DESC LIMIT %s""",
        (tag, limit),
    )
    return _dump({"asset_tag": tag, "total_interventions": total, "shown": len(rows), "interventions": rows})


@tool
def get_failure_stats(asset_tag: str = "", config: RunnableConfig = None) -> str:
    """Pannes les plus fréquentes de la machine : code, description, occurrences, arrêt cumulé (min)."""
    rows = query(
        """SELECT w.failure_code, f.description, COUNT(*) AS occurrences,
                  SUM(w.downtime_minutes) AS downtime_min
           FROM work_orders w JOIN machines m USING (machine_id)
           JOIN failure_codes f ON f.code = w.failure_code
           WHERE m.asset_tag = %s AND w.wo_type = 'corrective'
           GROUP BY w.failure_code, f.description ORDER BY occurrences DESC""",
        (resolve_tag(asset_tag, config),),
    )
    return _dump(rows) if rows else "Aucune panne enregistrée."