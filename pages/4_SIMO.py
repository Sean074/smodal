import streamlit as st

st.set_page_config(page_title="smodal · SIMO", layout="wide")

from core import brand

brand.page_header()
st.title("SIMO — System Identification (EMA)")

from core.simo_page import render

render()
