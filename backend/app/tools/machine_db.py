import json

from langchain_core.tools import tool

from app.db import query


def _dump(x) -> str:
    return json.dumps(x, default=str, ensure_ascii=False)


@tool
def get_machine_info(asset_tag: str) -> str:
    """Fiche d'une machine : modèle, ligne, statut, date d'installation, nombre total
    d'interventions (préventives/correctives), dernière intervention, temps d'arrêt, MTTR.
    asset_tag exemple : TNG-ROB-0007."""
    rows = query("SELECT * FROM machine_summary WHERE asset_tag = %s", (asset_tag.strip().upper(),))
    return _dump(rows[0]) if rows else "Machine introuvable."


@tool
def get_maintenance_history(asset_tag: str, limit: int = 5) -> str:
    """Dernières interventions de maintenance d'une machine (type, date, panne, technicien,
    temps d'arrêt, coût en MAD)."""
    limit = max(1, min(int(limit), 20))
    rows = query(
        """SELECT w.wo_id, w.wo_type, w.opened_at, w.downtime_minutes, w.description,
                  w.failure_code, f.description AS failure, t.full_name AS technician, w.cost_mad
           FROM work_orders w
           JOIN machines m USING (machine_id)
           LEFT JOIN failure_codes f ON f.code = w.failure_code
           LEFT JOIN technicians t ON t.technician_id = w.technician_id
           WHERE m.asset_tag = %s
           ORDER BY w.opened_at DESC LIMIT %s""",
        (asset_tag.strip().upper(), limit),
    )
    return _dump(rows) if rows else "Aucune intervention trouvée."


@tool
def get_failure_stats(asset_tag: str) -> str:
    """Pannes les plus fréquentes d'une machine : code, description, nombre d'occurrences,
    temps d'arrêt cumulé en minutes."""
    rows = query(
        """SELECT w.failure_code, f.description, COUNT(*) AS occurrences,
                  SUM(w.downtime_minutes) AS downtime_min
           FROM work_orders w
           JOIN machines m USING (machine_id)
           JOIN failure_codes f ON f.code = w.failure_code
           WHERE m.asset_tag = %s AND w.wo_type = 'corrective'
           GROUP BY w.failure_code, f.description
           ORDER BY occurrences DESC""",
        (asset_tag.strip().upper(),),
    )
    return _dump(rows) if rows else "Aucune panne enregistrée."