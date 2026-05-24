import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from scipy.signal import get_window

from core.spectral import (
    WINDOW_SCIPY_NAMES,
    compute_spectral_quantities,
    compute_welch_quantities,
)

st.set_page_config(page_title="smodal · Spectral Analysis", layout="wide")

from core import brand

brand.page_header()

st.title("Spectral Analysis")

# ── Guard ─────────────────────────────────────────────────────────────────────
if st.session_state.get("df") is None:
    st.warning("No data loaded. Go to **Page 1 — Time History** and upload a data file.")
    st.stop()

fft_res = st.session_state.get("fft_results")
input_channel: str = st.session_state.get("input_channel", "")
output_channels: list = st.session_state.get("output_channels", [])
sample_rate: float = st.session_state.get("sample_rate", 1.0)
_processed = st.session_state.get("processed_df")
src_df = _processed if _processed is not None else st.session_state.get("df")

# ── Layout ────────────────────────────────────────────────────────────────────
ctrl_col, chart_col = st.columns([1, 3])

# ── Controls ──────────────────────────────────────────────────────────────────
selected_outputs: list = []
welch_params: dict = {}

with ctrl_col:
    method = st.radio(
        "Method", ["Single FFT", "Welch"], horizontal=True, key="sa_method"
    )

    if method == "Single FFT":
        if fft_res is None:
            st.warning(
                "No FFT results available. Go to the **FFT** page, select channels, "
                "and click **Compute & Save FFT**."
            )
        elif fft_res.get("method") != "single_fft":
            st.warning(
                "The saved FFT result is a **Welch** analysis and cannot be used as the "
                "input for a Single FFT spectral analysis. Return to the **FFT** page, "
                "switch the method to **Single FFT**, recompute, and save."
            )
        else:
            fft_channels: list = fft_res.get("channels", [])
            if input_channel not in fft_channels:
                st.warning(
                    f"Input channel **{input_channel}** was not included in the saved FFT results. "
                    "Return to the FFT page and recompute with the input channel selected."
                )
            else:
                available_outputs = [ch for ch in output_channels if ch in fft_channels]
                if not available_outputs:
                    st.warning(
                        "No output channels found in the saved FFT results. "
                        "Return to the FFT page and recompute with at least one output channel selected."
                    )
                else:
                    selected_outputs = st.multiselect(
                        "Output channels",
                        options=available_outputs,
                        default=available_outputs,
                        key="sa_outputs",
                    )

    else:  # Welch
        if src_df is None:
            st.warning("No signal data available.")
        elif input_channel not in src_df.columns:
            st.warning(f"Input channel **{input_channel}** not found in data.")
        else:
            available_outputs_w = [ch for ch in output_channels if ch in src_df.columns]
            if not available_outputs_w:
                st.warning("No output channels found in the data.")
            else:
                selected_outputs = st.multiselect(
                    "Output channels",
                    options=available_outputs_w,
                    default=available_outputs_w,
                    key="sa_outputs_w",
                )
                n_segs = st.select_slider(
                    "Segments", options=[4, 8, 16, 32, 64], value=8, key="sa_n_segs"
                )
                overlap_pct = st.select_slider(
                    "Overlap (%)", options=[0, 25, 50, 75], value=50, key="sa_overlap"
                )
                welch_win = st.selectbox(
                    "Window", ["hann", "flattop", "boxcar"], key="sa_welch_win"
                )
                nperseg = max(16, len(src_df) // n_segs)
                noverlap = int(nperseg * overlap_pct / 100)
                st.caption(
                    f"Δf ≈ {sample_rate / nperseg:.3f} Hz  "
                    f"({nperseg} samples/segment)"
                )
                welch_params = {
                    "n_segs": n_segs,
                    "overlap_pct": overlap_pct,
                    "window": welch_win,
                    "nperseg": nperseg,
                    "noverlap": noverlap,
                }

    compute_btn = st.button(
        "Compute", type="primary", use_container_width=True, key="sa_compute"
    )

    cached = st.session_state.get("spectral_results")
    if cached:
        st.caption(
            f"Showing results for: {', '.join(cached.get('params', {}).get('output_channels', []))}"
        )

# ── Computation ───────────────────────────────────────────────────────────────
if compute_btn:
    if not selected_outputs:
        st.warning("Select at least one output channel.")
        st.stop()

    if method == "Single FFT":
        new_params = {
            "method": "Single FFT",
            "input_channel": input_channel,
            "output_channels": list(selected_outputs),
        }
        cached = st.session_state.get("spectral_results")
        if not (cached and cached.get("params") == new_params):
            Sx = fft_res["ffts"][input_channel]
            ch_results = {}
            for ch in selected_outputs:
                Sy = fft_res["ffts"][ch]
                ch_results[ch] = compute_spectral_quantities(Sx, Sy)

            st.session_state["spectral_results"] = {
                "params": new_params,
                "freqs": fft_res["freqs"],
                "input_channel": input_channel,
                "channels": ch_results,
            }
        st.rerun()

    else:  # Welch
        new_params = {
            "method": "Welch",
            "input_channel": input_channel,
            "output_channels": list(selected_outputs),
            **welch_params,
        }
        cached = st.session_state.get("spectral_results")
        if not (cached and cached.get("params") == new_params):
            x = src_df[input_channel].values.astype(float)
            ch_results = {}
            welch_freqs = None
            for ch in selected_outputs:
                y = src_df[ch].values.astype(float)
                result = compute_welch_quantities(
                    x, y, sample_rate,
                    welch_params["nperseg"],
                    welch_params["noverlap"],
                    welch_params["window"],
                )
                welch_freqs = result.pop("freqs")
                ch_results[ch] = result

            st.session_state["spectral_results"] = {
                "params": new_params,
                "freqs": welch_freqs,
                "input_channel": input_channel,
                "channels": ch_results,
            }
        st.rerun()

# ── Chart area ────────────────────────────────────────────────────────────────
with chart_col:
    res = st.session_state.get("spectral_results")

    if res is None:
        st.info("Select output channels and click **Compute** to run the analysis.")
        st.stop()

    freqs: np.ndarray = res["freqs"]
    ch_data: dict = res["channels"]
    plot_chs = [ch for ch in res["params"]["output_channels"] if ch in ch_data]

    if not plot_chs:
        st.warning("No channel data found. Click Compute again.")
        st.stop()

    f_nyq = float(freqs[-1])
    f_step = round(f_nyq / 1000, 4) or 0.001

    f_min, f_max = st.slider(
        "Frequency range (Hz)",
        min_value=0.0,
        max_value=f_nyq,
        value=(0.0, f_nyq),
        step=f_step,
        key="sa_frange",
    )
    mask = (freqs >= f_min) & (freqs <= f_max)
    f_plot = freqs[mask]

    tab_ap, tab_psd, tab_cp, tab_frf, tab_coh = st.tabs(
        ["Auto-Power", "PSD", "Cross-Power", "FRF", "Coherence"]
    )

    eps = np.finfo(float).tiny
    n_out = len(plot_chs)

    def _color(i: int) -> str:
        return f"hsl({(i * 47) % 360}, 65%, 50%)"

    # ── Tab 1: Auto-Power ────────────────────────────────────────────────────
    with tab_ap:
        n_rows = 1 + n_out
        titles = [f"Gxx — {input_channel}"] + [f"Gyy — {ch}" for ch in plot_chs]
        fig = make_subplots(
            rows=n_rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=titles,
        )

        Gxx = ch_data[plot_chs[0]]["Gxx"]
        Gxx_dB = 10 * np.log10(np.maximum(Gxx[mask], eps))
        fig.add_trace(
            go.Scatter(x=f_plot, y=Gxx_dB, mode="lines",
                       name=input_channel,
                       line=dict(color="#1f77b4", width=1.5)),
            row=1, col=1,
        )
        fig.update_yaxes(title_text="PSD (dB)", row=1, col=1)

        for i, ch in enumerate(plot_chs, start=1):
            Gyy_dB = 10 * np.log10(np.maximum(ch_data[ch]["Gyy"][mask], eps))
            fig.add_trace(
                go.Scatter(x=f_plot, y=Gyy_dB, mode="lines",
                           name=ch, line=dict(color=_color(i), width=1.5)),
                row=i + 1, col=1,
            )
            fig.update_yaxes(title_text="PSD (dB)", row=i + 1, col=1)

        fig.update_xaxes(title_text="Frequency (Hz)", row=n_rows, col=1)
        fig.update_layout(
            height=220 * n_rows,
            legend=dict(orientation="h", y=-0.06),
            margin=dict(t=40, b=60, l=60, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Tab 2: PSD ───────────────────────────────────────────────────────────
    with tab_psd:
        psd_log = st.checkbox("dB (10 log₁₀)", value=False, key="sa_psd_log")

        result_method = res["params"].get("method", "Single FFT")
        is_welch = result_method == "Welch"

        # Δf and normalisation factor
        N = fft_res.get("n_samples", 2 * (len(freqs) - 1))
        if is_welch:
            nperseg_val = res["params"].get("nperseg", N)
            delta_f = sample_rate / nperseg_val
            Sxx = ch_data[plot_chs[0]]["Gxx"]
            Syy_dict = {ch: ch_data[ch]["Gyy"] for ch in plot_chs}
        else:
            delta_f = sample_rate / N
            # Window power correction: W₂ = Σ w[n]² (boxcar → W₂=N, Hann → W₂≈0.375·N).
            # Gxx already includes ×4 from one-sided amplitude correction in compute_fft,
            # so norm = 2·fs·W₂ gives the correct one-sided PSD.
            win_name = fft_res.get("window", "uniform") if fft_res else "uniform"
            scipy_win = WINDOW_SCIPY_NAMES.get(win_name, "boxcar")
            if scipy_win == "exponential":
                _win_arr = get_window(("exponential", None, 1.0 / 8.686), N)
            else:
                _win_arr = get_window(scipy_win, N)
            W2 = float(np.sum(_win_arr ** 2))
            norm = 2 * sample_rate * W2
            Sxx = ch_data[plot_chs[0]]["Gxx"] / norm
            Syy_dict = {ch: ch_data[ch]["Gyy"] / norm for ch in plot_chs}

        y_label = "PSD (dB)" if psd_log else "PSD (unit²/Hz)"
        df_str = f"  Δf = {delta_f:.4f} Hz"

        n_rows_psd = 1 + n_out
        psd_titles = [f"Sxx — {input_channel}{df_str}"] + [
            f"Syy — {ch}{df_str}" for ch in plot_chs
        ]
        fig = make_subplots(
            rows=n_rows_psd, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=psd_titles,
        )

        def _psd_y(arr: np.ndarray) -> np.ndarray:
            return 10 * np.log10(np.maximum(arr, eps)) if psd_log else arr

        fig.add_trace(
            go.Scatter(x=f_plot, y=_psd_y(Sxx[mask]), mode="lines",
                       name=input_channel,
                       line=dict(color="#1f77b4", width=1.5)),
            row=1, col=1,
        )
        fig.update_yaxes(title_text=y_label, row=1, col=1)

        for i, ch in enumerate(plot_chs, start=1):
            fig.add_trace(
                go.Scatter(x=f_plot, y=_psd_y(Syy_dict[ch][mask]), mode="lines",
                           name=ch, line=dict(color=_color(i), width=1.5)),
                row=i + 1, col=1,
            )
            fig.update_yaxes(title_text=y_label, row=i + 1, col=1)

        fig.update_xaxes(title_text="Frequency (Hz)", row=n_rows_psd, col=1)
        fig.update_layout(
            height=220 * n_rows_psd,
            legend=dict(orientation="h", y=-0.06),
            margin=dict(t=40, b=60, l=60, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Tab 3: Cross-Power ───────────────────────────────────────────────────
    with tab_cp:
        n_rows = 2 * n_out
        titles = []
        for ch in plot_chs:
            titles += [f"|Gxy| — {ch} (dB)", f"∠Gxy — {ch} (°)"]

        fig = make_subplots(
            rows=n_rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=titles,
        )

        for i, ch in enumerate(plot_chs, start=1):
            Gxy = ch_data[ch]["Gxy"][mask]  # Gxy = Sy*conj(Sx); phase = ∠H
            color = _color(i)
            row_mag = 2 * i - 1
            row_ph = 2 * i

            Gxy_dB = 10 * np.log10(np.maximum(np.abs(Gxy), eps))
            Gxy_ph = np.degrees(np.angle(Gxy))

            fig.add_trace(
                go.Scatter(x=f_plot, y=Gxy_dB, mode="lines",
                           name=ch, line=dict(color=color, width=1.5)),
                row=row_mag, col=1,
            )
            fig.add_trace(
                go.Scatter(x=f_plot, y=Gxy_ph, mode="lines",
                           name=ch, line=dict(color=color, width=1.5),
                           showlegend=False),
                row=row_ph, col=1,
            )
            fig.update_yaxes(title_text="|Gxy| (dB)", row=row_mag, col=1)
            fig.update_yaxes(title_text="Phase (°)", row=row_ph, col=1)

        fig.update_xaxes(title_text="Frequency (Hz)", row=n_rows, col=1)
        fig.update_layout(
            height=220 * n_rows,
            legend=dict(orientation="h", y=-0.06),
            margin=dict(t=40, b=60, l=60, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Tab 4: FRF ───────────────────────────────────────────────────────────
    with tab_frf:
        estimator = st.radio(
            "FRF estimator",
            options=["H1", "H2", "Hv", "All"],
            horizontal=True,
            key="sa_estimator",
        )

        n_rows = 2 * n_out
        titles = []
        for ch in plot_chs:
            titles += [f"|H| — {ch} (dB)", f"∠H — {ch} (°)"]

        fig = make_subplots(
            rows=n_rows, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=titles,
        )

        _est_styles = {
            "H1": dict(dash="solid"),
            "H2": dict(dash="dash"),
            "Hv": dict(dash="dot"),
        }
        show_ests = ["H1", "H2", "Hv"] if estimator == "All" else [estimator]

        for i, ch in enumerate(plot_chs, start=1):
            color = _color(i)
            row_mag = 2 * i - 1
            row_ph = 2 * i

            for est in show_ests:
                H = ch_data[ch][est][mask]
                H_dB = 20 * np.log10(np.maximum(np.abs(H), eps))
                H_ph = np.degrees(np.angle(H))
                leg_name = f"{ch} — {est}" if estimator == "All" else ch

                fig.add_trace(
                    go.Scatter(
                        x=f_plot, y=H_dB, mode="lines",
                        name=leg_name,
                        legendgroup=est if estimator == "All" else ch,
                        line=dict(color=color, width=1.5, **_est_styles[est]),
                        showlegend=(i == 1),
                    ),
                    row=row_mag, col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=f_plot, y=H_ph, mode="lines",
                        name=leg_name,
                        legendgroup=est if estimator == "All" else ch,
                        line=dict(color=color, width=1.5, **_est_styles[est]),
                        showlegend=False,
                    ),
                    row=row_ph, col=1,
                )

            fig.update_yaxes(title_text="|H| (dB)", row=row_mag, col=1)
            fig.update_yaxes(title_text="Phase (°)", row=row_ph, col=1)

        fig.update_xaxes(title_text="Frequency (Hz)", row=n_rows, col=1)
        fig.update_layout(
            height=220 * n_rows,
            legend=dict(orientation="h", y=-0.06),
            margin=dict(t=40, b=60, l=60, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Tab 5: Coherence ─────────────────────────────────────────────────────
    with tab_coh:
        titles = [f"γ² — {ch}" for ch in plot_chs]
        fig = make_subplots(
            rows=n_out, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=titles,
        )

        for i, ch in enumerate(plot_chs, start=1):
            gamma2 = ch_data[ch]["gamma2"][mask]
            fig.add_trace(
                go.Scatter(x=f_plot, y=gamma2, mode="lines",
                           name=ch, line=dict(color=_color(i), width=1.5),
                           showlegend=(n_out > 1)),
                row=i, col=1,
            )
            fig.add_hline(
                y=0.85,
                line=dict(color="gray", dash="dash", width=1),
                row=i, col=1,
            )
            fig.update_yaxes(title_text="γ²", range=[0, 1.05], row=i, col=1)

        fig.update_xaxes(title_text="Frequency (Hz)", row=n_out, col=1)
        fig.update_layout(
            height=220 * n_out,
            legend=dict(orientation="h", y=-0.06),
            margin=dict(t=40, b=60, l=60, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        result_method = res["params"].get("method", "Single FFT")
        if result_method == "Welch":
            st.caption(
                "Coherence is computed from Welch-averaged cross- and auto-power estimates. "
                "Values below 0.85 (dashed line) indicate noise or nonlinearity."
            )
        else:
            st.caption(
                "Coherence = 1.0 is expected for single-realization FFTs. "
                "Frequency-averaged coherence requires multiple FFT segments."
            )
