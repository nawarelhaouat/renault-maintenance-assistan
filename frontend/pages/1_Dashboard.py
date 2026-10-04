import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import pandas as pd
import streamlit as st
from app.db import query
from app.ml.predict import score_fleet

st.set_page_config(page_title="Dashboard maintenance", page_icon="📊", layout="wide")
st.title("📊 Dashboard maintenance prédictive")


@st.cache_data(ttl=600)
def fleet():
    df, s = score_fleet()
    return df, str(s)


try:
    df, as_of = fleet()
except FileNotFoundError:
    st.error("Modèle introuvable. Lance d'abord : python ml/train.py")
    st.stop()

st.caption(f"Données arrêtées au {as_of} · modèle XGBoost entraîné sur un historique synthétique")

workshops = sorted(df["workshop"].unique())
cats = sorted(df["category"].unique())
sel_w = st.sidebar.multiselect("Atelier", workshops, default=workshops)
sel_c = st.sidebar.multiselect("Type de machine", cats, default=cats)
view = df[df["workshop"].isin(sel_w) & df["category"].isin(sel_c)].copy()
if view.empty:
    st.warning("Aucune machine pour ces filtres.")
    st.stop()

k = query("""SELECT
    COUNT(*) FILTER (WHERE wo_type = 'corrective' AND opened_at >= %(d)s::date - 90) AS c90,
    COUNT(*) FILTER (WHERE wo_type = 'corrective' AND opened_at >= %(d)s::date - 180
                       AND opened_at < %(d)s::date - 90) AS c_prev,
    COALESCE(SUM(downtime_minutes) FILTER (WHERE opened_at >= %(d)s::date - 90), 0) AS dt90,
    COALESCE(SUM(downtime_minutes) FILTER (WHERE opened_at >= %(d)s::date - 180
                       AND opened_at < %(d)s::date - 90), 0) AS dt_prev
    FROM work_orders""", {"d": as_of})[0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Pannes (90 j)", int(k["c90"]), delta=int(k["c90"] - k["c_prev"]), delta_color="inverse")
c2.metric("Arrêt machine (h, 90 j)", round(float(k["dt90"]) / 60, 1),
          delta=round(float(k["dt90"] - k["dt_prev"]) / 60, 1), delta_color="inverse")
c3.metric("Machines à risque élevé", int((view["level"] == "Élevé").sum()))
c4.metric("Préventives en retard", int((view["pm_ratio"] > 1).sum()))

st.subheader("Machines classées par risque de panne à 30 jours")
view["retard_pm_j"] = (view["days_since_pm"] - view["pm_days"]).clip(lower=0)
table = view.sort_values("risk", ascending=False)[
    ["asset_tag", "model", "workshop", "level", "risk_pct", "retard_pm_j", "n_fail_90", "drivers"]]
st.dataframe(
    table, hide_index=True, use_container_width=True,
    column_config={
        "asset_tag": "Machine", "model": "Modèle", "workshop": "Atelier", "level": "Niveau",
        "risk_pct": st.column_config.ProgressColumn(
            "Risque 30 j", format="%.0f%%", min_value=0.0, max_value=max(30.0, float(view["risk_pct"].max()))),
        "retard_pm_j": "Retard préventive (j)", "n_fail_90": "Pannes 90 j", "drivers": "Facteurs principaux",
    },
)

left, right = st.columns(2)
with left:
    st.subheader("Top 10 des risques")
    st.bar_chart(table.head(10).set_index("asset_tag")["risk_pct"])
with right:
    st.subheader("Pannes par mois et type de machine (12 mois)")
    m = pd.DataFrame(query("""SELECT to_char(date_trunc('month', w.opened_at), 'YYYY-MM') AS mois,
                                     mm.category, COUNT(*) AS n
                              FROM work_orders w
                              JOIN machines ma ON ma.machine_id = w.machine_id
                              JOIN machine_models mm ON mm.model_id = ma.model_id
                              WHERE w.wo_type = 'corrective' AND w.opened_at >= %(d)s::date - 365
                              GROUP BY 1, 2 ORDER BY 1""", {"d": as_of}))
    if not m.empty:
        st.bar_chart(m.pivot(index="mois", columns="category", values="n").fillna(0))

st.subheader("Détail d'une machine")
sel = st.selectbox("Machine", table["asset_tag"])
r = df[df["asset_tag"] == sel].iloc[0]
a, b, c = st.columns(3)
a.metric("Risque 30 j", f"{r['risk']:.0%}")
b.metric("Niveau", r["level"])
c.metric("Jours depuis préventive", int(r["days_since_pm"]), delta=f"plan : {int(r['pm_days'])} j", delta_color="off")
if r["drivers"]:
    st.write("**Facteurs qui augmentent le risque** : " + r["drivers"])
hist = query("""SELECT w.opened_at::date AS date, w.wo_type AS type, w.failure_code AS code,
                       w.downtime_minutes AS arret_min, w.cost_mad
                FROM work_orders w JOIN machines ma ON ma.machine_id = w.machine_id
                WHERE ma.asset_tag = %s ORDER BY w.opened_at DESC LIMIT 10""", (sel,))
st.dataframe(pd.DataFrame(hist), hide_index=True, use_container_width=True)