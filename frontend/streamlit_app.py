import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import streamlit as st

from app.agents.graph import run
from app.db import query

st.set_page_config(page_title="Assistant Maintenance", page_icon="🔧", layout="wide")
st.title("🔧 Assistant de maintenance")

# Sélection manuelle de la machine (remplacée par la photo en phase 3)
machines = query("SELECT asset_tag, manufacturer, model_name, line_name FROM machine_summary ORDER BY asset_tag")
labels = {m["asset_tag"]: f"{m['asset_tag']} · {m['manufacturer']} {m['model_name']} · {m['line_name']}" for m in machines}
tag = st.sidebar.selectbox("Machine", [None] + list(labels), format_func=lambda t: "Aucune" if t is None else labels[t])

if tag:
    info = query("SELECT * FROM machine_summary WHERE asset_tag = %s", (tag,))[0]
    st.sidebar.metric("Interventions", info["total_interventions"])
    st.sidebar.metric("Correctives", info["corrective_count"])
    st.sidebar.caption(f"S/N {info['serial_number']} · statut : {info['status']}")
    st.sidebar.caption(f"Dernière intervention : {str(info['last_intervention'])[:10]}")

if "history" not in st.session_state:
    st.session_state.history = []  # (role, content, trace)


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