import numpy as np
import pandas as pd
import streamlit as st
from scipy.signal import butter, sosfiltfilt, sosfreqz
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Time History", layout="wide")
st.title("Time History")

if st.session_state.get("df") is None:
    st.warning("No data loaded. Return to the Landing Page and load a data file.")
    st.stop()

df = st.session_state.df
fs = st.session_state.sample_rate
input_ch = st.session_state.input_channel
output_chs = st.session_state.output_channels
all_channels = [input_ch] + list(output_chs) if input_ch else list(output_chs)
time = df["time"].values

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
st.markdown("---")
ctrl_col, filt_col = st.columns([1, 1])

with ctrl_col:
    st.subheader("Display")
    selected_channels = st.multiselect(
        "Channels to plot",
        options=all_channels,
        default=all_channels,
    )
    stacked = st.toggle("Stacked subplots", value=True)
    t_min = float(time[0])
    t_max = float(time[-1])
    t_range = st.slider(
        "Time range (s)",
        min_value=t_min,
        max_value=t_max,
        value=(t_min, t_max),
        step=round((t_max - t_min) / 1000, 6),
    )

with filt_col:
    st.subheader("Filter")
    filter_type = st.selectbox(
        "Filter type",
        ["None", "Lowpass", "Highpass", "Bandpass", "Bandstop"],
    )
    apply_filter = filter_type != "None"

    nyq = fs / 2.0
    f_lo, f_hi = None, None
    order = 4

    if apply_filter:
        order = st.slider("Filter order", min_value=1, max_value=8, value=4)
        if filter_type in ("Lowpass", "Highpass"):
            fc = st.number_input(
                "Cutoff frequency (Hz)",
                min_value=0.01,
                max_value=float(nyq - 0.01),
                value=min(10.0, nyq * 0.5),
                step=0.5,
                format="%.2f",
            )
            f_lo = fc
        else:
            c1, c2 = st.columns(2)
            with c1:
                f_lo = st.number_input(
                    "Low cutoff (Hz)",
                    min_value=0.01,
                    max_value=float(nyq - 0.02),
                    value=1.0,
                    step=0.5,
                    format="%.2f",
                )
            with c2:
                f_hi = st.number_input(
                    "High cutoff (Hz)",
                    min_value=float(f_lo + 0.01),
                    max_value=float(nyq - 0.01),
                    value=min(float(f_lo + 10.0), float(nyq - 0.01)),
                    step=0.5,
                    format="%.2f",
                )

# ---------------------------------------------------------------------------
# Build filter once
# ---------------------------------------------------------------------------
def _build_sos(ftype, order, f_lo, f_hi, nyq):
    btype_map = {
        "Lowpass": "low",
        "Highpass": "high",
        "Bandpass": "bandpass",
        "Bandstop": "bandstop",
    }
    btype = btype_map[ftype]
    if btype in ("low", "high"):
        Wn = f_lo / nyq
    else:
        Wn = [f_lo / nyq, f_hi / nyq]
    return butter(order, Wn, btype=btype, output="sos")


sos = None
filter_error = None
if apply_filter:
    try:
        sos = _build_sos(filter_type, order, f_lo, f_hi, nyq)
    except Exception as e:
        filter_error = str(e)

if filter_error:
    st.error(f"Filter configuration error: {filter_error}")

# ---------------------------------------------------------------------------
# Slice to time range
# ---------------------------------------------------------------------------
mask = (time >= t_range[0]) & (time <= t_range[1])
t_plot = time[mask]

# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
st.markdown("---")

if not selected_channels:
    st.info("Select at least one channel to plot.")
    st.stop()

n = len(selected_channels)

if stacked:
    fig = make_subplots(
        rows=n,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=selected_channels,
    )
    for i, ch in enumerate(selected_channels, start=1):
        raw = df[ch].values[mask]
        color = "#1f77b4" if ch == input_ch else f"hsl({(i * 47) % 360}, 65%, 50%)"

        fig.add_trace(
            go.Scatter(
                x=t_plot,
                y=raw,
                mode="lines",
                name=ch,
                line=dict(color=color, width=1),
                legendgroup=ch,
                showlegend=True,
            ),
            row=i,
            col=1,
        )

        if sos is not None:
            filtered = sosfiltfilt(sos, df[ch].values)[mask]
            fig.add_trace(
                go.Scatter(
                    x=t_plot,
                    y=filtered,
                    mode="lines",
                    name=f"{ch} (filtered)",
                    line=dict(color="red", width=1.5, dash="dash"),
                    legendgroup=ch,
                    showlegend=True,
                ),
                row=i,
                col=1,
            )

        fig.update_yaxes(title_text=ch, row=i, col=1)

    fig.update_xaxes(title_text="Time (s)", row=n, col=1)
    fig.update_layout(
        height=220 * n,
        margin=dict(t=40, b=40, l=60, r=20),
        legend=dict(orientation="h", y=-0.06),
    )

