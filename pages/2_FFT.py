import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from scipy.signal import welch as scipy_welch

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

# ── Method ────────────────────────────────────────────────────────────────────
st.markdown("---")
method = st.radio("Method", ["Single FFT", "Welch"], horizontal=True)

# ── Controls ─────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns([4, 2, 2, 1, 2])

with c1:
    default_channels = (
        ([st.session_state.get("input_channel")] if st.session_state.get("input_channel") else [])
        + list(st.session_state.get("output_channels") or [])
    )
    default_channels = [c for c in default_channels if c in all_channels] or all_channels[:1]
    selected_channels = st.multiselect("Channels", options=all_channels, default=default_channels)

# defaults to avoid NameError in branches not taken
window = "uniform"
display_mode = "Gain/Phase"
log_y = True
n_segs = 16
overlap_pct = 50
welch_window = "hann"
nperseg = noverlap = 0

with c2:
    if method == "Single FFT":
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
    else:
        n_segs = st.selectbox("Segments", options=[4, 8, 16, 32, 64], index=2)

with c3:
    if method == "Single FFT":
        display_mode = st.radio("Display", options=["Gain/Phase", "Real/Imaginary"], horizontal=True)
    else:
        overlap_pct = st.selectbox(
            "Overlap",
            options=[0, 25, 50, 75],
            format_func=lambda k: f"{k}%",
            index=2,
        )

with c4:
    if method == "Single FFT":
        log_y = st.checkbox("Log Y", value=True)
    else:
        welch_window = st.selectbox(
            "Window",
            options=["hann", "flattop", "boxcar"],
            format_func=lambda k: {"hann": "Hann", "flattop": "Flat Top", "boxcar": "Uniform"}[k],
            index=0,
        )

with c5:
    if method == "Welch":
        n_samples = len(df)
        nperseg = max(16, n_samples // n_segs)
        noverlap = int(nperseg * overlap_pct / 100)
        df_val = sample_rate / nperseg
        log_y = st.checkbox("Log Y", value=True)
        st.caption(f"Δf = {df_val:.3g} Hz")
    else:
        st.write("")
    compute_btn = st.button("Compute & Save FFT", type="primary", use_container_width=True)

# ── Saved FFT indicator ───────────────────────────────────────────────────────
if st.session_state.get("fft_results"):
    saved = st.session_state["fft_results"]
    saved_method = saved.get("method", "single_fft")
    if saved_method == "welch":
        st.success(
            f"Welch PSD saved — window: **{saved['window']}**, "
            f"nperseg: {saved['nperseg']}, "
            f"channels: {', '.join(saved['channels'])}. "
            "Available for Spectral Analysis."
        )
    else:
        st.success(
            f"FFT saved — window: **{saved['window']}**, "
            f"channels: {', '.join(saved['channels'])}. "
            "Available for Spectral Analysis."
        )

# ── Compute & Save ────────────────────────────────────────────────────────────
if compute_btn:
    if not selected_channels:
        st.warning("Select at least one channel.")
        st.stop()

    if method == "Single FFT":
        _ffts: dict[str, np.ndarray] = {}
        _freqs = None
        for ch in selected_channels:
            signal = df[ch].values.astype(float)
            f, F = compute_fft(signal, sample_rate, window)
            _ffts[ch] = F
            _freqs = f

        st.session_state["fft_results"] = {
            "method": "single_fft",
            "freqs": _freqs,
            "ffts": _ffts,
            "window": window,
            "channels": selected_channels,
        }
    else:
        _psds: dict[str, np.ndarray] = {}
        _freqs = None
        for ch in selected_channels:
            signal = df[ch].values.astype(float)
            f, Pxx = scipy_welch(
                signal, fs=sample_rate, window=welch_window,
                nperseg=nperseg, noverlap=noverlap,
            )
            _psds[ch] = Pxx
            _freqs = f

        st.session_state["fft_results"] = {
            "method": "welch",
            "freqs": _freqs,
            "psds": _psds,
            "window": welch_window,
            "channels": selected_channels,
            "nperseg": nperseg,
            "noverlap": noverlap,
        }

# ── Resolve channels and data for plotting ────────────────────────────────────
plot_channels = selected_channels
if not plot_channels and st.session_state.get("fft_results"):
    plot_channels = st.session_state["fft_results"]["channels"]

if not plot_channels:
    st.info("Select channels and click **Compute & Save FFT** to generate the plot.")
    st.stop()

saved = st.session_state.get("fft_results")

if method == "Single FFT":
    # ── Resolve FFT data ──────────────────────────────────────────────────────
    if (
        saved
        and saved.get("method", "single_fft") == "single_fft"
        and set(plot_channels).issubset(set(saved["channels"]))
        and saved["window"] == window
    ):
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
        min_value=f_min, max_value=f_max,
        value=(f_min, f_max),
        step=round((f_max - f_min) / 1000, 4),
    )
    freq_mask = (freqs >= f_range[0]) & (freqs <= f_range[1])
    f_plot = freqs[freq_mask]

    # ── Build figure ──────────────────────────────────────────────────────────
    n_ch = len(plot_channels)
    if display_mode == "Gain/Phase":
        top_label, bot_label = "Gain", "Phase (deg)"
    else:
        top_label, bot_label = "Real", "Imaginary"

    subplot_titles = []
    for ch in plot_channels:
        subplot_titles += [f"{ch} — {top_label}", f"{ch} — {bot_label}"]

    fig = make_subplots(
        rows=n_ch * 2, cols=1,
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

else:  # Welch
    # ── Resolve PSD data ──────────────────────────────────────────────────────
    if (
        saved
        and saved.get("method") == "welch"
        and set(plot_channels).issubset(set(saved["channels"]))
        and saved["window"] == welch_window
        and saved.get("nperseg") == nperseg
        and saved.get("noverlap") == noverlap
    ):
        freqs = saved["freqs"]
        psds = {ch: saved["psds"][ch] for ch in plot_channels}
    else:
        psds = {}
        freqs = None
        for ch in plot_channels:
            signal = df[ch].values.astype(float)
            f, Pxx = scipy_welch(
                signal, fs=sample_rate, window=welch_window,
                nperseg=nperseg, noverlap=noverlap,
            )
            psds[ch] = Pxx
            freqs = f

    # ── Frequency range slider ────────────────────────────────────────────────
    f_min = float(freqs[0])
    f_max = float(freqs[-1])
    f_range = st.slider(
        "Frequency range (Hz)",
        min_value=f_min, max_value=f_max,
        value=(f_min, f_max),
        step=round((f_max - f_min) / 1000, 4),
    )
    freq_mask = (freqs >= f_range[0]) & (freqs <= f_range[1])
    f_plot = freqs[freq_mask]

    # ── Build figure: one row per channel ─────────────────────────────────────
    n_ch = len(plot_channels)
    subplot_titles = [f"{ch} — PSD" for ch in plot_channels]
    fig = make_subplots(
        rows=n_ch, cols=1,
        shared_xaxes=True,
        subplot_titles=subplot_titles,
        vertical_spacing=0.08,
    )

    for i, ch in enumerate(plot_channels):
        y = psds[ch][freq_mask]
        fig.add_trace(
            go.Scatter(x=f_plot, y=y, mode="lines", name=ch, showlegend=False),
            row=i + 1, col=1,
        )
        fig.update_yaxes(
            title_text="PSD",
            type="log" if log_y else "linear",
            row=i + 1, col=1,
        )

    fig.update_xaxes(title_text="Frequency (Hz)", row=n_ch, col=1)
    fig.update_layout(
        height=300 * n_ch,
        showlegend=False,
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
