import json
import sys
from pathlib import Path

import joblib
import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.ml.features import EMPTY, FEATURES, as_of_date, feats, index_events, load_machines  # noqa: E402

PARAMS = dict(n_estimators=250, max_depth=3, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
              min_child_weight=5, eval_metric="logloss", random_state=42)


def days(n: int):
    return np.timedelta64(n, "D")


def build_dataset():
    events, as_of = index_events(), as_of_date()
    rows = []
    for m in load_machines():
        ev = events.get(m["machine_id"], EMPTY)
        s = max(m["install"], np.datetime64("2022-01-01")) + days(180)      # 6 mois d'historique minimum
        while s <= as_of - days(30):
            f = feats(m["install"], m["criticality"], m["category"], m["pm_days"], ev, s)
            lo = np.searchsorted(ev["c"], s, "left")
            hi = np.searchsorted(ev["c"], s + days(30), "left")             # panne dans [s, s+30 j[
            rows.append({**f, "y": int(hi > lo), "date": pd.Timestamp(s), "machine_id": m["machine_id"]})
            s = s + days(7)
    return pd.DataFrame(rows), as_of


df, as_of = build_dataset()
split = pd.Timestamp(as_of) - pd.Timedelta(days=400)
train = df[df["date"] < split - pd.Timedelta(days=30)]    # aucun label ne déborde sur la période de test
test = df[df["date"] >= split]
print(f"{len(df)} instantanés · train {len(train)} · test {len(test)} · coupure {split.date()}")

model = XGBClassifier(**PARAMS).fit(train[FEATURES], train["y"])
p = model.predict_proba(test[FEATURES])[:, 1]
y = test["y"].to_numpy()
top = np.argsort(-p)[: max(1, int(0.1 * len(test)))]

metrics = {
    "prevalence_test": y.mean(),
    "auc_model": roc_auc_score(y, p),
    "auc_baseline_pm_ratio": roc_auc_score(y, test["pm_ratio"]),
    "avg_precision_model": average_precision_score(y, p),
    "brier_model": brier_score_loss(y, p),
    "brier_constant": brier_score_loss(y, np.full(len(y), train["y"].mean())),
    "precision_top10pct": y[top].mean(),
}
metrics = {k: float(v) for k, v in metrics.items()}

print("\n| Métrique (période de test) | Valeur |\n|---|---|")
for k, v in metrics.items():
    print(f"| {k} | {v:.3f} |")
imp = pd.Series(model.feature_importances_, index=FEATURES).sort_values(ascending=False)
print("\nImportance des variables :\n" + imp.round(3).to_string())

final = XGBClassifier(**PARAMS).fit(df[FEATURES], df["y"])      # modèle livré : réentraîné sur tout l'historique
out = ROOT / "models"
out.mkdir(exist_ok=True)
joblib.dump({"model": final, "features": FEATURES, "base_rate": float(df["y"].mean()),
             "metrics": metrics, "as_of": str(as_of)}, out / "failure_30d.joblib")
(out / "metrics.json").write_text(json.dumps(metrics, indent=2))

mlflow.set_tracking_uri(f"sqlite:///{(ROOT / 'mlflow.db').as_posix()}")
mlflow.set_experiment("failure-30d")
with mlflow.start_run():
    mlflow.log_params(PARAMS)
    mlflow.log_metrics(metrics)
    mlflow.log_artifact(str(out / "failure_30d.joblib"))
print("\nModèle enregistré dans models/failure_30d.joblib et tracé dans MLflow")