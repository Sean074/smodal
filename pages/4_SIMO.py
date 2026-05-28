import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core.data_loader import compute_sample_rate, load_csv
from core.ema_pipeline import extract_modes, nmse_quality_label
from core.plots import fft_subplot, frf_subplot
from core.preprocess import trim_and_filter
from core.spectral import band_coherence_stats, compute_fft, compute_spectral_quantities, compute_welch_quantities
from core.sysid import (
    build_stability_table,
    cmif_peak_estimates,
    deduplicate_stable_poles,
)
from core.uff_writer import write_uff58_shapes

st.set_page_config(page_title="smodal · SIMO", layout="wide")

from core import brand

brand.page_header()

st.title("SIMO — System Identification (EMA)")

eps = np.finfo(float).tiny

# ── Section A: File loading ────────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload time-history CSV", type="csv", key="simo_upload")

if uploaded_file is not None and st.session_state.get("simo_file_name") != uploaded_file.name:
    df_raw, err = load_csv(uploaded_file)
    if err:
        st.error(err)
    else:
        st.session_state["simo_df"] = df_raw
        st.session_state["simo_sample_rate"] = float(compute_sample_rate(df_raw["time"].values))
        st.session_state["simo_file_name"] = uploaded_file.name
        for k in ["si_H_mat", "si_freqs", "si_cmif", "si_stability_table", "modal_results",
                  "si_spectral_channels", "si_spectral_freqs", "si_frf_method_used"]:
            st.session_state.pop(k, None)

simo_df = st.session_state.get("simo_df")
if simo_df is None:
    st.info("Upload a time-history CSV file to begin.")
    st.stop()

fs: float = st.session_state.get("simo_sample_rate", 1.0)
data_cols = [c for c in simo_df.columns if c != "time"]

# ── Channel assignment ─────────────────────────────────────────────────────────
st.divider()
ch_col_in, ch_col_out = st.columns([1, 2])
with ch_col_in:
    input_channel = st.selectbox("Input channel", options=data_cols, key="simo_input_ch")
with ch_col_out:
    avail_outputs = [c for c in data_cols if c != input_channel]
    sel_outputs_default = st.session_state.get("simo_output_chs", avail_outputs)
    sel_outputs = st.multiselect("Output channels", options=avail_outputs, default=avail_outputs, key="simo_output_chs")

if not sel_outputs:
    st.warning("Select at least one output channel.")
    st.stop()

# ── Section B: Pre-processing expander ────────────────────────────────────────
with st.expander("Pre-processing (optional)"):
    t_min_data = float(simo_df["time"].min())
    t_max_data = float(simo_df["time"].max())
    t_step = max(round((t_max_data - t_min_data) / 1000, 6), 1e-6)
    t_min, t_max = st.slider(
        "Time range (s)",
        min_value=t_min_data,
        max_value=t_max_data,
        value=(t_min_data, t_max_data),
        step=t_step,
        key="simo_trange",
    )

    filter_type = st.radio(
        "Filter type",
        ["None", "Lowpass", "Highpass", "Bandpass", "Bandstop"],
        horizontal=True,
        key="simo_filter_type",
    )

    filter_order = 4
    cutoff_params = None

    if filter_type != "None":
        fc1, fc2 = st.columns(2)
        with fc1:
            filter_order = st.slider("Filter order", min_value=1, max_value=8, value=4, key="simo_filter_order")
        with fc2:
            if filter_type in ("Lowpass", "Highpass"):
                cutoff_params = float(
                    st.number_input(
                        "Cutoff (Hz)",
                        min_value=0.1,
                        max_value=float(fs / 2 * 0.99),
                        value=min(10.0, float(fs / 4)),
                        step=0.5,
                        key="simo_cutoff",
                    )
                )
            else:
                bp1, bp2 = st.columns(2)
                with bp1:
                    low_cut = st.number_input(
                        "Low cutoff (Hz)",
                        min_value=0.1,
                        max_value=float(fs / 2 * 0.49),
                        value=min(5.0, float(fs / 8)),
                        step=0.5,
                        key="simo_cutoff_low",
                    )
                with bp2:
                    high_cut = st.number_input(
                        "High cutoff (Hz)",
                        min_value=0.1,
                        max_value=float(fs / 2 * 0.99),
                        value=min(50.0, float(fs / 4)),
                        step=0.5,
                        key="simo_cutoff_high",
                    )
                cutoff_params = [float(low_cut), float(high_cut)]

    n_samples = max(4, int(round((t_max - t_min) * fs)) + 1)
    filt_label = filter_type if filter_type != "None" else "no filter"
    st.caption(f"Time window: {t_min:.3f}–{t_max:.3f} s  ·  ≈{n_samples} samples  ·  {filt_label}")

    if st.checkbox("Show time history preview", value=True, key="simo_show_th"):
        preview_cols = st.multiselect(
            "Channels to preview",
            options=data_cols,
            default=data_cols[: min(4, len(data_cols))],
            key="simo_preview_chs",
        )
        if preview_cols:
            mask = (simo_df["time"] >= t_min) & (simo_df["time"] <= t_max)
            df_trim = simo_df[mask]

            filter_active = (
                filter_type != "None"
                and cutoff_params is not None
                and not (isinstance(cutoff_params, list) and cutoff_params[0] >= cutoff_params[1])
            )
            if filter_active:
                df_filt = trim_and_filter(simo_df, t_min, t_max, filter_type, filter_order, cutoff_params, fs)

            n_rows_prev = len(preview_cols)
            fig_prev = make_subplots(
                rows=n_rows_prev,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                subplot_titles=preview_cols,
            )

            for pi, ch in enumerate(preview_cols):
                if ch not in df_trim.columns:
                    continue
                row = pi + 1
                fig_prev.add_trace(
                    go.Scatter(
                        x=df_trim["time"],
                        y=df_trim[ch],
                        mode="lines",
                        name="Raw",
                        line=dict(color="#1f77b4", width=1),
                        showlegend=(pi == 0),
                    ),
                    row=row,
                    col=1,
                )
                if filter_active:
                    fig_prev.add_trace(
                        go.Scatter(
                            x=df_filt["time"],
                            y=df_filt[ch],
                            mode="lines",
                            name="Filtered",
                            line=dict(color="#ff7f0e", width=1.5, dash="dash"),
                            showlegend=(pi == 0),
                        ),
                        row=row,
                        col=1,
                    )
                fig_prev.update_yaxes(title_text=ch, row=row, col=1)
                if row == n_rows_prev:
                    fig_prev.update_xaxes(title_text="Time (s)", row=row, col=1)

            fig_prev.update_layout(
                height=max(250, 200 * n_rows_prev),
                margin=dict(t=30, b=50, l=70, r=20),
                legend=dict(orientation="h", y=-0.08),
            )
            st.plotly_chart(fig_prev, use_container_width=True)