else:
    fig = go.Figure()
    for i, ch in enumerate(selected_channels):
        raw = df[ch].values[mask]
        color = f"hsl({(i * 47) % 360}, 65%, 50%)"
        fig.add_trace(
            go.Scatter(
                x=t_plot,
                y=raw,
                mode="lines",
                name=ch,
                line=dict(color=color, width=1),
                legendgroup=ch,
            )
        )
        if sos is not None:
            filtered = sosfiltfilt(sos, df[ch].values)[mask]
            fig.add_trace(
                go.Scatter(
                    x=t_plot,
                    y=filtered,
                    mode="lines",
                    name=f"{ch} (filtered)",
                    line=dict(color=color, width=1.5, dash="dash"),
                    legendgroup=ch,
                )
            )

    fig.update_layout(
        height=500,
        xaxis_title="Time (s)",
        yaxis_title="Amplitude",
        margin=dict(t=20, b=60, l=60, r=20),
        legend=dict(orientation="h", y=-0.12),
    )

st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Filter frequency response
# ---------------------------------------------------------------------------
if sos is not None and not filter_error:
    with st.expander("Filter frequency response", expanded=False):
        w, h = sosfreqz(sos, worN=4096, fs=fs)
        gain_db = 20 * np.log10(np.maximum(np.abs(h), 1e-12))
        phase_deg = np.degrees(np.unwrap(np.angle(h)))

        fig_fr = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            subplot_titles=("Gain (dB)", "Phase (°)"),
        )
        fig_fr.add_trace(
            go.Scatter(x=w, y=gain_db, mode="lines", line=dict(color="#1f77b4", width=1.5), showlegend=False),
            row=1, col=1,
        )
        fig_fr.add_trace(
            go.Scatter(x=w, y=phase_deg, mode="lines", line=dict(color="#ff7f0e", width=1.5), showlegend=False),
            row=2, col=1,
        )
        fig_fr.update_xaxes(title_text="Frequency (Hz)", row=2, col=1)
        fig_fr.update_yaxes(title_text="Gain (dB)", row=1, col=1)
        fig_fr.update_yaxes(title_text="Phase (°)", row=2, col=1)
        fig_fr.update_layout(
            height=420,
            margin=dict(t=40, b=40, l=60, r=20),
            title_text=f"{filter_type}  |  order {order}  |  "
                       + (f"{f_lo} Hz" if filter_type in ("Lowpass", "Highpass") else f"{f_lo}–{f_hi} Hz"),
        )
        st.plotly_chart(fig_fr, use_container_width=True)

# ---------------------------------------------------------------------------
# Persist processed (trimmed + filtered) signals for downstream pages
# ---------------------------------------------------------------------------
_proc: dict = {"time": t_plot}
for _ch in all_channels:
    if sos is not None and not filter_error:
        _proc[_ch] = sosfiltfilt(sos, df[_ch].values)[mask]
    else:
        _proc[_ch] = df[_ch].values[mask]
st.session_state["processed_df"] = pd.DataFrame(_proc)
st.session_state["processing_info"] = {
    "trim": t_range,
    "filter": filter_type if (apply_filter and not filter_error) else None,
    "order": order if (apply_filter and not filter_error) else None,
    "f_lo": f_lo if (apply_filter and not filter_error) else None,
    "f_hi": f_hi if (apply_filter and not filter_error) else None,
}

# ---------------------------------------------------------------------------
# Per-channel stats (in time-range window)
# ---------------------------------------------------------------------------
with st.expander("Channel statistics (visible window)"):
    rows = []
    for ch in selected_channels:
        sig = df[ch].values[mask]
        rows.append({
            "Channel": ch,
            "Type": "Input" if ch == input_ch else "Output",
            "Min": round(float(sig.min()), 6),
            "Max": round(float(sig.max()), 6),
            "Mean": round(float(sig.mean()), 6),
            "RMS": round(float(np.sqrt(np.mean(sig**2))), 6),
            "Std Dev": round(float(sig.std()), 6),
            "Samples": int(sig.size),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
