import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.data_loader import load_csv, compute_sample_rate
from core.preprocess import trim_and_filter
from core.spectral import compute_output_spectral_matrix
from core.sysid import cmif_peak_estimates, fdd_damping, fdd_svd

st.set_page_config(page_title="smodal · OMA", layout="wide")

from core import brand
brand.page_header()

st.title("OMA — Operational Modal Analysis")
st.caption(
    "Frequency Domain Decomposition (FDD) from output-only response data. "
    "No force/input channel is required — the excitation is assumed broadband."
)

eps = np.finfo(float).tiny

# ── Section A: File loading ────────────────────────────────────────────────────
uploaded_file = st.file_uploader("Upload time-history CSV", type="csv", key="oma_upload")

if uploaded_file is not None and st.session_state.get("oma_file_name") != uploaded_file.name:
    df_raw, err = load_csv(uploaded_file)
    if err:
        st.error(err)
    else:
        st.session_state["oma_df"] = df_raw
        st.session_state["oma_sample_rate"] = float(compute_sample_rate(df_raw["time"].values))
        st.session_state["oma_file_name"] = uploaded_file.name
        for k in ["oma_freqs", "oma_sv", "oma_svecs", "oma_Syy", "oma_modal_results",
                   "oma_peak_estimates"]:
            st.session_state.pop(k, None)
        st.session_state["oma_peak_seed_ver"] = st.session_state.get("oma_peak_seed_ver", 0) + 1

oma_df = st.session_state.get("oma_df")
if oma_df is None:
    st.info(
        "Upload a time-history CSV. Select output (response) channels only — "
        "force or input columns should not be assigned as outputs."
    )
    st.stop()

fs: float = st.session_state.get("oma_sample_rate", 1.0)
data_cols = [c for c in oma_df.columns if c != "time"]

# ── Channel selection ──────────────────────────────────────────────────────────
st.divider()
sel_outputs = st.multiselect(
    "Output channels (response only — do not include force/input columns)",
    options=data_cols,
    default=data_cols,
    key="oma_output_chs",
)
if not sel_outputs:
    st.warning("Select at least one output channel.")
    st.stop()

ignored = [c for c in data_cols if c not in sel_outputs]
if ignored:
    st.caption(f"Ignored columns: {', '.join(ignored)}")

# ── Section B: Pre-processing expander ────────────────────────────────────────
with st.expander("Pre-processing (optional)"):
    t_min_data = float(oma_df["time"].min())
    t_max_data = float(oma_df["time"].max())
    t_step = max(round((t_max_data - t_min_data) / 1000, 6), 1e-6)
    t_min, t_max = st.slider(
        "Time range (s)",
        min_value=t_min_data,
        max_value=t_max_data,
        value=(t_min_data, t_max_data),
        step=t_step,
        key="oma_trange",
    )

    filter_type = st.radio(
        "Filter type",
        ["None", "Lowpass", "Highpass", "Bandpass", "Bandstop"],
        horizontal=True,
        key="oma_filter_type",
    )

    filter_order = 4
    cutoff_params = None

    if filter_type != "None":
        fc1, fc2 = st.columns(2)
        with fc1:
            filter_order = st.slider(
                "Filter order", min_value=1, max_value=8, value=4, key="oma_filter_order"
            )
        with fc2:
            if filter_type in ("Lowpass", "Highpass"):
                cutoff_params = float(
                    st.number_input(
                        "Cutoff (Hz)",
                        min_value=0.1,
                        max_value=float(fs / 2 * 0.99),
                        value=min(10.0, float(fs / 4)),
                        step=0.5,
                        key="oma_cutoff",
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
                        key="oma_cutoff_low",
                    )
                with bp2:
                    high_cut = st.number_input(
                        "High cutoff (Hz)",
                        min_value=0.1,
                        max_value=float(fs / 2 * 0.99),
                        value=min(50.0, float(fs / 4)),
                        step=0.5,
                        key="oma_cutoff_high",
                    )
                cutoff_params = [float(low_cut), float(high_cut)]

    n_samples = max(4, int(round((t_max - t_min) * fs)) + 1)
    filt_label = filter_type if filter_type != "None" else "no filter"
    st.caption(
        f"Time window: {t_min:.3f}–{t_max:.3f} s  ·  ≈{n_samples} samples  ·  {filt_label}"
    )

    if st.checkbox("Show time history preview", value=True, key="oma_show_th"):
        preview_cols = st.multiselect(
            "Channels to preview",
            options=sel_outputs,
            default=sel_outputs[: min(4, len(sel_outputs))],
            key="oma_preview_chs",
        )
        if preview_cols:
            mask_t = (oma_df["time"] >= t_min) & (oma_df["time"] <= t_max)
            df_trim = oma_df[mask_t]

            _cutoffs_ok = not (
                isinstance(cutoff_params, list)
                and len(cutoff_params) == 2
                and cutoff_params[0] >= cutoff_params[1]
            )
            filter_active = filter_type != "None" and cutoff_params is not None and _cutoffs_ok
            if filter_active:
                df_filt = trim_and_filter(
                    oma_df, t_min, t_max, filter_type, filter_order, cutoff_params, fs
                )

            fig_prev = make_subplots(
                rows=len(preview_cols),
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
                        x=df_trim["time"], y=df_trim[ch],
                        mode="lines", name="Raw",
                        line=dict(color="#1f77b4", width=1),
                        showlegend=(pi == 0),
                    ),
                    row=row, col=1,
                )
                if filter_active:
                    fig_prev.add_trace(
                        go.Scatter(
                            x=df_filt["time"], y=df_filt[ch],
                            mode="lines", name="Filtered",
                            line=dict(color="#ff7f0e", width=1.5, dash="dash"),
                            showlegend=(pi == 0),
                        ),
                        row=row, col=1,
                    )
                fig_prev.update_yaxes(title_text=ch, row=row, col=1)
                if row == len(preview_cols):
                    fig_prev.update_xaxes(title_text="Time (s)", row=row, col=1)

            fig_prev.update_layout(
                height=max(250, 200 * len(preview_cols)),
                margin=dict(t=30, b=50, l=70, r=20),
                legend=dict(orientation="h", y=-0.08),
            )
            st.plotly_chart(fig_prev, use_container_width=True)


