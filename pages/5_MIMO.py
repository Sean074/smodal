import streamlit as st

st.set_page_config(page_title="smodal · MIMO", layout="wide")

from core import brand

brand.page_header()
st.title("MIMO — Multi-Reference System Identification (EMA)")

from core.mimo_page import render

render()