def _preview_proc():
    _ok = not (isinstance(cutoff_params, list) and len(cutoff_params) == 2 and cutoff_params[0] >= cutoff_params[1])
    return trim_and_filter(
        simo_df,
        t_min,
        t_max,
        filter_type if _ok else "None",
        filter_order,
        cutoff_params if _ok else None,
        fs,
    )


# ── Section C: FFT preview expander ───────────────────────────────────────────
with st.expander("FFT preview (optional)"):
    fft_fmax = st.slider(
        "Max frequency (Hz)",
        min_value=0.0,
        max_value=float(fs / 2),
        value=float(fs / 2),
        key="simo_fft_fmax",
    )
    st.plotly_chart(
        fft_subplot(_preview_proc(), [input_channel] + sel_outputs, fs, fft_fmax),
        use_container_width=True,
    )

# ── Section D: FRF preview expander ───────────────────────────────────────────
with st.expander("FRF preview (optional)"):
    frf_fmax = st.slider(
        "Max frequency (Hz)",
        min_value=0.0,
        max_value=float(fs / 2),
        value=float(fs / 2),
        key="simo_frf_fmax",
    )
    st.plotly_chart(
        frf_subplot(_preview_proc(), input_channel, sel_outputs, fs, frf_fmax),
        use_container_width=True,
    )

# ── Layout ────────────────────────────────────────────────────────────────────
ctrl_col, chart_col = st.columns([1, 3])

