import streamlit as st

st.set_page_config(page_title="OMA", layout="wide")
st.title("Operational Modal Analysis (OMA)")

if st.session_state.get("df") is None:
    st.warning("No data loaded. Return to the Landing Page and load a data file.")
    st.stop()

st.info("OMA / Stability Diagram page — under construction.")
