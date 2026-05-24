import streamlit as st

st.set_page_config(page_title="smodal", layout="wide")

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "df": None,
    "input_channel": None,
    "output_channels": [],
    "sample_rate": None,
    "analysis_name": "",
    "analyst": "",
    "description": "",
    "comment": "",
}
for key, val in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------------------------------------------------------------------
# Page content
# ---------------------------------------------------------------------------
st.title("smodal — Modal Analysis")
st.caption(
    "Experimental & operational modal analysis (EMA / OMA) from a multi-channel CSV — "
    "open source on [GitHub](https://github.com/Sean074/smodal)."
)
st.markdown("---")

st.header("Analysis Information")
col1, col2 = st.columns(2)
with col1:
    st.session_state.analysis_name = st.text_input("Analysis Name", value=st.session_state.analysis_name)
with col2:
    st.session_state.analyst = st.text_input("Analyst Name", value=st.session_state.analyst)
st.session_state.description = st.text_area("Analysis Description", value=st.session_state.description, height=80)

st.markdown("---")
st.subheader("Workflow")
st.markdown(
    """
1. **Time History** — load a CSV, assign channels, trim and filter the signal.
2. **FFT** — inspect the frequency content of each channel.
3. **Spectral Analysis** — compute FRFs (H1 / H2 / Hv), PSDs, and coherence.
4. **SIMO** — single-reference system identification (pLSCF stability diagram, mode extraction).
5. **MIMO** — multi-reference system identification from two independent excitation runs.
6. **MAC** *(in work)* — Modal Assurance Criterion matrix between identified mode shapes.
7. **Wireframe** — 3-D mode shape visualisation.
8. **Method** — signal-processing reference: derivations, algorithms, and worked examples.

> **SIMO and MIMO users:** load your data directly on the SIMO or MIMO page — it has its own file uploaders and does not depend on pages 1–3.
"""
)
