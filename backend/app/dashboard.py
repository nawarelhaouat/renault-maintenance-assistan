import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_roles
from app.db import query

router = APIRouter(prefix="/dashboard", dependencies=[Depends(require_roles("technician", "manager", "admin"))])
_cache: dict = {"t": 0.0, "v": None}

KPI_SQL = """SELECT
    COUNT(*) FILTER (WHERE wo_type = 'corrective' AND opened_at >= %(d)s::date - %(n)s) AS cur,
    COUNT(*) FILTER (WHERE wo_type = 'corrective' AND opened_at >= %(d)s::date - 2 * %(n)s
                       AND opened_at < %(d)s::date - %(n)s) AS prev,
    COALESCE(SUM(downtime_minutes) FILTER (WHERE opened_at >= %(d)s::date - %(n)s), 0) AS dt_cur,
    COALESCE(SUM(downtime_minutes) FILTER (WHERE opened_at >= %(d)s::date - 2 * %(n)s
                       AND opened_at < %(d)s::date - %(n)s), 0) AS dt_prev
    FROM work_orders"""

FLEET_COLS = ["asset_tag", "model", "category", "workshop", "line_name", "level", "risk",
              "days_since_pm", "pm_days", "n_fail_90", "drivers"]

_ROOT = Path(__file__).resolve()
METRICS_CANDIDATES = [_ROOT.parents[2] / "models" / "metrics.json", _ROOT.parents[1] / "models" / "metrics.json",
                      Path("models") / "metrics.json"]


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
def summary(days: int = Query(90, ge=30, le=730)):
    df, as_of = _fleet()
    k = query(KPI_SQL, {"d": as_of, "n": days})[0]
    return {"as_of": as_of, "days": days, "machines": len(df),
            "failures": int(k["cur"]), "failures_prev": int(k["prev"]),
            "downtime_h": round(float(k["dt_cur"]) / 60, 1), "downtime_h_prev": round(float(k["dt_prev"]) / 60, 1),
            "high_risk": int((df["level"] == "Élevé").sum()), "pm_late": int((df["pm_ratio"] > 1).sum())}


@router.get("/fleet")
def fleet():
    df, as_of = _fleet()
    return {"as_of": as_of, "machines": df.sort_values("risk", ascending=False)[FLEET_COLS].to_dict("records")}


@router.get("/failures-monthly")
def failures_monthly():
    df, as_of = _fleet()
    rows = query("""SELECT to_char(date_trunc('month', w.opened_at), 'YYYY-MM') AS month,
                           m.asset_tag, COUNT(*) AS failures
                    FROM work_orders w JOIN machines m ON m.machine_id = w.machine_id
                    WHERE w.wo_type = 'corrective' AND w.opened_at >= %(d)s::date - 365
                    GROUP BY 1, 2 ORDER BY 1""", {"d": as_of})
    cat = dict(zip(df["asset_tag"], df["category"]))
    months: dict[str, dict] = {}
    for r in rows:
        c = cat.get(r["asset_tag"], "Autre")
        row = months.setdefault(r["month"], {"month": r["month"]})
        row[c] = row.get(c, 0) + int(r["failures"])
    return {"categories": sorted(set(cat.values())), "data": [months[k] for k in sorted(months)]}


@router.get("/failure-codes")
def failure_codes(days: int = Query(90, ge=30, le=730)):
    _, as_of = _fleet()
    rows = query("""SELECT failure_code AS code, COUNT(*) AS failures,
                           COALESCE(SUM(downtime_minutes), 0) AS downtime_min
                    FROM work_orders
                    WHERE wo_type = 'corrective' AND failure_code IS NOT NULL
                      AND opened_at >= %(d)s::date - %(n)s
                    GROUP BY 1 ORDER BY 2 DESC, 1""", {"d": as_of, "n": days})
    total = sum(int(r["failures"]) for r in rows) or 1
    run, out = 0, []
    for r in rows:
        run += int(r["failures"])
        out.append({"code": r["code"], "failures": int(r["failures"]),
                    "downtime_h": round(float(r["downtime_min"]) / 60, 1),
                    "cumulative": round(100 * run / total, 1)})
    return out


@router.get("/model-metrics")
def model_metrics():
    for p in METRICS_CANDIDATES:
        if p.exists():
            return {"available": True, "metrics": json.loads(p.read_text(encoding="utf-8"))}
    return {"available": False, "metrics": {}}


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