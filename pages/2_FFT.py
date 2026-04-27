import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.spectral import compute_fft

st.set_page_config(page_title="FFT", layout="wide")
st.title("FFT")

if st.session_state.get("df") is None:
    st.warning("No data loaded. Return to the Landing Page and load a data file.")
    st.stop()

# ── Data source ───────────────────────────────────────────────────────────────
_processed_df = st.session_state.get("processed_df")
_proc_info = st.session_state.get("processing_info", {})
_has_processed = _processed_df is not None

_source_options = ["Raw (full dataset)"]
if _has_processed:
    _label_parts = []
    _t = _proc_info.get("trim")
    if _t:
        _label_parts.append(f"trimmed {_t[0]:.3g}–{_t[1]:.3g} s")
    _filt = _proc_info.get("filter")
    if _filt:
        _order = _proc_info.get("order", "")
        _flo = _proc_info.get("f_lo")
        _fhi = _proc_info.get("f_hi")
        _filt_str = f"{_filt} order {_order}"
        if _flo and _fhi:
            _filt_str += f" ({_flo}–{_fhi} Hz)"
        elif _flo:
            _filt_str += f" @ {_flo} Hz"
        _label_parts.append(_filt_str)
    _source_options.append("Time History (" + (", ".join(_label_parts) if _label_parts else "trimmed") + ")")

_use_processed = False
if _has_processed:
    _src = st.radio("Data source", _source_options, horizontal=True)
    _use_processed = _src != "Raw (full dataset)"
else:
    st.caption("Data source: Raw — visit Time History page to apply trim/filter.")

df = _processed_df if _use_processed else st.session_state["df"]
all_channels = [c for c in df.columns if c != "time"]
sample_rate: float = st.session_state.get("sample_rate", 1.0)

# ── Controls ─────────────────────────────────────────────────────────────────
st.markdown("---")
c1, c2, c3, c4, c5 = st.columns([4, 2, 2, 1, 2])

with c1:
    default_channels = (
        ([st.session_state.get("input_channel")] if st.session_state.get("input_channel") else [])
        + list(st.session_state.get("output_channels") or [])
    )
    default_channels = [c for c in default_channels if c in all_channels] or all_channels[:1]
    selected_channels = st.multiselect("Channels", options=all_channels, default=default_channels)

with c2:
    window_options = {
        "uniform": "Uniform (no window)",
        "hanning": "Hanning",
        "flattop": "Flat Top",
        "force": "Force",
        "exponential": "Exponential",
    }
    window = st.selectbox(
        "Window",
        options=list(window_options.keys()),
        format_func=lambda k: window_options[k],
        index=0,
    )

with c3:
    display_mode = st.radio("Display", options=["Gain/Phase", "Real/Imaginary"], horizontal=True)

with c4:
    log_y = st.checkbox("Log Y", value=True)

with c5:
    st.write("")
    compute_btn = st.button("Compute & Save FFT", type="primary", use_container_width=True)

# ── Saved FFT indicator ───────────────────────────────────────────────────────
if st.session_state.get("fft_results"):
    saved = st.session_state["fft_results"]
    st.success(
        f"FFT saved — window: **{saved['window']}**, "
        f"channels: {', '.join(saved['channels'])}. "
        "Available for Spectral Analysis."
    )

# ── Compute ───────────────────────────────────────────────────────────────────
if compute_btn:
    if not selected_channels:
        st.warning("Select at least one channel.")
        st.stop()

    _ffts: dict[str, np.ndarray] = {}
    _freqs = None
    for ch in selected_channels:
        signal = df[ch].values.astype(float)
        f, F = compute_fft(signal, sample_rate, window)
        _ffts[ch] = F
        _freqs = f

    st.session_state["fft_results"] = {
        "freqs": _freqs,
        "ffts": _ffts,
        "window": window,
        "channels": selected_channels,
    }

# ── Resolve channels and FFT data for plotting ────────────────────────────────
plot_channels = selected_channels
if not plot_channels and st.session_state.get("fft_results"):
    plot_channels = st.session_state["fft_results"]["channels"]

if plot_channels:
    saved = st.session_state.get("fft_results")
    if saved and set(plot_channels).issubset(set(saved["channels"])) and saved["window"] == window:
        freqs = saved["freqs"]
        ffts = {ch: saved["ffts"][ch] for ch in plot_channels}
    else:
        ffts = {}
        freqs = None
        for ch in plot_channels:
            signal = df[ch].values.astype(float)
            f, F = compute_fft(signal, sample_rate, window)
            ffts[ch] = F
            freqs = f

    # ── Frequency range slider ────────────────────────────────────────────────
    f_min = float(freqs[0])
    f_max = float(freqs[-1])
    f_range = st.slider(
        "Frequency range (Hz)",
        min_value=f_min,
        max_value=f_max,
        value=(f_min, f_max),
        step=round((f_max - f_min) / 1000, 4),
    )

    freq_mask = (freqs >= f_range[0]) & (freqs <= f_range[1])
    f_plot = freqs[freq_mask]

    # ── Build figure: 2 rows per channel (top = gain/real, bottom = phase/imag) ─
    n_ch = len(plot_channels)
    if display_mode == "Gain/Phase":
        top_label, bot_label = "Gain", "Phase (deg)"
    else:
        top_label, bot_label = "Real", "Imaginary"

    subplot_titles = []
    for ch in plot_channels:
        subplot_titles += [f"{ch} — {top_label}", f"{ch} — {bot_label}"]

    fig = make_subplots(
        rows=n_ch * 2,
        cols=1,
        shared_xaxes=True,
        subplot_titles=subplot_titles,
        vertical_spacing=0.05,
    )

    for i, ch in enumerate(plot_channels):
        F = ffts[ch][freq_mask]
        if display_mode == "Gain/Phase":
            y_top = np.abs(F)
            y_bot = np.angle(F, deg=True)
        else:
            y_top = F.real
            y_bot = F.imag

        row_top = 2 * i + 1
        row_bot = 2 * i + 2

        fig.add_trace(
            go.Scatter(x=f_plot, y=y_top, mode="lines", name=ch, showlegend=False),
            row=row_top, col=1,
        )
        fig.add_trace(
            go.Scatter(x=f_plot, y=y_bot, mode="lines", name=ch, showlegend=False),
            row=row_bot, col=1,
        )

        fig.update_yaxes(
            title_text=top_label,
            type="log" if log_y and display_mode == "Gain/Phase" else "linear",
            row=row_top, col=1,
        )
        fig.update_yaxes(title_text=bot_label, row=row_bot, col=1)

    fig.update_xaxes(title_text="Frequency (Hz)", row=n_ch * 2, col=1)
    fig.update_layout(
        height=220 * n_ch * 2,
        showlegend=False,
        margin=dict(t=40, b=40),
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Select channels and click **Compute & Save FFT** to generate the plot.")
