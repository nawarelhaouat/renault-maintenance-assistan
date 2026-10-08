import time

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_roles
from app.db import query

router = APIRouter(prefix="/dashboard", dependencies=[Depends(require_roles("technician", "manager", "admin"))])
_cache: dict = {"t": 0.0, "v": None}

KPI_SQL = """SELECT
    COUNT(*) FILTER (WHERE wo_type = 'corrective' AND opened_at >= %(d)s::date - 90) AS c90,
    COUNT(*) FILTER (WHERE wo_type = 'corrective' AND opened_at >= %(d)s::date - 180
                       AND opened_at < %(d)s::date - 90) AS c_prev,
    COALESCE(SUM(downtime_minutes) FILTER (WHERE opened_at >= %(d)s::date - 90), 0) AS dt90,
    COALESCE(SUM(downtime_minutes) FILTER (WHERE opened_at >= %(d)s::date - 180
                       AND opened_at < %(d)s::date - 90), 0) AS dt_prev
    FROM work_orders"""

FLEET_COLS = ["asset_tag", "model", "category", "workshop", "line_name", "level", "risk",
              "days_since_pm", "pm_days", "n_fail_90", "drivers"]


def _fleet():
    if _cache["v"] is None or time.time() - _cache["t"] > 300:
        try:
            from app.ml.predict import score_fleet
            df, as_of = score_fleet()
        except FileNotFoundError:
            raise HTTPException(status_code=503,
                                detail="Modèle prédictif non entraîné : lance python ml/train.py") from None
        _cache.update(t=time.time(), v=(df, str(as_of)))
    return _cache["v"]


@router.get("/summary")
def summary():
    df, as_of = _fleet()
    k = query(KPI_SQL, {"d": as_of})[0]
    return {"as_of": as_of, "machines": len(df),
            "failures_90": int(k["c90"]), "failures_prev": int(k["c_prev"]),
            "downtime_h_90": round(float(k["dt90"]) / 60, 1), "downtime_h_prev": round(float(k["dt_prev"]) / 60, 1),
            "high_risk": int((df["level"] == "Élevé").sum()), "pm_late": int((df["pm_ratio"] > 1).sum())}


@router.get("/fleet")
def fleet():
    df, as_of = _fleet()
    return {"as_of": as_of, "machines": df.sort_values("risk", ascending=False)[FLEET_COLS].to_dict("records")}


@router.get("/failures-monthly")
def failures_monthly():
    _, as_of = _fleet()
    return query("""SELECT to_char(date_trunc('month', opened_at), 'YYYY-MM') AS month, COUNT(*) AS failures
                    FROM work_orders WHERE wo_type = 'corrective' AND opened_at >= %(d)s::date - 365
                    GROUP BY 1 ORDER BY 1""", {"d": as_of})


@router.get("/machines/{asset_tag}")
def machine_detail(asset_tag: str):
    df, _ = _fleet()
    row = df[df["asset_tag"] == asset_tag.upper()]
    if row.empty:
        raise HTTPException(status_code=404, detail="Machine introuvable")
    history = query("""SELECT w.opened_at::date AS date, w.wo_type AS type, w.failure_code AS code,
                              w.downtime_minutes AS downtime_min, w.cost_mad
                       FROM work_orders w JOIN machines m ON m.machine_id = w.machine_id
                       WHERE m.asset_tag = %s ORDER BY w.opened_at DESC LIMIT 10""", (asset_tag.upper(),))
    return {"machine": row[FLEET_COLS].to_dict("records")[0], "history": history}