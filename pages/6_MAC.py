import streamlit as st

st.set_page_config(page_title="MAC", layout="wide")
st.title("Modal Assurance Criteria (MAC)")

if st.session_state.get("df") is None:
    st.warning("No data loaded. Return to the Landing Page and load a data file.")
    st.stop()

st.info("MAC plot page — under construction.")
