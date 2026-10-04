from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from app.config import ROOT
from app.ml.features import EMPTY, FEATURES, as_of_date, feats, index_events, load_machines

MODEL_PATH = ROOT / "models" / "failure_30d.joblib"
LABELS = {
    "age_years": "âge de la machine (ans)", "criticality": "criticité",
    "category_code": "type de machine", "days_since_pm": "jours depuis la dernière préventive",
    "pm_ratio": "ratio jours/plan préventif", "days_since_fail": "jours depuis la dernière panne",
    "n_fail_30": "pannes sur 30 j", "n_fail_90": "pannes sur 90 j", "n_fail_365": "pannes sur 12 mois",
    "downtime_90": "arrêt cumulé sur 90 j (min)", "n_pm_365": "préventives sur 12 mois",
}


@lru_cache(maxsize=1)
def _bundle():
    return joblib.load(MODEL_PATH)


def _fmt(name: str, v) -> str:
    return f"{v:.1f}" if name in ("age_years", "pm_ratio") else str(int(v))


def score_fleet():
    """Retourne (DataFrame du parc avec risque, niveau et facteurs, date d'arrêt des données)."""
    b = _bundle()
    model, base = b["model"], b["base_rate"]
    s, events = as_of_date(), index_events()
    rows = []
    for m in load_machines():
        f = feats(m["install"], m["criticality"], m["category"], m["pm_days"],
                  events.get(m["machine_id"], EMPTY), s)
        meta = {k: m[k] for k in ("asset_tag", "category", "manufacturer", "model_name",
                                  "workshop", "line_name", "pm_days")}
        rows.append({**meta, **f})
    df = pd.DataFrame(rows)
    X = df[FEATURES]
    df["risk"] = model.predict_proba(X)[:, 1]
    contrib = model.get_booster().predict(xgb.DMatrix(X), pred_contribs=True)[:, :-1]
    drivers = []
    for i in range(len(df)):
        top = [j for j in np.argsort(-contrib[i])[:3] if contrib[i][j] > 0]
        drivers.append("; ".join(f"{LABELS[FEATURES[j]]} = {_fmt(FEATURES[j], X.iloc[i, j])}" for j in top))
    df["drivers"] = drivers
    df["level"] = np.where(df["risk"] >= 2 * base, "Élevé", np.where(df["risk"] >= base, "Modéré", "Faible"))
    df["risk_pct"] = df["risk"] * 100
    df["model"] = df["manufacturer"] + " " + df["model_name"]
    return df, s


def risk_report(asset_tag: str) -> str:
    try:
        df, s = score_fleet()
    except FileNotFoundError:
        return "Modèle prédictif non entraîné. Lance : `python ml/train.py`."
    r = df[df["asset_tag"] == asset_tag]
    if r.empty:
        return "Machine introuvable."
    r = r.iloc[0]
    rank = int((df["risk"] > r["risk"]).sum()) + 1
    lines = [f"**{asset_tag}** : risque estimé de panne dans les 30 jours : **{r['risk']:.0%}** "
             f"(niveau {r['level']}, rang {rank}/{len(df)} du parc).",
             f"*Données arrêtées au {s}. Modèle entraîné sur historique synthétique.*", ""]
    if r["drivers"]:
        lines.append("**Facteurs qui augmentent le risque** : " + r["drivers"])
    late = int(r["days_since_pm"] - r["pm_days"])
    if late > 0:
        lines.append(f"\n⚠️ Maintenance préventive en retard de {late} jours : à planifier en priorité.")
    return "\n".join(lines)