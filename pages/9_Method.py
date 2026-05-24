import base64
from pathlib import Path

import nbformat
import streamlit as st

st.set_page_config(page_title="smodal · Method", layout="wide")

from core import brand

brand.page_header()

st.title("Analysis Methods")

nb_path = Path("docs/methods.ipynb")
if not nb_path.exists():
    st.error(f"Notebook not found: {nb_path}")
    st.stop()

nb = nbformat.read(nb_path.open(), as_version=4)

for cell in nb.cells:
    if cell.cell_type == "markdown":
        st.markdown(cell.source)

    elif cell.cell_type == "code" and cell.source.strip():
        with st.expander("Show code", expanded=False):
            st.code(cell.source, language="python")
        for output in cell.get("outputs", []):
            otype = output.get("output_type", "")
            if otype in ("display_data", "execute_result"):
                data = output.get("data", {})
                if "image/png" in data:
                    st.image(base64.b64decode(data["image/png"]))
                elif "text/plain" in data:
                    st.text(data["text/plain"])
            elif otype == "stream":
                st.text(output.get("text", ""))
