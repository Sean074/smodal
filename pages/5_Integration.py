import streamlit as st

st.set_page_config(page_title="Integration / Differentiation", layout="wide")
st.title("Integration / Differentiation")

if st.session_state.get("df") is None:
    st.warning("No data loaded. Return to the Landing Page and load a data file.")
    st.stop()

st.info("Integration / Differentiation page — under construction.")
