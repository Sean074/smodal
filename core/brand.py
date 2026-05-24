import streamlit as st

APP_NAME = "smodal"
TAGLINE = "Modal Analysis"


def page_header() -> None:
    st.caption(f"**{APP_NAME}** — {TAGLINE}")
    st.markdown("---")
