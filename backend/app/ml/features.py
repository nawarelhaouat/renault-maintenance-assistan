import numpy as np

from app.db import query

CATS = ["Robot", "Presse", "Visseuse", "Automate", "Robot peinture"]
FEATURES = ["age_years", "criticality", "category_code", "days_since_pm", "pm_ratio",
            "days_since_fail", "n_fail_30", "n_fail_90", "n_fail_365", "downtime_90", "n_pm_365"]
EMPTY = {"c": np.array([], dtype="datetime64[D]"), "cd": np.array([], dtype=int),
         "p": np.array([], dtype="datetime64[D]")}


def load_machines() -> list[dict]:
    rows = query("""SELECT m.machine_id, m.asset_tag, m.install_date, m.criticality, mm.category,
                           mm.manufacturer, mm.model_name, pl.workshop, pl.name AS line_name,
                           COALESCE((SELECT MIN(frequency_days) FROM maintenance_plans p
                                     WHERE p.model_id = m.model_id), 90) AS pm_days
                    FROM machines m
                    JOIN machine_models mm ON mm.model_id = m.model_id
                    JOIN production_lines pl ON pl.line_id = m.line_id
                    ORDER BY m.machine_id""")
    for r in rows:
        r["install"] = np.datetime64(r["install_date"], "D")
        r["pm_days"] = int(r["pm_days"])
    return rows


def index_events() -> dict:
    rows = query("SELECT machine_id, wo_type, opened_at, downtime_minutes FROM work_orders ORDER BY opened_at")
    raw = {}
    for r in rows:
        e = raw.setdefault(r["machine_id"], {"c": [], "cd": [], "p": []})
        d = np.datetime64(r["opened_at"].date(), "D")
        if r["wo_type"] == "corrective":
            e["c"].append(d)
            e["cd"].append(int(r["downtime_minutes"]))
        elif r["wo_type"] == "preventive":
            e["p"].append(d)
    return {k: {"c": np.array(v["c"], dtype="datetime64[D]"), "cd": np.array(v["cd"], dtype=int),
                "p": np.array(v["p"], dtype="datetime64[D]")} for k, v in raw.items()}


def as_of_date():
    d = query("SELECT MAX(opened_at)::date + 1 AS d FROM work_orders")[0]["d"]
    return np.datetime64(d, "D")


def feats(install, crit, cat, pm_days, ev, s) -> dict:
    """Features à la date s, calculées UNIQUEMENT avec les événements antérieurs à s (pas de fuite)."""
    one = np.timedelta64(1, "D")
    c, p, cd = ev["c"], ev["p"], ev["cd"]
    nc = int(np.searchsorted(c, s, "left"))
    npm = int(np.searchsorted(p, s, "left"))
    last_pm = p[npm - 1] if npm else install
    dsp = int((s - last_pm) / one)

    def n_in(days: int) -> int:
        return nc - int(np.searchsorted(c, s - np.timedelta64(days, "D"), "left"))

    lo90 = int(np.searchsorted(c, s - np.timedelta64(90, "D"), "left"))
    lo365 = int(np.searchsorted(p, s - np.timedelta64(365, "D"), "left"))
    return {
        "age_years": float((s - install) / one) / 365.25,
        "criticality": int(crit),
        "category_code": CATS.index(cat),
        "days_since_pm": dsp,
        "pm_ratio": dsp / pm_days,
        "days_since_fail": min(int((s - c[nc - 1]) / one), 365) if nc else 365,
        "n_fail_30": n_in(30), "n_fail_90": n_in(90), "n_fail_365": n_in(365),
        "downtime_90": int(cd[lo90:nc].sum()),
        "n_pm_365": npm - lo365,
    }