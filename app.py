import streamlit as st
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

from core.data_loader import load_csv, compute_summary

st.set_page_config(page_title="Modal Analysis", layout="wide")

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
# Page header
# ---------------------------------------------------------------------------
st.title("Modal Analysis — System Identification")
st.markdown("---")

# ---------------------------------------------------------------------------
# Section 1: Analysis information
# ---------------------------------------------------------------------------
st.header("Analysis Information")
col1, col2 = st.columns(2)
with col1:
    st.session_state.analysis_name = st.text_input(
        "Analysis Name", value=st.session_state.analysis_name
    )
with col2:
    st.session_state.analyst = st.text_input(
        "Analyst Name", value=st.session_state.analyst
    )
st.session_state.description = st.text_area(
    "Analysis Description", value=st.session_state.description, height=80
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Section 2: Data load
# ---------------------------------------------------------------------------
st.header("Load Data")
st.caption(
    "CSV format: one column named **time** (seconds), remaining columns are data channels. "
    "Multiple files may be merged if they share the same time axis."
)

uploaded_files = st.file_uploader(
    "Select data file(s)", type=["csv"], accept_multiple_files=True
)

if uploaded_files:
    frames = []
    errors = []
    for f in uploaded_files:
        df_i, err = load_csv(f)
        if err:
            errors.append(f"{f.name}: {err}")
        else:
            frames.append(df_i)

    if errors:
        for e in errors:
            st.error(e)

    if frames:
        if len(frames) == 1:
            df = frames[0]
        else:
            # Merge multiple files on time column (inner join)
            df = frames[0]
            for df_i in frames[1:]:
                data_cols = [c for c in df_i.columns if c != "time"]
                df = df.merge(df_i[["time"] + data_cols], on="time", how="inner")

        st.session_state.df = df

# ---------------------------------------------------------------------------
# Section 3: Channel assignment (only shown once data is loaded)
# ---------------------------------------------------------------------------
if st.session_state.df is not None:
    df = st.session_state.df
    channels = [c for c in df.columns if c != "time"]

    st.markdown("---")
    st.header("Channel Assignment")
    col_a, col_b = st.columns(2)

    with col_a:
        input_ch = st.selectbox(
            "Input channel (force / excitation)",
            channels,
            index=channels.index(st.session_state.input_channel)
            if st.session_state.input_channel in channels
            else 0,
        )
        st.session_state.input_channel = input_ch

    with col_b:
        available_outputs = [c for c in channels if c != input_ch]
        default_outputs = (
            [c for c in st.session_state.output_channels if c in available_outputs]
            or available_outputs
        )
        output_chs = st.multiselect(
            "Output channels (accelerometers / responses)",
            available_outputs,
            default=default_outputs,
        )
        st.session_state.output_channels = output_chs

    # ---------------------------------------------------------------------------
    # Section 4: Data summary
    # ---------------------------------------------------------------------------
    if output_chs:
        st.markdown("---")
        st.header("Data Summary")

        summary_rows = compute_summary(df, input_ch, output_chs)
        st.session_state.sample_rate = summary_rows[0]["Sample Rate (Hz)"]

        summary_df = pd.DataFrame(summary_rows)
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        # ---------------------------------------------------------------------------
        # Section 5: Comment and log
        # ---------------------------------------------------------------------------
        st.markdown("---")
        st.header("Analysis Log")
        st.session_state.comment = st.text_area(
            "Analysis Comment", value=st.session_state.comment, height=80
        )

        if st.button("Save Analysis Log", type="primary"):
            log = {
                "date": datetime.now().isoformat(timespec="seconds"),
                "analysis_name": st.session_state.analysis_name,
                "analyst": st.session_state.analyst,
                "description": st.session_state.description,
                "comment": st.session_state.comment,
                "data_summary": summary_rows,
            }
            safe_name = (st.session_state.analysis_name or "analysis").replace(" ", "_")
            log_path = Path("data/output") / f"{safe_name}_log.json"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps(log, indent=2))
            st.success(f"Log saved to `{log_path}`")

        st.markdown("---")
        st.success("Data loaded successfully. Use the sidebar to navigate to the next page.")
