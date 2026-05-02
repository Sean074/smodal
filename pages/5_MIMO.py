import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.signal import butter, sosfiltfilt
import streamlit as st

from core.data_loader import load_csv, compute_sample_rate
from core.spectral import compute_fft, compute_spectral_quantities, compute_welch_quantities
from core.sysid import (
    build_stability_table,
    cmif_peak_estimates,
    compute_mimo_cmif,
    extract_residues,
    modal_fit_nmse,
    poles_from_estimates,
    synthesize_frf,
)

st.set_page_config(page_title="MIMO EMA", layout="wide")
st.title("MIMO — Multi-Reference System Identification (EMA)")

eps = np.finfo(float).tiny


# ── Helper: apply pre-processing to a DataFrame ───────────────────────────────
def _preprocess(
    df: pd.DataFrame,
    t_min: float,
    t_max: float,
    ftype: str,
    forder: int,
    cutoffs,
    fs: float,
) -> pd.DataFrame:
    proc = df[(df["time"] >= t_min) & (df["time"] <= t_max)].copy().reset_index(drop=True)
    if ftype == "None" or cutoffs is None:
        return proc
    btype_map = {
        "Lowpass": "low",
        "Highpass": "high",
        "Bandpass": "band",
        "Bandstop": "bandstop",
    }
    sos = butter(forder, cutoffs, btype=btype_map[ftype], fs=fs, output="sos")
    for col in proc.columns:
        if col != "time":
            proc[col] = sosfiltfilt(sos, proc[col].values)
    return proc


# ── Section A: File loading ────────────────────────────────────────────────────
col_up_a, col_up_b = st.columns(2)
with col_up_a:
    st.markdown("**Run A — In-phase excitation**")
    file_a = st.file_uploader(
        "Upload Run A CSV", type="csv", key="mimo_upload_a", label_visibility="collapsed"
    )
with col_up_b:
    st.markdown("**Run B — Out-of-phase excitation**")
    file_b = st.file_uploader(
        "Upload Run B CSV", type="csv", key="mimo_upload_b", label_visibility="collapsed"
    )

# Load on file change (name-based guard avoids re-reading on every rerun)
if file_a is not None and st.session_state.get("mimo_file_a_name") != file_a.name:
    df_a, err_a = load_csv(file_a)
    if err_a:
        st.error(f"Run A: {err_a}")
    else:
        st.session_state["mimo_run_a_df"] = df_a
        st.session_state["mimo_sample_rate"] = float(compute_sample_rate(df_a["time"].values))
        st.session_state["mimo_file_a_name"] = file_a.name
        for k in ["mimo_H_mat", "mimo_freqs", "mimo_cmif", "mimo_stability_table", "mimo_modal_results"]:
            st.session_state.pop(k, None)

if file_b is not None and st.session_state.get("mimo_file_b_name") != file_b.name:
    df_b, err_b = load_csv(file_b)
    if err_b:
        st.error(f"Run B: {err_b}")
    else:
        st.session_state["mimo_run_b_df"] = df_b
        st.session_state["mimo_file_b_name"] = file_b.name
        for k in ["mimo_H_mat", "mimo_freqs", "mimo_cmif", "mimo_stability_table", "mimo_modal_results"]:
            st.session_state.pop(k, None)
        fs_b = float(compute_sample_rate(df_b["time"].values))
        fs_a = st.session_state.get("mimo_sample_rate")
        if fs_a is not None and abs(fs_b - fs_a) / (fs_a + 1e-9) > 0.01:
            st.warning(
                f"Run B sample rate ({fs_b:.1f} Hz) differs from Run A ({fs_a:.1f} Hz) by more than 1 %. "
                "FRF estimates will be unreliable. Re-upload files with matching sample rates."
            )

run_a = st.session_state.get("mimo_run_a_df")
run_b = st.session_state.get("mimo_run_b_df")

if run_a is None or run_b is None:
    st.info("Upload both **Run A** (in-phase) and **Run B** (out-of-phase) CSV files to begin.")
    st.stop()

