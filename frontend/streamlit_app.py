import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "backend"))

import streamlit as st

from app.config import MANUALS_DIR
from app.rag.retriever import answer

st.set_page_config(page_title="Assistant Maintenance", page_icon="🔧")
st.title("🔧 Assistant de maintenance")

manuals = ["Tous les manuels"] + sorted(p.name for p in MANUALS_DIR.glob("*.pdf"))
choice = st.sidebar.selectbox("Manuel", manuals)
source = None if choice == manuals[0] else choice

if "history" not in st.session_state:
    st.session_state.history = []

for role, content, docs in st.session_state.history:
    with st.chat_message(role):
        st.markdown(content)
        if docs:
            with st.expander("Sources"):
                for d in docs:
                    st.caption(f"{d['source']} p.{d['page']} (score {d['score']:.2f})")
                    st.write(d["text"])

if q := st.chat_input("Pose ta question (français / darija)..."):
    st.session_state.history.append(("user", q, None))
    with st.chat_message("user"):
        st.markdown(q)
    with st.chat_message("assistant"):
        with st.spinner("Recherche dans les manuels..."):
            text, docs = answer(q, source)
        st.markdown(text)
        with st.expander("Sources"):
            for d in docs:
                st.caption(f"{d['source']} p.{d['page']} (score {d['score']:.2f})")
                st.write(d["text"])
    st.session_state.history.append(("assistant", text, docs))