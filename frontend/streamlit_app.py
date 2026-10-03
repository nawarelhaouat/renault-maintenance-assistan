import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import streamlit as st

from app.agents.graph import run
from app.db import query
from app.vision.identify import identify

st.set_page_config(page_title="Assistant Maintenance", page_icon="🔧", layout="wide")
st.title("🔧 Assistant de maintenance")

machines = query("SELECT asset_tag, manufacturer, model_name, line_name FROM machine_summary ORDER BY asset_tag")
labels = {m["asset_tag"]: f"{m['asset_tag']} · {m['manufacturer']} {m['model_name']} · {m['line_name']}" for m in machines}

# ---------- Sidebar : photo ----------
with st.sidebar:
    st.subheader("📷 Identifier par photo")
    tab_up, tab_cam = st.tabs(["Importer", "Caméra"])
    with tab_up:
        up = st.file_uploader("Photo de la machine", type=["jpg", "jpeg", "png"])
    with tab_cam:
        cam = st.camera_input("Prendre une photo")
    photo = up or cam

    if photo is not None:
        data = photo.getvalue()
        key = hashlib.md5(data).hexdigest()
        if st.session_state.get("photo_key") != key:
            with st.spinner("Identification..."):
                st.session_state.ident = identify(data)
            st.session_state.photo_key = key
            st.session_state.photo_tag = None
            res = st.session_state.ident
            if res.get("asset_tag") and not res.get("needs_confirmation"):
                st.session_state.photo_tag = res["asset_tag"]

        res = st.session_state.ident
        if res.get("error"):
            st.error(res["error"])
        else:
            st.caption(f"Méthode : {res['method']} · confiance {res['confidence']:.0%}")
            if res.get("asset_tag") and res.get("needs_confirmation"):
                st.warning(f"Lecture à confirmer : {res['asset_tag']}")
                if st.button(f"✅ Confirmer {res['asset_tag']}"):
                    st.session_state.photo_tag = res["asset_tag"]
            elif res.get("candidates"):
                st.warning(f"Catégorie probable : {res['category']}. Choisis la machine :")
                cand = st.selectbox("Candidats", [c["asset_tag"] for c in res["candidates"]],
                                    format_func=lambda t: labels[t])
                if st.button("✅ Valider ce choix"):
                    st.session_state.photo_tag = cand

    if st.session_state.get("photo_tag") and st.button("Effacer la photo"):
        st.session_state.photo_tag = None

    st.divider()
    manual = st.selectbox("Ou choisir manuellement", [None] + list(labels),
                          format_func=lambda t: "Aucune" if t is None else labels[t])

tag = st.session_state.get("photo_tag") or manual

if tag:
    info = query("SELECT * FROM machine_summary WHERE asset_tag = %s", (tag,))[0]
    st.info(f"**{info['asset_tag']}** · {info['manufacturer']} {info['model_name']} · {info['line_name']} "
            f"· S/N {info['serial_number']} · statut : {info['status']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Interventions", info["total_interventions"])
    c2.metric("Correctives", info["corrective_count"])
    c3.metric("Arrêt cumulé (h)", round(info["total_downtime_min"] / 60, 1))
    c4.metric("MTTR (min)", info["mttr_min"])

if "history" not in st.session_state:
    st.session_state.history = []


def show_trace(trace):
    if trace:
        with st.expander("Outils utilisés"):
            for t in trace:
                st.caption(f"{t['tool']}({t['args']})")
                st.code(str(t["result"])[:1500])


for role, content, trace in st.session_state.history:
    with st.chat_message(role):
        st.markdown(content)
        show_trace(trace)

if q := st.chat_input("Pose ta question (français / darija)..."):
    past = [(r, c) for r, c, _ in st.session_state.history][-6:]
    st.session_state.history.append(("user", q, None))
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant"):
        with st.spinner("L'agent réfléchit..."):
            text, trace = run(q, tag, past)
        st.markdown(text)
        show_trace(trace)
    st.session_state.history.append(("assistant", text, trace))