fs: float = st.session_state.get("mimo_sample_rate", 1.0)

common_cols = sorted(set(run_a.columns) & set(run_b.columns) - {"time"})
if not common_cols:
    st.error("Run A and Run B share no common data channels. Ensure both files use the same column names.")
    st.stop()

# ── Channel assignment ─────────────────────────────────────────────────────────
st.divider()
ch_col_a, ch_col_b, ch_col_out = st.columns([1, 1, 2])
with ch_col_a:
    input_a = st.selectbox("Run A input channel", options=common_cols, key="mimo_input_a")
with ch_col_b:
    input_b = st.selectbox("Run B input channel", options=common_cols, key="mimo_input_b")
with ch_col_out:
    avail_outputs = [c for c in common_cols if c not in (input_a, input_b)]
    if not avail_outputs:
        avail_outputs = [c for c in common_cols if c != input_a]
    sel_outputs = st.multiselect(
        "Output channels", options=avail_outputs, default=avail_outputs, key="mimo_outputs"
    )

if not sel_outputs:
    st.warning("Select at least one output channel.")
    st.stop()

n_out = len(sel_outputs)

# ── Section B: Pre-processing expander (Option C) ─────────────────────────────
with st.expander("Pre-processing (optional — applied identically to both runs)"):
    t_min_data = float(run_a["time"].min())
    t_max_data = float(run_a["time"].max())
    t_step = max(round((t_max_data - t_min_data) / 1000, 6), 1e-6)
    t_min, t_max = st.slider(
        "Time range (s)",
        min_value=t_min_data,
        max_value=t_max_data,
        value=(t_min_data, t_max_data),
        step=t_step,
        key="mimo_trange",
    )

    filter_type = st.radio(
        "Filter type",
        ["None", "Lowpass", "Highpass", "Bandpass", "Bandstop"],
        horizontal=True,
        key="mimo_filter_type",
    )

    filter_order = 4
    cutoff_params = None

    if filter_type != "None":
        fc1, fc2 = st.columns(2)
        with fc1:
            filter_order = st.slider(
                "Filter order", min_value=1, max_value=8, value=4, key="mimo_filter_order"
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
                        key="mimo_cutoff",
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
                        key="mimo_cutoff_low",
                    )
                with bp2:
                    high_cut = st.number_input(
                        "High cutoff (Hz)",
                        min_value=0.1,
                        max_value=float(fs / 2 * 0.99),
                        value=min(50.0, float(fs / 4)),
                        step=0.5,
                        key="mimo_cutoff_high",
                    )
                cutoff_params = [float(low_cut), float(high_cut)]

    n_samples = max(4, int(round((t_max - t_min) * fs)) + 1)
    filt_label = filter_type if filter_type != "None" else "no filter"
    st.caption(
        f"Time window: {t_min:.3f}–{t_max:.3f} s  ·  ≈{n_samples} samples  ·  {filt_label}"
    )

    if st.checkbox("Show time history preview", value=True, key="mimo_show_th"):
        preview_cols = st.multiselect(
            "Channels to preview",
            options=common_cols,
            default=common_cols[: min(4, len(common_cols))],
            key="mimo_preview_chs",
        )
        if preview_cols:
            mask_a = (run_a["time"] >= t_min) & (run_a["time"] <= t_max)
            mask_b = (run_b["time"] >= t_min) & (run_b["time"] <= t_max)
            ra_trim = run_a[mask_a]
            rb_trim = run_b[mask_b]

            filter_active = (
                filter_type != "None"
                and cutoff_params is not None
                and not (isinstance(cutoff_params, list) and cutoff_params[0] >= cutoff_params[1])
            )
            if filter_active:
                ra_filt = _preprocess(run_a, t_min, t_max, filter_type, filter_order, cutoff_params, fs)
                rb_filt = _preprocess(run_b, t_min, t_max, filter_type, filter_order, cutoff_params, fs)

            n_rows_prev = len(preview_cols)
            fig_prev = make_subplots(
                rows=n_rows_prev,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.05,
                subplot_titles=preview_cols,
            )

            for pi, ch in enumerate(preview_cols):
                if ch not in ra_trim.columns or ch not in rb_trim.columns:
                    continue
                row = pi + 1
                first = pi == 0

                fig_prev.add_trace(
                    go.Scatter(
                        x=ra_trim["time"],
                        y=ra_trim[ch],
                        mode="lines",
                        name="Run A",
                        line=dict(color="#1f77b4", width=1),
                        showlegend=first,
                    ),
                    row=row,
                    col=1,
                )
                fig_prev.add_trace(
                    go.Scatter(
                        x=rb_trim["time"],
                        y=rb_trim[ch],
                        mode="lines",
                        name="Run B",
                        line=dict(color="#ff7f0e", width=1),
                        showlegend=first,
                    ),
                    row=row,
                    col=1,
                )

                if filter_active:
                    fig_prev.add_trace(
                        go.Scatter(
                            x=ra_filt["time"],
                            y=ra_filt[ch],
                            mode="lines",
                            name="Run A (filtered)",
                            line=dict(color="#1f77b4", width=1.5, dash="dash"),
                            showlegend=first,
                        ),
                        row=row,
                        col=1,
                    )
                    fig_prev.add_trace(
                        go.Scatter(
                            x=rb_filt["time"],
                            y=rb_filt[ch],
                            mode="lines",
                            name="Run B (filtered)",
                            line=dict(color="#ff7f0e", width=1.5, dash="dash"),
                            showlegend=first,
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

# ── Layout ────────────────────────────────────────────────────────────────────
ctrl_col, chart_col = st.columns([1, 3])

# ── Controls ──────────────────────────────────────────────────────────────────
with ctrl_col:
    st.subheader("Step 1 — Stability Diagram")

    frf_method = st.radio(
        "FRF method", ["Welch", "Single FFT"], horizontal=True, key="mimo_frf_method"
    )

    n_seg = 8
    ovlp_pct = 50
    welch_win = "hann"

    if frf_method == "Welch":
        n_seg = st.selectbox("Segments", options=[4, 8, 16, 32, 64], index=1, key="mimo_segments")
        ovlp_pct = st.selectbox("Overlap (%)", options=[0, 25, 50, 75], index=2, key="mimo_overlap")
        welch_win = st.selectbox("Window", options=["hann", "flattop", "boxcar"], key="mimo_welch_win")
        nperseg_preview = max(4, n_samples // n_seg)
        delta_f_preview = fs / nperseg_preview
        st.caption(f"Δf ≈ {delta_f_preview:.3f} Hz · ~{nperseg_preview} samples/segment")

    frf_est = st.radio("FRF estimator", ["H1", "H2", "Hv"], horizontal=True, key="mimo_frf_est")

    f_nyq = fs / 2.0
    f_step = round(f_nyq / 500, 4) or 0.01
    f_min_hz, f_max_hz = st.slider(
        "Frequency range (Hz)",
        min_value=0.0,
        max_value=f_nyq,
        value=(0.0, f_nyq),
        step=f_step,
        key="mimo_frange",
    )

    max_order = st.slider(
        "Max model order", min_value=4, max_value=100, value=40, step=2, key="mimo_max_order"
    )

    with st.expander("Stability thresholds"):
        df_thr = (
            st.number_input(
                "Δf threshold (%)", value=1.0, step=0.5, min_value=0.1, key="mimo_df_thr"
            )
            / 100.0
        )
        dd_thr = (
            st.number_input(
                "Δξ threshold (%)", value=5.0, step=1.0, min_value=0.1, key="mimo_dd_thr"
            )
            / 100.0
        )
        mac_thr = st.slider(
            "MAC threshold", min_value=0.5, max_value=1.0, value=0.95, step=0.01, key="mimo_mac_thr"
        )

    build_btn = st.button(
        "Build Stability Diagram", type="primary", use_container_width=True, key="mimo_build"
    )

    st.divider()
    st.subheader("Step 2 — Mode Specification")

    stab_results = st.session_state.get("mimo_stability_table")
    cmif_cache = st.session_state.get("mimo_cmif")
    freqs_cache = st.session_state.get("mimo_freqs")

    # Auto-suggest n_modes from green stable poles
    if stab_results is not None:
        green_poles = []
        for row in stab_results:
            for k, s in enumerate(row["stability"]):
                if s == "stable_all":
                    green_poles.append(
                        {
                            "fn_hz": float(row["fn"][k]),
                            "xi_pct": float(row["xi"][k]) * 100.0,
                            "source": f"order {row['order']}",
                        }
                    )
        deduped: list[dict] = []
        for g in sorted(green_poles, key=lambda x: x["fn_hz"]):
            if (
                not deduped
                or abs(g["fn_hz"] - deduped[-1]["fn_hz"]) / (g["fn_hz"] + 1e-9) > 0.01
            ):
                deduped.append(g)
        auto_n = max(1, len(deduped))
    else:
        deduped = []
        auto_n = 1

    n_modes = st.number_input(
        "Number of modes", min_value=1, max_value=20, value=auto_n, step=1, key="mimo_n_modes"
    )

    # Build initial estimates table
    cmif_for_peaks = cmif_cache[:, 0] if cmif_cache is not None else None

    if len(deduped) >= n_modes:
        init_rows = deduped[:n_modes]
    elif len(deduped) > 0:
        if cmif_for_peaks is not None and freqs_cache is not None:
            extra = cmif_peak_estimates(cmif_for_peaks, freqs_cache, n_modes - len(deduped))
            init_rows = deduped + extra
        else:
            init_rows = deduped + [
                {"fn_hz": 0.0, "xi_pct": 2.0, "source": "manual"}
                for _ in range(n_modes - len(deduped))
            ]
    else:
        if cmif_for_peaks is not None and freqs_cache is not None:
            init_rows = cmif_peak_estimates(cmif_for_peaks, freqs_cache, n_modes)
        else:
            init_rows = [
                {"fn_hz": 0.0, "xi_pct": 2.0, "source": "manual"} for _ in range(n_modes)
            ]

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
        key="mimo_estimates",
    )

    extract_btn = st.button(
        "Extract Mode Shapes", type="secondary", use_container_width=True, key="mimo_extract"
    )

# ── Build Stability Diagram ────────────────────────────────────────────────────
if build_btn:
    if not sel_outputs:
        st.error("Select at least one output channel.")
        st.stop()

    if isinstance(cutoff_params, list) and len(cutoff_params) == 2:
        if cutoff_params[0] >= cutoff_params[1]:
            st.error("Filter: low cutoff must be less than high cutoff.")
            st.stop()

    with st.spinner("Pre-processing…"):
        run_a_proc = _preprocess(run_a, t_min, t_max, filter_type, filter_order, cutoff_params, fs)
        run_b_proc = _preprocess(run_b, t_min, t_max, filter_type, filter_order, cutoff_params, fs)

    with st.spinner("Computing FRFs…"):
        H_A_cols: list[np.ndarray] = []
        H_B_cols: list[np.ndarray] = []

        if frf_method == "Welch":
            n_proc = len(run_a_proc)
            nperseg_build = max(4, n_proc // n_seg)
            noverlap_build = int(nperseg_build * ovlp_pct / 100)
            for ch in sel_outputs:
                res_a = compute_welch_quantities(
                    run_a_proc[input_a].values,
                    run_a_proc[ch].values,
                    fs,
                    nperseg_build,
                    noverlap_build,
                    welch_win,
                )
                res_b = compute_welch_quantities(
                    run_b_proc[input_b].values,
                    run_b_proc[ch].values,
                    fs,
                    nperseg_build,
                    noverlap_build,
                    welch_win,
                )
                H_A_cols.append(res_a[frf_est])
                H_B_cols.append(res_b[frf_est])
            freqs_full: np.ndarray = res_a["freqs"]

        else:  # Single FFT
            freqs_full, Sx_a = compute_fft(run_a_proc[input_a].values, fs)
            _, Sx_b = compute_fft(run_b_proc[input_b].values, fs)
            for ch in sel_outputs:
                _, Sy_a = compute_fft(run_a_proc[ch].values, fs)
                _, Sy_b = compute_fft(run_b_proc[ch].values, fs)
                H_A_cols.append(compute_spectral_quantities(Sx_a, Sy_a)[frf_est])
                H_B_cols.append(compute_spectral_quantities(Sx_b, Sy_b)[frf_est])

        H_A = np.column_stack(H_A_cols)          # (n_freqs, n_out)
        H_B = np.column_stack(H_B_cols)          # (n_freqs, n_out)
        H_stacked = np.column_stack([H_A, H_B])  # (n_freqs, n_out * 2)

    with st.spinner("Building stability diagram…"):
        band_mask = (freqs_full >= f_min_hz) & (freqs_full <= f_max_hz)
        H_band = H_stacked[band_mask]
        freqs_band = freqs_full[band_mask]

        if len(freqs_band) == 0:
            st.error("No frequency points in the selected range. Widen the frequency range.")
            st.stop()

        cmif_vals = compute_mimo_cmif(H_stacked, n_out)  # (n_freqs, 2) — full range

        table = build_stability_table(
            H_band,
            freqs_band,
            fs,
            max_order=max_order,
            method="plscf",
            df_thr=df_thr,
            dd_thr=dd_thr,
            mac_thr=mac_thr,
        )

    st.session_state["mimo_H_mat"] = H_stacked
    st.session_state["mimo_freqs"] = freqs_full
    st.session_state["mimo_freqs_band"] = freqs_band
    st.session_state["mimo_cmif"] = cmif_vals
    st.session_state["mimo_stability_table"] = table
    st.session_state["mimo_sel_outputs"] = sel_outputs
    st.session_state["mimo_n_out"] = n_out
    st.session_state["mimo_frf_est_used"] = frf_est
    st.session_state.pop("mimo_modal_results", None)
    st.rerun()

# ── Extract Mode Shapes ────────────────────────────────────────────────────────
if extract_btn:
    H_mat = st.session_state.get("mimo_H_mat")
    freqs_ext = st.session_state.get("mimo_freqs")
    n_out_ext: int = st.session_state.get("mimo_n_out", n_out)
    sel_out_ext: list = st.session_state.get("mimo_sel_outputs", sel_outputs)

    if H_mat is None or freqs_ext is None:
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

    poles = poles_from_estimates(fn_arr, xi_arr)

    with st.spinner("Extracting residues…"):
        residues = extract_residues(H_mat, freqs_ext, poles)  # (n_out*2, n_modes)

        # Reshape: first n_out_ext rows = Run A, next n_out_ext rows = Run B
        res_A = residues[:n_out_ext, :]   # (n_out, n_modes)
        res_B = residues[n_out_ext:, :]   # (n_out, n_modes)
        r3d = np.stack([res_A, res_B], axis=1)  # (n_out, 2, n_modes)

        # Symmetric (S) if Run A norm dominates, Antisymmetric (A) otherwise
        n_modes_fit = residues.shape[1]
        mode_types = []
        for m in range(n_modes_fit):
            norm_A = np.linalg.norm(r3d[:, 0, m])
            norm_B = np.linalg.norm(r3d[:, 1, m])
            mode_types.append("S" if norm_A >= norm_B else "A")

        H_syn = synthesize_frf(freqs_ext, poles, residues)  # (n_freqs, n_out*2)
        nmse = modal_fit_nmse(H_mat, H_syn)                 # (n_out*2,)

    fn_fit = np.abs(poles.imag) / (2.0 * np.pi)
    xi_fit = -poles.real / (np.abs(poles) + 1e-30)

    st.session_state["mimo_modal_results"] = {
        "fn": fn_fit,
        "xi": xi_fit,
        "poles": poles,
        "mode_shapes": r3d,           # (n_out, 2, n_modes) complex
        "residues_flat": residues,    # (n_out*2, n_modes) for modal contribution plots
        "mode_types": mode_types,
        "output_channels": sel_out_ext,
        "freqs": freqs_ext,
        "H_measured": H_mat,
        "H_synthesis": H_syn,
        "nmse": nmse,
    }
    st.rerun()

# ── Charts ─────────────────────────────────────────────────────────────────────
with chart_col:
    cmif_vals = st.session_state.get("mimo_cmif")
    freqs_full_c = st.session_state.get("mimo_freqs")
    stab_results = st.session_state.get("mimo_stability_table")
    modal_res = st.session_state.get("mimo_modal_results")

    tab_cmif, tab_stab, tab_shapes, tab_export = st.tabs(
        ["CMIF", "Stability Diagram", "Mode Shapes", "Export"]
    )

    # ── CMIF ──────────────────────────────────────────────────────────────────
    with tab_cmif:
        if cmif_vals is None or freqs_full_c is None:
            st.info("Click **Build Stability Diagram** to compute the SVD-CMIF.")
        else:
            bm = (freqs_full_c >= f_min_hz) & (freqs_full_c <= f_max_hz)
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=freqs_full_c[bm],
                    y=cmif_vals[bm, 0],
                    mode="lines",
                    name="σ₁ — all modes",
                    line=dict(color="#1f77b4", width=1.5),
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=freqs_full_c[bm],
                    y=cmif_vals[bm, 1],
                    mode="lines",
                    name="σ₂ — repeated / closely-spaced",
                    line=dict(color="#ff7f0e", width=1.5, dash="dash"),
                )
            )
            fig.update_yaxes(type="log", title_text="Singular Value")
            fig.update_xaxes(title_text="Frequency (Hz)", range=[f_min_hz, f_max_hz])
            fig.update_layout(
                height=400,
                margin=dict(t=30, b=50, l=60, r=20),
                title="SVD-CMIF — Multi-Reference",
                legend=dict(orientation="h", y=-0.18),
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("σ₁ shows all modes. σ₂ helps resolve repeated or closely-spaced modes.")

    # ── Stability Diagram ─────────────────────────────────────────────────────
    with tab_stab:
        if stab_results is None:
            st.info("Click **Build Stability Diagram** to run the analysis.")
        else:
            _style = {
                "new":        dict(color="lightgrey", symbol="circle-open", size=6),
                "stable_f":   dict(color="#1f77b4",   symbol="cross",        size=7),
                "stable_fd":  dict(color="#ff7f0e",   symbol="x",            size=7),
                "stable_all": dict(color="#2ca02c",   symbol="star",         size=9),
            }
            _label = {
                "new":        "New (o)",
                "stable_f":   "Freq stable (f)",
                "stable_fd":  "Freq+Damp stable (d)",
                "stable_all": "Fully stable (s)",
            }

            fig = go.Figure()

            if cmif_vals is not None and freqs_full_c is not None:
                bm = (freqs_full_c >= f_min_hz) & (freqs_full_c <= f_max_hz)
                cmif_norm = cmif_vals[:, 0] / (np.max(cmif_vals[:, 0]) + eps) * (max_order * 0.9)
                fig.add_trace(
                    go.Scatter(
                        x=freqs_full_c[bm],
                        y=cmif_norm[bm],
                        mode="lines",
                        line=dict(color="rgba(150,150,150,0.3)", width=1),
                        name="σ₁ CMIF (bg)",
                        showlegend=False,
                    )
                )

            buckets: dict[str, dict] = {k: {"x": [], "y": []} for k in _style}
            for row in stab_results:
                for k, s in enumerate(row["stability"]):
                    cls = s if s in buckets else "new"
                    buckets[cls]["x"].append(float(row["fn"][k]))
                    buckets[cls]["y"].append(row["order"])

            for cls, pts in buckets.items():
                if pts["x"]:
                    sc = _style[cls]
                    fig.add_trace(
                        go.Scatter(
                            x=pts["x"],
                            y=pts["y"],
                            mode="markers",
                            marker=dict(color=sc["color"], symbol=sc["symbol"], size=sc["size"]),
                            name=_label[cls],
                        )
                    )

            fig.update_xaxes(title_text="Natural Frequency (Hz)", range=[f_min_hz, f_max_hz])
            fig.update_yaxes(title_text="Model Order")
            fig.update_layout(
                height=500,
                margin=dict(t=30, b=50, l=60, r=20),
                legend=dict(orientation="h", y=-0.12),
                title="Stability Diagram — pLSCF (Multi-Reference)",
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Mode Shapes ───────────────────────────────────────────────────────────
    with tab_shapes:
        if modal_res is None:
            st.info("Specify modes and click **Extract Mode Shapes**.")
        else:
            fn_fit = modal_res["fn"]
            xi_fit = modal_res["xi"]
            poles_fit = modal_res["poles"]
            r3d = modal_res["mode_shapes"]          # (n_out, 2, n_modes)
            residues_flat = modal_res["residues_flat"]  # (n_out*2, n_modes)
            H_meas = modal_res["H_measured"]         # (n_freqs, n_out*2)
            H_syn_res = modal_res["H_synthesis"]     # (n_freqs, n_out*2)
            nmse = modal_res["nmse"]                 # (n_out*2,)
            out_chs = modal_res["output_channels"]
            mode_types = modal_res["mode_types"]
            n_modes_fit = len(fn_fit)
            n_out_fit = len(out_chs)

            # Summary table
            summary_rows = []
            for m in range(n_modes_fit):
                row_d: dict = {
                    "Mode": m + 1,
                    "fn (Hz)": round(float(fn_fit[m]), 4),
                    "ξ (%)": round(float(xi_fit[m]) * 100, 3),
                    "Type": mode_types[m],
                }
                for o, ch in enumerate(out_chs):
                    for ri, rl in enumerate(["A", "B"]):
                        row_d[f"|φ| {rl}·{ch}"] = round(float(np.abs(r3d[o, ri, m])), 6)
                        row_d[f"∠φ {rl}·{ch} (°)"] = round(
                            float(np.degrees(np.angle(r3d[o, ri, m]))), 2
                        )
                summary_rows.append(row_d)
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

            # Per-channel plot selector
            default_plot = out_chs[: min(4, len(out_chs))]
            plot_chs = st.multiselect(
                "Channels to plot", options=out_chs, default=default_plot, key="mimo_plot_chs"
            )
            show_modal = st.checkbox(
                "Show individual modal contributions", value=False, key="mimo_show_modal"
            )

            if not plot_chs:
                st.info("Select channels to plot.")
            else:
                all_freqs = modal_res["freqs"]
                bm_plot = (all_freqs >= f_min_hz) & (all_freqs <= f_max_hz)
                freqs_plot = all_freqs[bm_plot]
                omega_plot = 2.0 * np.pi * freqs_plot

                # 4 rows per channel: Run-A mag, Run-A phase, Run-B mag, Run-B phase
                n_rows_fig = 4 * len(plot_chs)
                titles = []
                for ch in plot_chs:
                    titles += [
                        f"|H_A| — {ch} (dB)",
                        f"∠H_A — {ch} (°)",
                        f"|H_B| — {ch} (dB)",
                        f"∠H_B — {ch} (°)",
                    ]

                fig = make_subplots(
                    rows=n_rows_fig,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.03,
                    subplot_titles=titles,
                )

                def _color(i: int) -> str:
                    return f"hsl({(i * 47) % 360}, 65%, 50%)"

                for pi, ch in enumerate(plot_chs):
                    o = out_chs.index(ch)
                    color = _color(pi + 1)
                    base_row = 4 * pi

                    for ri, rl in enumerate(["A", "B"]):
                        col_idx = o if ri == 0 else n_out_fit + o
                        row_mag = base_row + 2 * ri + 1
                        row_ph = base_row + 2 * ri + 2

                        H_m = H_meas[bm_plot, col_idx]
                        H_s = H_syn_res[bm_plot, col_idx]
                        first = pi == 0 and ri == 0

                        fig.add_trace(
                            go.Scatter(
                                x=freqs_plot,
                                y=20 * np.log10(np.maximum(np.abs(H_m), eps)),
                                mode="lines",
                                name=f"Measured (Run {rl})",
                                line=dict(color=color, width=1.5),
                                showlegend=first,
                            ),
                            row=row_mag,
                            col=1,
                        )
                        fig.add_trace(
                            go.Scatter(
                                x=freqs_plot,
                                y=20 * np.log10(np.maximum(np.abs(H_s), eps)),
                                mode="lines",
                                name=f"Synthesised (Run {rl})",
                                line=dict(color="red", width=1.5, dash="dash"),
                                showlegend=first,
                            ),
                            row=row_mag,
                            col=1,
                        )
                        fig.add_trace(
                            go.Scatter(
                                x=freqs_plot,
                                y=np.degrees(np.angle(H_m)),
                                mode="lines",
                                name=f"Measured (Run {rl})",
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
                                name=f"Synthesised (Run {rl})",
                                line=dict(color="red", width=1.5, dash="dash"),
                                showlegend=False,
                            ),
                            row=row_ph,
                            col=1,
                        )

                        if show_modal:
                            for m in range(n_modes_fit):
                                pole = poles_fit[m]
                                res_m = residues_flat[col_idx, m]
                                H_mode = res_m / (1j * omega_plot - pole) + res_m.conj() / (
                                    1j * omega_plot - pole.conj()
                                )
                                fig.add_trace(
                                    go.Scatter(
                                        x=freqs_plot,
                                        y=20 * np.log10(np.maximum(np.abs(H_mode), eps)),
                                        mode="lines",
                                        name=f"Mode {m + 1}",
                                        line=dict(dash="dot", width=1),
                                        showlegend=first,
                                    ),
                                    row=row_mag,
                                    col=1,
                                )

                        fig.update_yaxes(title_text="|H| (dB)", row=row_mag, col=1)
                        fig.update_yaxes(title_text="Phase (°)", row=row_ph, col=1)
                        if row_ph == n_rows_fig:
                            fig.update_xaxes(title_text="Frequency (Hz)", row=row_ph, col=1)

                        # Annotate NMSE on magnitude subplot title
                        nmse_val = float(nmse[col_idx]) if col_idx < len(nmse) else float("nan")
                        ann_idx = pi * 4 + ri * 2
                        if ann_idx < len(fig.layout.annotations):
                            fig.layout.annotations[ann_idx].text += (
                                f"   NMSE = {nmse_val:.1f} dB"
                            )

                fig.update_layout(
                    height=220 * n_rows_fig,
                    margin=dict(t=40, b=60, l=70, r=20),
                    legend=dict(orientation="h", y=-0.04),
                )
                st.plotly_chart(fig, use_container_width=True)

    # ── Export ────────────────────────────────────────────────────────────────
    with tab_export:
        if modal_res is None:
            st.info("Extract mode shapes to enable export.")
        else:
            fn_fit = modal_res["fn"]
            xi_fit = modal_res["xi"]
            r3d = modal_res["mode_shapes"]
            out_chs = modal_res["output_channels"]
            mode_types = modal_res["mode_types"]

            rows = []
            for m in range(len(fn_fit)):
                row_e: dict = {
                    "mode": m + 1,
                    "fn_hz": round(float(fn_fit[m]), 4),
                    "xi_pct": round(float(xi_fit[m]) * 100, 3),
                    "type": mode_types[m],
                }
                for o, ch in enumerate(out_chs):
                    for ri, rl in enumerate(["A", "B"]):
                        row_e[f"phi_amp_{rl}_{ch}"] = float(np.abs(r3d[o, ri, m]))
                        row_e[f"phi_phase_deg_{rl}_{ch}"] = float(
                            np.degrees(np.angle(r3d[o, ri, m]))
                        )
                rows.append(row_e)

            export_df = pd.DataFrame(rows)
            st.dataframe(export_df, use_container_width=True, hide_index=True)
            csv_bytes = export_df.to_csv(index=False).encode()
            analysis_name = st.session_state.get("analysis_name", "analysis")
            st.download_button(
                "Download CSV",
                data=csv_bytes,
                file_name=f"{analysis_name}_mimo_results.csv",
                mime="text/csv",
            )