# ── Controls ──────────────────────────────────────────────────────────────────
with ctrl_col:
    st.subheader("Step 1 — Stability Diagram")

    frf_method = st.radio("FRF method", ["Welch", "Single FFT"], horizontal=True, key="si_frf_method")

    if frf_method == "Welch":
        n_seg = st.number_input("Segments", min_value=2, max_value=50, value=8, step=1, key="si_segments")
        ovlp_pct = st.slider("Overlap (%)", min_value=0, max_value=90, value=50, step=5, key="si_overlap")
        welch_win = st.selectbox("Window", ["hann", "flattop", "boxcar"], key="si_welch_win")
        nperseg_preview = max(4, n_samples // n_seg)
        df_hz = fs / nperseg_preview
        st.caption(f"Δf ≈ {df_hz:.3f} Hz  |  {nperseg_preview} samples/segment")

    frf_est = st.radio("FRF estimator", ["H1", "H2", "Hv"], horizontal=True, key="si_frf_est")

    si_freqs_cached = st.session_state.get("si_freqs")
    f_nyq = float(si_freqs_cached[-1]) if si_freqs_cached is not None else fs / 2.0
    f_step = round(f_nyq / 500, 4) or 0.01
    f_min, f_max = st.slider(
        "Frequency range (Hz)",
        min_value=0.0,
        max_value=f_nyq,
        value=(0.0, f_nyq),
        step=f_step,
        key="si_frange",
    )

    # ── Coherence quality gate ─────────────────────────────────────────────────
    _si_spec_chs_gate = st.session_state.get("si_spectral_channels")
    _si_spec_freqs_gate = st.session_state.get("si_spectral_freqs")
    _si_method_gate = st.session_state.get("si_frf_method_used")
    _coh_red_intervals: list = []
    _coh_yellow_intervals: list = []
    if _si_spec_chs_gate is not None and _si_spec_freqs_gate is not None:
        if _si_method_gate == "Single FFT":
            st.caption("Coherence shading suppressed — Single FFT coherence is 1.0 everywhere.")
        else:
            _g2_arrays = [cd["gamma2"] for cd in _si_spec_chs_gate.values()]
            _min_len = min(len(g) for g in _g2_arrays)
            _g2_min = np.min(np.stack([g[:_min_len] for g in _g2_arrays], axis=0), axis=0)
            _freqs_aligned = _si_spec_freqs_gate[:_min_len]
            _stats_70 = band_coherence_stats(_g2_min, _freqs_aligned, f_min, f_max, threshold=0.7)
            _stats_85 = band_coherence_stats(_g2_min, _freqs_aligned, f_min, f_max, threshold=0.85)
            _coh_red_intervals = _stats_70["low_bands"]
            _coh_yellow_intervals = _stats_85["low_bands"]
            if not _stats_70["passes"]:
                st.warning(
                    f"Low coherence (γ² < 0.7) covers {_stats_70['pct_low']:.0%} of the analysis band "
                    f"(mean γ² = {_stats_70['mean_coh']:.2f}). "
                    "Modes extracted here may not reflect physical resonances."
                )
            elif _stats_85["pct_low"] > 0:
                st.info(
                    f"Moderate coherence (γ² < 0.85) covers {_stats_85['pct_low']:.0%} of the analysis band. "
                    "Interpret results with care."
                )

    max_order = st.slider("Max model order", min_value=4, max_value=100, value=40, step=2, key="si_max_order")

    if si_freqs_cached is not None:
        _n_band = int(np.sum((si_freqs_cached >= f_min) & (si_freqs_cached <= f_max)))
        if _n_band > 0 and max_order > _n_band // 4:
            st.warning(
                f"Max model order ({max_order}) exceeds ¼ of the frequency lines in the "
                f"analysis band ({_n_band} lines → recommended ≤ {_n_band // 4}). "
                "Overdetermined models produce spurious computational poles."
            )

    with st.expander("Stability thresholds"):
        df_thr = st.number_input("Δf threshold (%)", value=1.0, step=0.5, min_value=0.1, key="si_df_thr") / 100.0
        dd_thr = st.number_input("Δξ threshold (%)", value=5.0, step=1.0, min_value=0.1, key="si_dd_thr") / 100.0
        mac_thr = st.slider("MAC threshold", min_value=0.5, max_value=1.0, value=0.95, step=0.01, key="si_mac_thr")

    build_btn = st.button("Build Stability Diagram", type="primary", use_container_width=True, key="si_build")

    st.divider()
    st.subheader("Step 2 — Mode Specification")

    stab_results = st.session_state.get("si_stability_table")
    cmif_cache = st.session_state.get("si_cmif")
    freqs_cache = st.session_state.get("si_freqs")
    cmif_for_peaks = cmif_cache[:, 0] if cmif_cache is not None else None

    deduped = deduplicate_stable_poles(stab_results) if stab_results is not None else []
    auto_n = max(1, len(deduped))

    n_modes = st.number_input("Number of modes", min_value=1, max_value=20, value=auto_n, step=1, key="si_n_modes")

    if len(deduped) >= n_modes:
        init_rows = deduped[:n_modes]
    elif len(deduped) > 0:
        if cmif_for_peaks is not None:
            extra = cmif_peak_estimates(cmif_for_peaks, freqs_cache, n_modes - len(deduped))
            init_rows = deduped + extra
        else:
            init_rows = deduped + [
                {"fn_hz": 0.0, "xi_pct": 2.0, "source": "manual"} for _ in range(n_modes - len(deduped))
            ]
    else:
        if cmif_for_peaks is not None:
            init_rows = cmif_peak_estimates(cmif_for_peaks, freqs_cache, n_modes)
        else:
            init_rows = [{"fn_hz": 0.0, "xi_pct": 2.0, "source": "manual"} for _ in range(n_modes)]

    init_df = pd.DataFrame(
        {
            "fn (Hz)": [r["fn_hz"] for r in init_rows[:n_modes]],
            "ξ (%)": [r["xi_pct"] for r in init_rows[:n_modes]],
            "source": [r["source"] for r in init_rows[:n_modes]],
        }
    )

    estimates_df = st.data_editor(
        init_df,
        column_config={
            "fn (Hz)": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
            "ξ (%)": st.column_config.NumberColumn(min_value=0.01, max_value=30.0, format="%.2f"),
            "source": st.column_config.TextColumn(disabled=True),
        },
        hide_index=True,
        use_container_width=True,
        key="si_estimates",
    )

    extract_btn = st.button("Extract Mode Shapes", type="secondary", use_container_width=True, key="si_extract")

# ── Build Stability Diagram ───────────────────────────────────────────────────
if build_btn:
    if not sel_outputs:
        st.error("Select at least one output channel.")
        st.stop()

    _cutoffs_ok = not (
        isinstance(cutoff_params, list) and len(cutoff_params) == 2 and cutoff_params[0] >= cutoff_params[1]
    )
    if not _cutoffs_ok:
        st.error("Filter: low cutoff must be less than high cutoff.")
        st.stop()

    with st.spinner("Pre-processing…"):
        proc_df = trim_and_filter(
            simo_df,
            t_min,
            t_max,
            filter_type if _cutoffs_ok else "None",
            filter_order,
            cutoff_params if _cutoffs_ok else None,
            fs,
        )

    _spectral_keys = ("Gxx", "Gyy", "Gxy", "Gyx", "H1", "H2", "Hv", "gamma2")
    all_res: dict = {}
    if frf_method == "Welch":
        n_proc = len(proc_df)
        nperseg = max(4, n_proc // n_seg)
        noverlap = int(nperseg * ovlp_pct / 100)
        H_cols: list = []
        last_res: dict = {}
        for ch in sel_outputs:
            last_res = compute_welch_quantities(
                proc_df[input_channel].values,
                proc_df[ch].values,
                fs,
                nperseg,
                noverlap,
                welch_win,
            )
            H_cols.append(last_res[frf_est])
            all_res[ch] = {k: last_res[k] for k in _spectral_keys}
        freqs = last_res["freqs"]
        _si_spectral_freqs = freqs
        _si_frf_method_used = "Welch"
    else:  # Single FFT
        freqs, Sx = compute_fft(proc_df[input_channel].values, fs, window="uniform")
        H_cols = []
        for ch in sel_outputs:
            _, Sy = compute_fft(proc_df[ch].values, fs, window="uniform")
            ch_res = compute_spectral_quantities(Sx, Sy)
            H_cols.append(ch_res[frf_est])
            all_res[ch] = {k: ch_res[k] for k in _spectral_keys}
        _si_spectral_freqs = freqs
        _si_frf_method_used = "Single FFT"

    H_mat = np.column_stack(H_cols)
    mask = (freqs >= f_min) & (freqs <= f_max)
    H_band = H_mat[mask]
    f_band = freqs[mask]

    with st.spinner("Building stability diagram…"):
        with warnings.catch_warnings(record=True) as _stab_warns:
            warnings.simplefilter("always")
            table = build_stability_table(
                H_band,
                f_band,
                fs,
                max_order=max_order,
                method="plscf",
                df_thr=df_thr,
                dd_thr=dd_thr,
                mac_thr=mac_thr,
            )
        sigma1 = np.linalg.norm(H_mat, axis=1)
        cmif_vals = np.column_stack([sigma1, np.zeros_like(sigma1)])

    if any(issubclass(w.category, RuntimeWarning) for w in _stab_warns):
        st.warning(
            "Residue fit was ill-conditioned at one or more model orders. "
            "Consider widening the frequency band or reducing max model order."
        )

    st.session_state["si_freqs"] = freqs
    st.session_state["si_stability_table"] = table
    st.session_state["si_cmif"] = cmif_vals
    st.session_state["si_H_mat"] = H_mat
    st.session_state["si_freqs_band"] = f_band
    st.session_state["si_H_mat_band"] = H_band
    st.session_state["si_sel_outputs"] = sel_outputs
    st.session_state["si_frf_est_used"] = frf_est
    st.session_state["si_spectral_channels"] = all_res
    st.session_state["si_spectral_freqs"] = _si_spectral_freqs
    st.session_state["si_frf_method_used"] = _si_frf_method_used
    st.session_state.pop("modal_results", None)
    st.rerun()

# ── Extract Mode Shapes ───────────────────────────────────────────────────────
if extract_btn:
    H_mat = st.session_state.get("si_H_mat")
    freqs = st.session_state.get("si_freqs")
    H_mat_band = st.session_state.get("si_H_mat_band")
    freqs_band = st.session_state.get("si_freqs_band")
    if H_mat is None or freqs is None or H_mat_band is None or freqs_band is None:
        st.error("Build the stability diagram first.")
        st.stop()

    fn_arr = estimates_df["fn (Hz)"].values.astype(float)
    xi_arr = estimates_df["ξ (%)"].values.astype(float) / 100.0

    valid = (fn_arr > 0) & (xi_arr > 0)
    fn_arr = fn_arr[valid]
    xi_arr = xi_arr[valid]

    if len(fn_arr) == 0:
        st.error("No valid mode estimates. Enter fn > 0 and ξ > 0.")
        st.stop()

    sel_out = st.session_state.get("si_sel_outputs", sel_outputs)

    with st.spinner("Extracting residues…"):
        result = extract_modes(H_mat_band, freqs_band, freqs, fn_arr, xi_arr)

    poles    = result["poles"]
    fn_fit   = result["fn_hz"]
    xi_fit   = result["xi"]
    residues = result["residues"]
    H_syn    = result["H_synthesis_full"]
    nmse     = result["nmse"]

    if len(freqs_band) < 2 * len(poles):
        st.warning(
            f"Frequency band has {len(freqs_band)} lines but {2 * len(poles)} are needed "
            f"for {len(poles)} modes — residue fit may be ill-conditioned."
        )

    st.session_state["modal_results"] = {
        "fn": fn_fit,
        "xi": xi_fit,
        "poles": poles,
        "mode_shapes": residues,  # (n_outputs, n_modes) complex
        "output_channels": sel_out,
        "freqs": freqs,
        "H_measured": H_mat,
        "H_synthesis": H_syn,
        "nmse": nmse,
    }
    st.rerun()

# ── Charts ────────────────────────────────────────────────────────────────────
with chart_col:
    stab_results = st.session_state.get("si_stability_table")
    cmif_vals = st.session_state.get("si_cmif")
    modal_res = st.session_state.get("modal_results")
    freqs_chart = st.session_state.get("si_freqs")

    tab_cmif, tab_stab, tab_shapes, tab_spectral, tab_export = st.tabs(["CMIF", "Stability Diagram", "Mode Shapes", "Spectral", "Export"])

    # ── CMIF ──────────────────────────────────────────────────────────────────
    with tab_cmif:
        if cmif_vals is None or freqs_chart is None:
            st.info("Select output channels and build the stability diagram.")
        else:
            band_mask = (freqs_chart >= f_min) & (freqs_chart <= f_max)
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=freqs_chart[band_mask],
                    y=cmif_vals[band_mask, 0],
                    mode="lines",
                    line=dict(color="#1f77b4", width=1.5),
                    name="σ₁",
                )
            )
            fig.update_yaxes(type="log", title_text="CMIF")
            fig.update_xaxes(title_text="Frequency (Hz)", range=[f_min, f_max])
            fig.update_layout(
                height=350,
                margin=dict(t=30, b=50, l=60, r=20),
                title="Complex Mode Indicator Function",
                legend=dict(orientation="h", y=-0.15),
            )
            for _f_lo, _f_hi in _coh_yellow_intervals:
                fig.add_vrect(x0=_f_lo, x1=_f_hi, fillcolor="rgba(255,200,0,0.15)", layer="below", line_width=0)
            for _f_lo, _f_hi in _coh_red_intervals:
                fig.add_vrect(x0=_f_lo, x1=_f_hi, fillcolor="rgba(220,50,50,0.20)", layer="below", line_width=0)
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Peaks indicate candidate mode locations.")

    # ── Stability Diagram ─────────────────────────────────────────────────────
    with tab_stab:
        if stab_results is None:
            st.info("Click **Build Stability Diagram** to run the analysis.")
        else:
            _style = {
                "new": dict(color="lightgrey", symbol="circle-open", size=6),
                "stable_f": dict(color="#1f77b4", symbol="cross", size=7),
                "stable_fd": dict(color="#ff7f0e", symbol="x", size=7),
                "stable_all": dict(color="#2ca02c", symbol="star", size=9),
            }
            _label = {
                "new": "New (o)",
                "stable_f": "Freq stable (f)",
                "stable_fd": "Freq+Damp stable (d)",
                "stable_all": "Fully stable (s)",
            }

            fig = go.Figure()

            # Background CMIF
            if cmif_vals is not None and freqs_chart is not None:
                band_mask = (freqs_chart >= f_min) & (freqs_chart <= f_max)
                cmif_norm = cmif_vals[:, 0] / (np.max(cmif_vals[:, 0]) + eps) * (max_order * 0.9)
                fig.add_trace(
                    go.Scatter(
                        x=freqs_chart[band_mask],
                        y=cmif_norm[band_mask],
                        mode="lines",
                        line=dict(color="rgba(150,150,150,0.3)", width=1),
                        name="CMIF (bg)",
                        showlegend=False,
                    )
                )

            # Scatter one trace per stability class
            buckets: dict[str, dict] = {k: {"x": [], "y": []} for k in _style}
            for row in stab_results:
                for k, s in enumerate(row["stability"]):
                    cls = s if s in buckets else "new"
                    buckets[cls]["x"].append(float(row["fn"][k]))
                    buckets[cls]["y"].append(row["order"])

            for cls, pts in buckets.items():
                if pts["x"]:
                    st_cfg = _style[cls]
                    fig.add_trace(
                        go.Scatter(
                            x=pts["x"],
                            y=pts["y"],
                            mode="markers",
                            marker=dict(color=st_cfg["color"], symbol=st_cfg["symbol"], size=st_cfg["size"]),
                            name=_label[cls],
                        )
                    )

            fig.update_xaxes(title_text="Natural Frequency (Hz)", range=[f_min, f_max])
            fig.update_yaxes(title_text="Model Order")
            fig.update_layout(
                height=500,
                margin=dict(t=30, b=50, l=60, r=20),
                legend=dict(orientation="h", y=-0.12),
                title="Stability Diagram — pLSCF",
            )
            for _f_lo, _f_hi in _coh_yellow_intervals:
                fig.add_vrect(x0=_f_lo, x1=_f_hi, fillcolor="rgba(255,200,0,0.15)", layer="below", line_width=0)
            for _f_lo, _f_hi in _coh_red_intervals:
                fig.add_vrect(x0=_f_lo, x1=_f_hi, fillcolor="rgba(220,50,50,0.20)", layer="below", line_width=0)
            if _coh_red_intervals:
                fig.add_annotation(
                    text="⚠ Low coherence (γ²<0.7)",
                    x=0.01, y=0.99, xref="paper", yref="paper",
                    showarrow=False, font=dict(size=10, color="darkred"),
                    bgcolor="rgba(255,240,240,0.8)", bordercolor="darkred", borderwidth=1,
                )
            st.plotly_chart(fig, use_container_width=True)
            with st.expander("Stability diagram guide"):
                st.markdown(
                    "| Glyph | Class | Criterion | Guidance |\n"
                    "|---|---|---|---|\n"
                    "| ★ green star | **Fully stable** | fn, ξ, and MAC all consistent across consecutive orders | Pick first — most trustworthy physical pole |\n"
                    "| × orange × | **Freq + Damp stable** | fn and ξ consistent; MAC not yet verified | Use if no green star appears at that frequency |\n"
                    "| + blue + | **Freq stable** | Only fn consistent | Treat with caution — often computational |\n"
                    "| ○ grey circle | **New** | First appearance at this order | Usually noise; ignore unless it stabilizes |"
                )
                st.caption(
                    "Physical modes appear as vertical columns of consistent poles. "
                    "Prefer green stars (★) that repeat at the same frequency across many model orders. "
                    "Stability thresholds (Δf, Δξ, MAC) are adjustable in the controls panel."
                )

    # ── Mode Shapes ───────────────────────────────────────────────────────────
    with tab_shapes:
        if modal_res is None:
            st.info("Specify modes and click **Extract Mode Shapes**.")
        else:
            fn_fit = modal_res["fn"]
            xi_fit = modal_res["xi"]
            poles_fit = modal_res["poles"]
            residues = modal_res["mode_shapes"]  # (n_out, n_modes)
            H_meas = modal_res["H_measured"]  # (n_freqs, n_out)
            H_syn = modal_res["H_synthesis"]
            nmse = modal_res["nmse"]
            out_chs = modal_res["output_channels"]
            n_modes_fit = len(fn_fit)
            n_out_fit = len(out_chs)

            # Summary table
            summary_rows = []
            for m in range(n_modes_fit):
                row: dict = {
                    "Mode": m + 1,
                    "fn (Hz)": round(float(fn_fit[m]), 4),
                    "ξ (%)": round(float(xi_fit[m]) * 100, 3),
                }
                for o, ch in enumerate(out_chs):
                    row[f"|φ| {ch}"] = round(float(np.abs(residues[o, m])), 6)
                    row[f"∠φ {ch} (°)"] = round(float(np.degrees(np.angle(residues[o, m]))), 2)
                summary_rows.append(row)
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

            # Individual modal FRF contributions
            show_modal = st.checkbox("Show individual modal contributions", value=False, key="si_show_modal")

            all_freqs = modal_res["freqs"]
            band_mask = (all_freqs >= f_min) & (all_freqs <= f_max)
            freqs_plot = all_freqs[band_mask]
            omega = 2.0 * np.pi * freqs_plot

            # Stacked FRF overlay plots (magnitude + phase per output channel)
            n_rows_fig = 2 * n_out_fit
            titles = []
            for ch in out_chs:
                titles += [f"|H| — {ch} (dB)", f"∠H — {ch} (°)"]

            fig = make_subplots(
                rows=n_rows_fig, cols=1, shared_xaxes=True, vertical_spacing=0.04, subplot_titles=titles
            )

            def _color(i):
                return f"hsl({(i * 47) % 360}, 65%, 50%)"

            for o, ch in enumerate(out_chs):
                row_mag = 2 * o + 1
                row_ph = 2 * o + 2
                color = _color(o + 1)

                H_m = H_meas[band_mask, o]
                H_s = H_syn[band_mask, o]

                fig.add_trace(
                    go.Scatter(
                        x=freqs_plot,
                        y=20 * np.log10(np.maximum(np.abs(H_m), eps)),
                        mode="lines",
                        name=f"Measured — {ch}",
                        line=dict(color=color, width=1.5),
                        showlegend=(o == 0),
                    ),
                    row=row_mag,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=freqs_plot,
                        y=20 * np.log10(np.maximum(np.abs(H_s), eps)),
                        mode="lines",
                        name="Synthesised",
                        line=dict(color="red", width=1.5, dash="dash"),
                        showlegend=(o == 0),
                    ),
                    row=row_mag,
                    col=1,
                )

                fig.add_trace(
                    go.Scatter(
                        x=freqs_plot,
                        y=np.degrees(np.angle(H_m)),
                        mode="lines",
                        name=f"Measured — {ch}",
                        line=dict(color=color, width=1.5),
                        showlegend=False,
                    ),
                    row=row_ph,
                    col=1,
                )
                fig.add_trace(
                    go.Scatter(
                        x=freqs_plot,
                        y=np.degrees(np.angle(H_s)),
                        mode="lines",
                        name="Synthesised",
                        line=dict(color="red", width=1.5, dash="dash"),
                        showlegend=False,
                    ),
                    row=row_ph,
                    col=1,
                )

                if show_modal:
                    for m in range(n_modes_fit):
                        pole = poles_fit[m]
                        res_m = residues[o, m]
                        H_mode = res_m / (1j * omega - pole) + res_m.conj() / (1j * omega - pole.conj())
                        fig.add_trace(
                            go.Scatter(
                                x=freqs_plot,
                                y=20 * np.log10(np.maximum(np.abs(H_mode), eps)),
                                mode="lines",
                                name=f"Mode {m + 1} — {ch}",
                                line=dict(dash="dot", width=1),
                                showlegend=(o == 0),
                            ),
                            row=row_mag,
                            col=1,
                        )

                fig.update_yaxes(title_text="|H| (dB)", row=row_mag, col=1)
                fig.update_yaxes(title_text="Phase (°)", row=row_ph, col=1)
                fig.update_xaxes(title_text="Frequency (Hz)", row=row_ph, col=1)

                nmse_val = float(nmse[o]) if o < len(nmse) else float("nan")
                fig.layout.annotations[2 * o].text += f"   NMSE = {nmse_val:.1f} dB"

            fig.update_layout(
                height=280 * n_rows_fig,
                margin=dict(t=40, b=60, l=70, r=20),
                legend=dict(orientation="h", y=-0.04),
            )
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("Fit quality (NMSE per channel)"):
                st.caption(
                    "NMSE = 10 log₁₀(error energy / signal energy). Lower (more negative) is better. "
                    "−20 dB means the error is 1 % of the measured signal energy. "
                    "Scale: Excellent < −30 dB · Good −30 to −20 dB · Acceptable −20 to −10 dB · Poor > −10 dB"
                )
                nmse_rows = [
                    {"Channel": ch, "NMSE (dB)": round(float(nmse[o]), 2), "Quality": nmse_quality_label(float(nmse[o]))}
                    for o, ch in enumerate(out_chs)
                ]
                st.dataframe(pd.DataFrame(nmse_rows), use_container_width=True, hide_index=True)

    # ── Spectral ──────────────────────────────────────────────────────────────
    with tab_spectral:
        _si_spec_chs = st.session_state.get("si_spectral_channels")
        _si_spec_freqs = st.session_state.get("si_spectral_freqs")
        _si_method_used = st.session_state.get("si_frf_method_used")
        if _si_spec_chs is None or _si_spec_freqs is None:
            st.info("Build the stability diagram to populate spectral data.")
        else:
            band_mask_sp = (_si_spec_freqs >= f_min) & (_si_spec_freqs <= f_max)
            freqs_sp = _si_spec_freqs[band_mask_sp]
            sub_frf, sub_coh, sub_psd = st.tabs(["FRF", "Coherence", "Auto-PSD"])

            with sub_frf:
                _frf_sel = st.radio("FRF estimator", ["H1", "H2", "Hv"], horizontal=True, key="si_spec_frf_est")
                n_sp_chs = len(_si_spec_chs)
                fig_frf = make_subplots(
                    rows=2 * n_sp_chs, cols=1,
                    shared_xaxes=True, vertical_spacing=0.04,
                    subplot_titles=[t for ch in _si_spec_chs for t in (f"|H| — {ch} (dB)", f"∠H — {ch} (°)")],
                )
                for i, (ch, cd) in enumerate(_si_spec_chs.items()):
                    H_sp = cd[_frf_sel][band_mask_sp]
                    clr = f"hsl({i * 47 % 360},65%,50%)"
                    fig_frf.add_trace(
                        go.Scatter(x=freqs_sp, y=20 * np.log10(np.maximum(np.abs(H_sp), eps)),
                                   mode="lines", name=ch, line=dict(color=clr, width=1.5), showlegend=True),
                        row=2 * i + 1, col=1,
                    )
                    fig_frf.add_trace(
                        go.Scatter(x=freqs_sp, y=np.degrees(np.angle(H_sp)),
                                   mode="lines", name=ch, line=dict(color=clr, width=1.5), showlegend=False),
                        row=2 * i + 2, col=1,
                    )
                    fig_frf.update_yaxes(title_text="|H| (dB)", row=2 * i + 1, col=1)
                    fig_frf.update_yaxes(title_text="Phase (°)", row=2 * i + 2, col=1)
                fig_frf.update_xaxes(title_text="Frequency (Hz)", row=2 * n_sp_chs, col=1, range=[f_min, f_max])
                fig_frf.update_layout(height=280 * 2 * n_sp_chs, margin=dict(t=40, b=60, l=70, r=20),
                                      legend=dict(orientation="h", y=-0.04))
                st.plotly_chart(fig_frf, use_container_width=True)

            with sub_coh:
                if _si_method_used == "Single FFT":
                    st.info("Coherence is 1.0 for a single-realization FFT.")
                else:
                    fig_coh = go.Figure()
                    for i, (ch, cd) in enumerate(_si_spec_chs.items()):
                        fig_coh.add_trace(
                            go.Scatter(x=freqs_sp, y=cd["gamma2"][band_mask_sp],
                                       mode="lines", name=ch,
                                       line=dict(color=f"hsl({i * 47 % 360},65%,50%)", width=1.5))
                        )
                    fig_coh.add_hline(y=0.85, line=dict(color="grey", dash="dash", width=1))
                    fig_coh.update_yaxes(title_text="γ²", range=[0, 1.05])
                    fig_coh.update_xaxes(title_text="Frequency (Hz)", range=[f_min, f_max])
                    fig_coh.update_layout(height=350, margin=dict(t=30, b=50, l=60, r=20),
                                          legend=dict(orientation="h", y=-0.15))
                    st.plotly_chart(fig_coh, use_container_width=True)

            with sub_psd:
                _first_cd = next(iter(_si_spec_chs.values()))
                n_rows_psd = 1 + len(_si_spec_chs)
                titles_psd = ["Gxx — Input"] + [f"Gyy — {ch}" for ch in _si_spec_chs]
                fig_psd = make_subplots(rows=n_rows_psd, cols=1, shared_xaxes=True,
                                        vertical_spacing=0.04, subplot_titles=titles_psd)
                fig_psd.add_trace(
                    go.Scatter(x=freqs_sp, y=10 * np.log10(np.maximum(_first_cd["Gxx"][band_mask_sp], eps)),
                               mode="lines", name="Gxx", line=dict(color="#1f77b4", width=1.5), showlegend=False),
                    row=1, col=1,
                )
                fig_psd.update_yaxes(title_text="PSD (dB)", row=1, col=1)
                for i, (ch, cd) in enumerate(_si_spec_chs.items()):
                    fig_psd.add_trace(
                        go.Scatter(x=freqs_sp, y=10 * np.log10(np.maximum(cd["Gyy"][band_mask_sp], eps)),
                                   mode="lines", name=ch,
                                   line=dict(color=f"hsl({i * 47 % 360},65%,50%)", width=1.5), showlegend=False),
                        row=i + 2, col=1,
                    )
                    fig_psd.update_yaxes(title_text="PSD (dB)", row=i + 2, col=1)
                fig_psd.update_xaxes(title_text="Frequency (Hz)", row=n_rows_psd, col=1, range=[f_min, f_max])
                fig_psd.update_layout(height=max(300, 200 * n_rows_psd), margin=dict(t=40, b=60, l=70, r=20))
                st.plotly_chart(fig_psd, use_container_width=True)

    # ── Export ────────────────────────────────────────────────────────────────
    with tab_export:
        if modal_res is None:
            st.info("Extract mode shapes to enable export.")
        else:
            fn_fit = modal_res["fn"]
            xi_fit = modal_res["xi"]
            residues = modal_res["mode_shapes"]
            out_chs = modal_res["output_channels"]

            rows = []
            for m in range(len(fn_fit)):
                row = {"mode": m + 1, "fn_hz": round(float(fn_fit[m]), 4), "xi_pct": round(float(xi_fit[m]) * 100, 3)}
                for o, ch in enumerate(out_chs):
                    row[f"phi_amp_{ch}"] = float(np.abs(residues[o, m]))
                    row[f"phi_phase_deg_{ch}"] = float(np.degrees(np.angle(residues[o, m])))
                rows.append(row)

            export_df = pd.DataFrame(rows)
            st.dataframe(export_df, use_container_width=True, hide_index=True)
            csv_bytes = export_df.to_csv(index=False).encode()
            analysis_name = st.session_state.get("analysis_name", "analysis")
            st.download_button(
                "Download CSV",
                data=csv_bytes,
                file_name=f"{analysis_name}_modal_results.csv",
                mime="text/csv",
            )
            uff_bytes = write_uff58_shapes(fn_fit, xi_fit, residues, out_chs, analysis_name)
            st.download_button(
                "Download UFF58",
                data=uff_bytes,
                file_name=f"{analysis_name}_modal_results.uff",
                mime="application/octet-stream",
            )