def _get_proc_df():
    _ok = not (
        isinstance(cutoff_params, list)
        and len(cutoff_params) == 2
        and cutoff_params[0] >= cutoff_params[1]
    )
    return trim_and_filter(
        oma_df, t_min, t_max,
        filter_type if _ok else "None",
        filter_order,
        cutoff_params if _ok else None,
        fs,
    )


# ── Layout ────────────────────────────────────────────────────────────────────
ctrl_col, chart_col = st.columns([1, 3])

# ── Controls ──────────────────────────────────────────────────────────────────
with ctrl_col:
    st.subheader("Step 1 — Build Power CMIF")

    n_seg = st.number_input(
        "Segments", min_value=2, max_value=100, value=8, step=1, key="oma_segments"
    )
    ovlp_pct = st.slider(
        "Overlap (%)", min_value=0, max_value=90, value=50, step=5, key="oma_overlap"
    )
    welch_win = st.selectbox("Window", ["hann", "flattop", "boxcar"], key="oma_welch_win")

    nperseg_preview = max(4, n_samples // n_seg)
    df_hz = fs / nperseg_preview
    st.caption(f"Δf ≈ {df_hz:.3f} Hz  |  {nperseg_preview} samples/segment")

    oma_freqs_cached = st.session_state.get("oma_freqs")
    f_nyq = float(oma_freqs_cached[-1]) if oma_freqs_cached is not None else fs / 2.0
    f_step = round(f_nyq / 500, 4) or 0.01
    f_min, f_max = st.slider(
        "Frequency range (Hz)",
        min_value=0.0,
        max_value=f_nyq,
        value=(0.0, f_nyq),
        step=f_step,
        key="oma_frange",
    )

    build_btn = st.button(
        "Build Power CMIF", type="primary", use_container_width=True, key="oma_build"
    )

    st.divider()
    st.subheader("Step 2 — Mode Specification")

    oma_sv_cache = st.session_state.get("oma_sv")
    oma_freqs_full = st.session_state.get("oma_freqs")
    stored_estimates = st.session_state.get("oma_peak_estimates")  # set during Build

    if stored_estimates is not None:
        auto_peaks = stored_estimates
        auto_n = max(1, len(auto_peaks))
    elif oma_sv_cache is not None and oma_freqs_full is not None:
        band_mask_ctrl = (oma_freqs_full >= f_min) & (oma_freqs_full <= f_max)
        sv1_band = oma_sv_cache[band_mask_ctrl, 0]
        freqs_band = oma_freqs_full[band_mask_ctrl]
        auto_peaks = cmif_peak_estimates(sv1_band, freqs_band, n_modes=6)
        auto_n = max(1, len(auto_peaks))
    else:
        auto_peaks = []
        auto_n = 2

    n_modes = st.number_input(
        "Number of modes", min_value=1, max_value=20, value=auto_n, step=1, key="oma_n_modes"
    )

    if len(auto_peaks) >= n_modes:
        init_rows = auto_peaks[:n_modes]
    elif len(auto_peaks) > 0:
        init_rows = auto_peaks + [{"fn_hz": 0.0, "xi_pct": 2.0, "source": "manual"}
                                   for _ in range(n_modes - len(auto_peaks))]
    else:
        init_rows = [{"fn_hz": 0.0, "xi_pct": 2.0, "source": "manual"}
                     for _ in range(n_modes)]

    init_df = pd.DataFrame({
        "fn (Hz)": [r["fn_hz"] for r in init_rows[:n_modes]],
        "ξ (%)": [r["xi_pct"] for r in init_rows[:n_modes]],
        "source": [r["source"] for r in init_rows[:n_modes]],
    })

    seed_ver = st.session_state.get("oma_peak_seed_ver", 0)
    estimates_df = st.data_editor(
        init_df,
        column_config={
            "fn (Hz)": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
            "ξ (%)": st.column_config.NumberColumn(min_value=0.01, max_value=30.0, format="%.2f"),
            "source": st.column_config.TextColumn(disabled=True),
        },
        hide_index=True,
        use_container_width=True,
        key=f"oma_estimates_v{seed_ver}",
    )

    extract_btn = st.button(
        "Extract Mode Shapes", type="secondary", use_container_width=True, key="oma_extract"
    )

# ── Build Power CMIF ──────────────────────────────────────────────────────────
if build_btn:
    _cutoffs_ok = not (
        isinstance(cutoff_params, list)
        and len(cutoff_params) == 2
        and cutoff_params[0] >= cutoff_params[1]
    )
    if not _cutoffs_ok:
        st.error("Filter: low cutoff must be less than high cutoff.")
        st.stop()

    with st.spinner("Pre-processing…"):
        proc_df = _get_proc_df()

    signals = proc_df[sel_outputs].values
    n_proc = len(proc_df)
    nperseg = max(4, n_proc // n_seg)
    noverlap = int(nperseg * ovlp_pct / 100)

    with st.spinner("Computing output spectral matrix (CPSD)…"):
        freqs_full, Syy = compute_output_spectral_matrix(
            signals, fs, nperseg, noverlap, welch_win
        )

    with st.spinner("Running FDD (SVD)…"):
        sv, svecs = fdd_svd(Syy)

    st.session_state["oma_freqs"] = freqs_full
    st.session_state["oma_sv"] = sv
    st.session_state["oma_svecs"] = svecs
    st.session_state["oma_Syy"] = Syy
    st.session_state["oma_sel_outputs"] = sel_outputs
    st.session_state.pop("oma_modal_results", None)

    # Compute auto-peak estimates with real ξ from half-power bandwidth
    _band_mask = (freqs_full >= f_min) & (freqs_full <= f_max)
    _sv1_band = sv[_band_mask, 0]
    _freqs_band = freqs_full[_band_mask]
    _raw_peaks = cmif_peak_estimates(_sv1_band, _freqs_band, n_modes=6)
    _sv1_full = sv[:, 0]
    _peak_ests = []
    for _p in _raw_peaks:
        _pidx = int(np.argmin(np.abs(freqs_full - _p["fn_hz"])))
        _xi, _, _ = fdd_damping(_sv1_full, freqs_full, _pidx)
        if _xi <= 0 or _xi > 50:
            _xi = 2.0
        _peak_ests.append({"fn_hz": float(freqs_full[_pidx]), "xi_pct": round(_xi, 3), "source": "CMIF peak"})
    st.session_state["oma_peak_estimates"] = _peak_ests
    st.session_state["oma_peak_seed_ver"] = st.session_state.get("oma_peak_seed_ver", 0) + 1
    st.rerun()

# ── Extract Mode Shapes ───────────────────────────────────────────────────────
if extract_btn:
    oma_freqs = st.session_state.get("oma_freqs")
    oma_sv = st.session_state.get("oma_sv")
    oma_svecs = st.session_state.get("oma_svecs")
    oma_sel_out = st.session_state.get("oma_sel_outputs", sel_outputs)

    if oma_freqs is None or oma_sv is None:
        st.error("Build the Power CMIF first.")
        st.stop()

    fn_arr = estimates_df["fn (Hz)"].values.astype(float)
    xi_arr = estimates_df["ξ (%)"].values.astype(float)
    valid = (fn_arr > 0) & (fn_arr <= oma_freqs[-1])
    fn_arr = fn_arr[valid]
    xi_arr = xi_arr[valid]

    if len(fn_arr) == 0:
        st.error("No valid mode estimates. Enter fn > 0.")
        st.stop()

    sv1 = oma_sv[:, 0]
    modes = []
    for i, fn in enumerate(fn_arr):
        # Snap fn to nearest frequency line
        peak_idx = int(np.argmin(np.abs(oma_freqs - fn)))
        # Re-estimate damping from the half-power bandwidth
        xi_pct, f_a, f_b = fdd_damping(sv1, oma_freqs, peak_idx)
        if xi_pct <= 0 or xi_pct > 50:
            xi_pct = float(xi_arr[i])
        # Mode shape: first left singular vector at the peak frequency
        mode_shape = oma_svecs[peak_idx, :, 0]
        modes.append({
            "fn_hz": float(oma_freqs[peak_idx]),
            "xi_pct": xi_pct,
            "mode_shape": mode_shape,
            "f_a": f_a,
            "f_b": f_b,
        })

    st.session_state["oma_modal_results"] = {
        "fn": np.array([m["fn_hz"] for m in modes]),
        "xi": np.array([m["xi_pct"] / 100.0 for m in modes]),
        "mode_shapes": np.column_stack([m["mode_shape"] for m in modes]),  # (n_out, n_modes)
        "output_channels": oma_sel_out,
        "f_a": [m["f_a"] for m in modes],
        "f_b": [m["f_b"] for m in modes],
    }
    st.rerun()

# ── Charts ────────────────────────────────────────────────────────────────────
with chart_col:
    oma_freqs = st.session_state.get("oma_freqs")
    oma_sv = st.session_state.get("oma_sv")
    modal_res = st.session_state.get("oma_modal_results")

    tab_cmif, tab_shapes, tab_export = st.tabs(["Power CMIF", "Mode Shapes", "Export"])

    # ── Power CMIF tab ─────────────────────────────────────────────────────────
    with tab_cmif:
        if oma_sv is None or oma_freqs is None:
            st.info("Select output channels and click **Build Power CMIF**.")
        else:
            band_mask = (oma_freqs >= f_min) & (oma_freqs <= f_max)
            fig = go.Figure()

            n_sv = oma_sv.shape[1]
            colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
            for r in range(n_sv):
                sv_db = 10 * np.log10(np.maximum(oma_sv[band_mask, r], eps))
                fig.add_trace(go.Scatter(
                    x=oma_freqs[band_mask],
                    y=sv_db,
                    mode="lines",
                    name=f"σ{r + 1}",
                    line=dict(color=colors[r % len(colors)], width=1.5 if r == 0 else 1.0,
                              dash="solid" if r == 0 else "dash"),
                ))

            # Overlay identified peaks if extracted
            if modal_res is not None:
                for m_idx, fn in enumerate(modal_res["fn"]):
                    if f_min <= fn <= f_max:
                        peak_idx = int(np.argmin(np.abs(oma_freqs - fn)))
                        sv_db_peak = 10 * np.log10(max(oma_sv[peak_idx, 0], eps))
                        fig.add_vline(
                            x=fn, line=dict(color="red", dash="dot", width=1),
                        )
                        fig.add_annotation(
                            x=fn, y=sv_db_peak,
                            text=f"M{m_idx + 1}<br>{fn:.2f} Hz",
                            showarrow=True, arrowhead=2,
                            font=dict(size=10, color="red"),
                            arrowcolor="red",
                        )

            fig.update_xaxes(title_text="Frequency (Hz)", range=[f_min, f_max])
            fig.update_yaxes(title_text="Singular Value (dB)")
            fig.update_layout(
                height=400,
                margin=dict(t=40, b=50, l=70, r=20),
                title="Power CMIF — Singular Values of S_yy",
                legend=dict(orientation="h", y=-0.15),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "σ₁ peaks indicate natural frequencies. "
                "σ₂ peaks at the same frequency suggest repeated or closely spaced modes."
            )

    # ── Mode Shapes tab ────────────────────────────────────────────────────────
    with tab_shapes:
        if modal_res is None:
            st.info("Specify modes and click **Extract Mode Shapes**.")
        else:
            fn_fit = modal_res["fn"]
            xi_fit = modal_res["xi"]
            shapes = modal_res["mode_shapes"]   # (n_out, n_modes) complex
            out_chs = modal_res["output_channels"]
            f_a_list = modal_res["f_a"]
            f_b_list = modal_res["f_b"]
            n_modes_fit = len(fn_fit)

            # Summary table
            summary_rows = []
            for m in range(n_modes_fit):
                row: dict = {
                    "Mode": m + 1,
                    "fn (Hz)": round(float(fn_fit[m]), 4),
                    "ξ (%)": round(float(xi_fit[m]) * 100, 3),
                    "f_a (Hz)": round(float(f_a_list[m]), 4),
                    "f_b (Hz)": round(float(f_b_list[m]), 4),
                }
                for o, ch in enumerate(out_chs):
                    row[f"|φ| {ch}"] = round(float(np.abs(shapes[o, m])), 6)
                    row[f"∠φ {ch} (°)"] = round(float(np.degrees(np.angle(shapes[o, m]))), 2)
                summary_rows.append(row)
            st.dataframe(
                pd.DataFrame(summary_rows), use_container_width=True, hide_index=True
            )

            # Mode shape magnitude bar charts
            if n_modes_fit > 0 and len(out_chs) > 0:
                fig_ms = make_subplots(
                    rows=1,
                    cols=n_modes_fit,
                    subplot_titles=[f"Mode {m + 1} — {fn_fit[m]:.2f} Hz" for m in range(n_modes_fit)],
                )

                def _color(i):
                    return f"hsl({(i * 47) % 360}, 65%, 50%)"

                for m in range(n_modes_fit):
                    amps = np.abs(shapes[:, m])
                    amps_norm = amps / (np.max(amps) + eps)
                    fig_ms.add_trace(
                        go.Bar(
                            x=amps_norm,
                            y=out_chs,
                            orientation="h",
                            marker_color=_color(m),
                            name=f"Mode {m + 1}",
                            showlegend=False,
                        ),
                        row=1, col=m + 1,
                    )
                    fig_ms.update_xaxes(title_text="Norm |φ|", row=1, col=m + 1)

                fig_ms.update_layout(
                    height=max(200, 40 * len(out_chs) + 100),
                    margin=dict(t=50, b=40, l=80, r=20),
                    title="Normalised Mode Shape Amplitudes",
                )
                st.plotly_chart(fig_ms, use_container_width=True)

            st.info(
                "OMA mode shapes are un-normalised (no mass-normalisation is possible without "
                "a measured input). Amplitudes are relative, not physical residues."
            )

            # ── Auto-PSD: measured vs. analytical fit ──────────────────────────
            oma_Syy_plot = st.session_state.get("oma_Syy")
            oma_sv_plot  = st.session_state.get("oma_sv")
            oma_fq_plot  = st.session_state.get("oma_freqs")

            if oma_Syy_plot is not None and oma_sv_plot is not None and oma_fq_plot is not None:
                band_mask_s = (oma_fq_plot >= f_min) & (oma_fq_plot <= f_max)
                fq_b = oma_fq_plot[band_mask_s]
                om_b = 2 * np.pi * fq_b

                # Synthesise auto-PSDs: SDOF superposition of identified modes
                # S_yy_ii(ω) ≈ Σ_r |φ_i,r|² · A_r / ((ωr²−ω²)² + (2ξr ωr ω)²)
                # A_r = σ₁(ωr) · 4ξr² ωr⁴  (from peak value under rank-1 approx)
                S_synth = np.zeros((int(band_mask_s.sum()), len(out_chs)))
                for r in range(n_modes_fit):
                    wn   = 2 * np.pi * fn_fit[r]
                    xi_r = xi_fit[r]  # fraction
                    denom = (wn**2 - om_b**2)**2 + (2 * xi_r * wn * om_b)**2 + eps
                    H2   = 1.0 / denom
                    pidx = int(np.argmin(np.abs(oma_fq_plot - fn_fit[r])))
                    sv1_peak = float(oma_sv_plot[pidx, 0])
                    A_r = sv1_peak * 4 * xi_r**2 * wn**4
                    for i in range(len(out_chs)):
                        phi2 = float(np.abs(shapes[i, r])**2)
                        S_synth[:, i] += phi2 * A_r * H2

                fig_psd = make_subplots(
                    rows=len(out_chs),
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    subplot_titles=out_chs,
                )
                for i, ch in enumerate(out_chs):
                    S_meas     = oma_Syy_plot[band_mask_s, i, i].real
                    S_meas_db  = 10 * np.log10(np.maximum(S_meas, eps))
                    S_synth_db = 10 * np.log10(np.maximum(S_synth[:, i], eps))

                    fig_psd.add_trace(
                        go.Scatter(
                            x=fq_b, y=S_meas_db, mode="lines",
                            name="Measured", showlegend=(i == 0),
                            line=dict(color="#1f77b4", width=1),
                        ),
                        row=i + 1, col=1,
                    )
                    fig_psd.add_trace(
                        go.Scatter(
                            x=fq_b, y=S_synth_db, mode="lines",
                            name="SDOF fit", showlegend=(i == 0),
                            line=dict(color="#d62728", width=1.5, dash="dash"),
                        ),
                        row=i + 1, col=1,
                    )
                    for fn_m in fn_fit:
                        if f_min <= fn_m <= f_max:
                            ax_n = "" if i == 0 else str(i + 1)
                            fig_psd.add_shape(
                                type="line",
                                x0=fn_m, x1=fn_m,
                                y0=0, y1=1,
                                xref=f"x{ax_n}", yref=f"y{ax_n} domain",
                                line=dict(color="green", dash="dot", width=1),
                            )
                    fig_psd.update_yaxes(title_text="PSD (dB)", row=i + 1, col=1)

                fig_psd.update_xaxes(
                    title_text="Frequency (Hz)", range=[f_min, f_max],
                    row=len(out_chs), col=1,
                )
                fig_psd.update_layout(
                    height=max(300, 200 * len(out_chs)),
                    margin=dict(t=50, b=50, l=70, r=20),
                    title="Auto-PSD: Measured vs. SDOF Modal Fit",
                    legend=dict(orientation="h", y=-0.12),
                )
                st.plotly_chart(fig_psd, use_container_width=True)
                st.caption(
                    "Blue — measured auto-PSD (diagonal of S_yy). "
                    "Red dashed — SDOF superposition of identified modes. "
                    "Green dotted lines mark natural frequencies."
                )

    # ── Export tab ─────────────────────────────────────────────────────────────
    with tab_export:
        if modal_res is None:
            st.info("Extract mode shapes to enable export.")
        else:
            fn_fit = modal_res["fn"]
            xi_fit = modal_res["xi"]
            shapes = modal_res["mode_shapes"]
            out_chs = modal_res["output_channels"]

            rows = []
            for m in range(len(fn_fit)):
                row = {
                    "mode": m + 1,
                    "fn_hz": round(float(fn_fit[m]), 4),
                    "xi_pct": round(float(xi_fit[m]) * 100, 3),
                }
                for o, ch in enumerate(out_chs):
                    row[f"phi_amp_{ch}"] = float(np.abs(shapes[o, m]))
                    row[f"phi_phase_deg_{ch}"] = float(np.degrees(np.angle(shapes[o, m])))
                rows.append(row)

            export_df = pd.DataFrame(rows)
            st.dataframe(export_df, use_container_width=True, hide_index=True)
            csv_bytes = export_df.to_csv(index=False).encode()
            analysis_name = st.session_state.get("analysis_name", "analysis")
            st.download_button(
                "Download CSV",
                data=csv_bytes,
                file_name=f"{analysis_name}_oma_results.csv",
                mime="text/csv",
            )
            st.caption(
                "CSV format is compatible with the MAC page (Page 7). "
                "Import as a SIMO result to compare OMA shapes against FE modes."
            )
