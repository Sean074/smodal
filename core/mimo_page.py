"""MIMO EMA page logic — called by pages/5_MIMO.py driver."""

import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core.data_loader import compute_sample_rate, load_csv
from core.ema_charts import (
    coherence_gate_warnings,
    mode_estimates_init_df,
    spectral_tab_content,
    stability_diagram_figure,
    stability_diagram_guide,
)
from core.ema_pipeline import extract_modes, nmse_quality_label
from core.mimo import compute_mimo_cmif, compute_mimo_frfs
from core.plots import fft_subplot, frf_subplot
from core.preprocess import trim_and_filter
from core.spectral import compute_fft, compute_spectral_quantities, compute_welch_quantities
from core.sysid import build_stability_table, deduplicate_stable_poles
from core.uff_writer import write_uff58_shapes_mimo

eps = np.finfo(float).tiny


def render() -> None:
    # ── Section A: File loading ──────────────────────────────────────────────────
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

    _mimo_invalidate_keys = [
        "mimo_H_mat", "mimo_freqs", "mimo_freqs_band", "mimo_H_mat_band",
        "mimo_cmif", "mimo_stability_table", "mimo_modal_results",
        "mimo_spectral_channels", "mimo_spectral_freqs", "mimo_frf_method_used",
    ]

    if file_a is not None and st.session_state.get("mimo_file_a_name") != file_a.name:
        df_a, err_a = load_csv(file_a)
        if err_a:
            st.error(f"Run A: {err_a}")
        else:
            st.session_state["mimo_run_a_df"] = df_a
            st.session_state["mimo_sample_rate"] = float(compute_sample_rate(df_a["time"].values))
            st.session_state["mimo_file_a_name"] = file_a.name
            for k in _mimo_invalidate_keys:
                st.session_state.pop(k, None)

    if file_b is not None and st.session_state.get("mimo_file_b_name") != file_b.name:
        df_b, err_b = load_csv(file_b)
        if err_b:
            st.error(f"Run B: {err_b}")
        else:
            st.session_state["mimo_run_b_df"] = df_b
            st.session_state["mimo_file_b_name"] = file_b.name
            for k in _mimo_invalidate_keys:
                st.session_state.pop(k, None)
            fs_b = float(compute_sample_rate(df_b["time"].values))
            fs_a = st.session_state.get("mimo_sample_rate")
            if fs_a is not None and abs(fs_b - fs_a) / (fs_a + 1e-9) > 0.01:
                st.error(
                    f"Run B sample rate ({fs_b:.1f} Hz) differs from Run A ({fs_a:.1f} Hz) by more than 1 %. "
                    "FRF estimates will be unreliable. Re-upload files with matching sample rates."
                )
                st.stop()

    run_a = st.session_state.get("mimo_run_a_df")
    run_b = st.session_state.get("mimo_run_b_df")

    if run_a is None or run_b is None:
        st.info(
            "Upload both **Run A** (in-phase) and **Run B** (out-of-phase) CSV files to begin."
        )
        st.stop()

    fs: float = st.session_state.get("mimo_sample_rate", 1.0)
    common_cols = sorted(set(run_a.columns) & set(run_b.columns) - {"time"})
    if not common_cols:
        st.error(
            "Run A and Run B share no common data channels. "
            "Ensure both files use the same column names."
        )
        st.stop()

    # ── Channel assignment ───────────────────────────────────────────────────────
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

    # ── Section B: Pre-processing expander ──────────────────────────────────────
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
        st.caption(f"Time window: {t_min:.3f}–{t_max:.3f} s  ·  ≈{n_samples} samples  ·  {filt_label}")

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
                    ra_filt = trim_and_filter(
                        run_a, t_min, t_max, filter_type, filter_order, cutoff_params, fs
                    )
                    rb_filt = trim_and_filter(
                        run_b, t_min, t_max, filter_type, filter_order, cutoff_params, fs
                    )
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

    def _preview_proc(run_df):
        _cutoffs_ok = not (
            isinstance(cutoff_params, list)
            and len(cutoff_params) == 2
            and cutoff_params[0] >= cutoff_params[1]
        )
        return trim_and_filter(
            run_df,
            t_min,
            t_max,
            filter_type if _cutoffs_ok else "None",
            filter_order,
            cutoff_params if _cutoffs_ok else None,
            fs,
        )

    # ── Section C: FFT Preview expander ─────────────────────────────────────────
    with st.expander("FFT preview (optional — input & output channels, trimmed/filtered)"):
        fft_fmax = st.slider(
            "Max frequency (Hz)",
            min_value=0.0,
            max_value=float(fs / 2),
            value=float(fs / 2),
            key="mimo_fft_prev_fmax",
        )
        col_ffta, col_fftb = st.columns(2)
        ra_fft = _preview_proc(run_a)
        rb_fft = _preview_proc(run_b)
        with col_ffta:
            st.markdown("**Run A**")
            st.plotly_chart(
                fft_subplot(ra_fft, [input_a] + sel_outputs, fs, fft_fmax),
                use_container_width=True,
                key="mimo_fft_prev_a",
            )
        with col_fftb:
            st.markdown("**Run B**")
            st.plotly_chart(
                fft_subplot(rb_fft, [input_b] + sel_outputs, fs, fft_fmax),
                use_container_width=True,
                key="mimo_fft_prev_b",
            )

    # ── Section D: FRF Preview expander ─────────────────────────────────────────
    with st.expander("FRF preview (optional — H1 estimator, single FFT, trimmed/filtered)"):
        frf_fmax = st.slider(
            "Max frequency (Hz)",
            min_value=0.0,
            max_value=float(fs / 2),
            value=float(fs / 2),
            key="mimo_frf_prev_fmax",
        )
        col_frfa, col_frfb = st.columns(2)
        ra_frf = _preview_proc(run_a)
        rb_frf = _preview_proc(run_b)
        with col_frfa:
            st.markdown("**Run A**")
            st.plotly_chart(
                frf_subplot(ra_frf, input_a, sel_outputs, fs, frf_fmax),
                use_container_width=True,
                key="mimo_frf_prev_a",
            )
        with col_frfb:
            st.markdown("**Run B**")
            st.plotly_chart(
                frf_subplot(rb_frf, input_b, sel_outputs, fs, frf_fmax),
                use_container_width=True,
                key="mimo_frf_prev_b",
            )

    # ── Layout ──────────────────────────────────────────────────────────────────
    ctrl_col, chart_col = st.columns([1, 3])

    # ── Controls ────────────────────────────────────────────────────────────────
    with ctrl_col:
        st.subheader("Step 1 — Stability Diagram")

        frf_method = st.radio(
            "FRF method", ["Welch", "Single FFT"], horizontal=True, key="mimo_frf_method"
        )

        n_seg, ovlp_pct, welch_win = 8, 50, "hann"
        if frf_method == "Welch":
            n_seg = st.selectbox(
                "Segments", options=[4, 8, 16, 32, 64], index=1, key="mimo_segments"
            )
            ovlp_pct = st.selectbox(
                "Overlap (%)", options=[0, 25, 50, 75], index=2, key="mimo_overlap"
            )
            welch_win = st.selectbox(
                "Window", options=["hann", "flattop", "boxcar"], key="mimo_welch_win"
            )
            nperseg_preview = max(4, n_samples // n_seg)
            st.caption(
                f"Δf ≈ {fs / nperseg_preview:.3f} Hz · ~{nperseg_preview} samples/segment"
            )

        frf_est = st.radio(
            "FRF estimator", ["H1", "H2", "Hv"], horizontal=True, key="mimo_frf_est"
        )

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

        coh_red, coh_yellow = coherence_gate_warnings(
            st.session_state.get("mimo_spectral_channels"),
            st.session_state.get("mimo_spectral_freqs"),
            st.session_state.get("mimo_frf_method_used"),
            f_min_hz,
            f_max_hz,
        )

        max_order = st.slider(
            "Max model order", min_value=4, max_value=100, value=40, step=2, key="mimo_max_order"
        )

        _mimo_freqs_check = st.session_state.get("mimo_freqs")
        if _mimo_freqs_check is not None:
            _n_band = int(
                np.sum((_mimo_freqs_check >= f_min_hz) & (_mimo_freqs_check <= f_max_hz))
            )
            if _n_band > 0 and max_order > _n_band // 4:
                st.warning(
                    f"Max model order ({max_order}) exceeds ¼ of the frequency lines in the "
                    f"analysis band ({_n_band} lines → recommended ≤ {_n_band // 4}). "
                    "Overdetermined models produce spurious computational poles."
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
                "MAC threshold",
                min_value=0.5,
                max_value=1.0,
                value=0.95,
                step=0.01,
                key="mimo_mac_thr",
            )

        build_btn = st.button(
            "Build Stability Diagram", type="primary", use_container_width=True, key="mimo_build"
        )

        st.divider()
        st.subheader("Step 2 — Mode Specification")

        stab_results = st.session_state.get("mimo_stability_table")
        cmif_cache = st.session_state.get("mimo_cmif")
        freqs_cache = st.session_state.get("mimo_freqs")

        deduped = deduplicate_stable_poles(stab_results) if stab_results is not None else []
        auto_n = max(1, len(deduped))
        n_modes = st.number_input(
            "Number of modes", min_value=1, max_value=20, value=auto_n, step=1, key="mimo_n_modes"
        )
        init_df = mode_estimates_init_df(deduped, cmif_cache, freqs_cache, n_modes)

        estimates_df = st.data_editor(
            init_df,
            column_config={
                "fn (Hz)": st.column_config.NumberColumn(min_value=0.0, format="%.3f"),
                "ξ (%)": st.column_config.NumberColumn(
                    min_value=0.01, max_value=30.0, format="%.2f"
                ),
                "source": st.column_config.TextColumn(disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="mimo_estimates",
        )

        extract_btn = st.button(
            "Extract Mode Shapes", type="secondary", use_container_width=True, key="mimo_extract"
        )

    # ── Build Stability Diagram ──────────────────────────────────────────────────
    if build_btn:
        if not sel_outputs:
            st.error("Select at least one output channel.")
            st.stop()
        if isinstance(cutoff_params, list) and len(cutoff_params) == 2:
            if cutoff_params[0] >= cutoff_params[1]:
                st.error("Filter: low cutoff must be less than high cutoff.")
                st.stop()
        with st.spinner("Pre-processing…"):
            run_a_proc = trim_and_filter(
                run_a, t_min, t_max, filter_type, filter_order, cutoff_params, fs
            )
            run_b_proc = trim_and_filter(
                run_b, t_min, t_max, filter_type, filter_order, cutoff_params, fs
            )
        with st.spinner("Computing FRFs…"):
            H_stacked, freqs_full = compute_mimo_frfs(
                run_a_proc,
                run_b_proc,
                input_a,
                input_b,
                sel_outputs,
                fs,
                frf_method,
                frf_est,
                n_seg,
                ovlp_pct,
                welch_win,
            )
        _spectral_keys = ("Gxx", "Gyy", "Gxy", "Gyx", "H1", "H2", "Hv", "gamma2")
        _mimo_all_res: dict = {}
        if frf_method == "Welch":
            _n_proc_m = len(run_a_proc)
            _nperseg_m = max(4, _n_proc_m // n_seg)
            _noverlap_m = int(_nperseg_m * ovlp_pct / 100)
            _last_m: dict = {}
            for ch in sel_outputs:
                _last_m = compute_welch_quantities(
                    run_a_proc[input_a].values,
                    run_a_proc[ch].values,
                    fs,
                    _nperseg_m,
                    _noverlap_m,
                    welch_win,
                )
                _mimo_all_res[ch] = {k: _last_m[k] for k in _spectral_keys}
            _mimo_spectral_freqs = _last_m["freqs"]
            _mimo_frf_method_used = "Welch"
        else:
            _, _Sx_m = compute_fft(run_a_proc[input_a].values, fs, window="uniform")
            for ch in sel_outputs:
                _, _Sy_m = compute_fft(run_a_proc[ch].values, fs, window="uniform")
                _res_m = compute_spectral_quantities(_Sx_m, _Sy_m)
                _mimo_all_res[ch] = {k: _res_m[k] for k in _spectral_keys}
            _mimo_spectral_freqs = freqs_full
            _mimo_frf_method_used = "Single FFT"
        with st.spinner("Building stability diagram…"):
            band_mask = (freqs_full >= f_min_hz) & (freqs_full <= f_max_hz)
            H_band = H_stacked[band_mask]
            freqs_band = freqs_full[band_mask]
            if len(freqs_band) == 0:
                st.error(
                    "No frequency points in the selected range. Widen the frequency range."
                )
                st.stop()
            cmif_vals = compute_mimo_cmif(H_stacked, n_out)
            with warnings.catch_warnings(record=True) as _stab_warns:
                warnings.simplefilter("always")
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
        if any(issubclass(w.category, RuntimeWarning) for w in _stab_warns):
            st.warning(
                "Residue fit was ill-conditioned at one or more model orders. "
                "Consider widening the frequency band or reducing max model order."
            )
        st.session_state.update(
            {
                "mimo_H_mat": H_stacked,
                "mimo_freqs": freqs_full,
                "mimo_freqs_band": freqs_band,
                "mimo_H_mat_band": H_band,
                "mimo_cmif": cmif_vals,
                "mimo_stability_table": table,
                "mimo_sel_outputs": sel_outputs,
                "mimo_n_out": n_out,
                "mimo_frf_est_used": frf_est,
                "mimo_spectral_channels": _mimo_all_res,
                "mimo_spectral_freqs": _mimo_spectral_freqs,
                "mimo_frf_method_used": _mimo_frf_method_used,
            }
        )
        st.session_state.pop("mimo_modal_results", None)
        st.rerun()

    # ── Extract Mode Shapes ──────────────────────────────────────────────────────
    if extract_btn:
        H_mat_band = st.session_state.get("mimo_H_mat_band")
        freqs_ext = st.session_state.get("mimo_freqs_band")
        H_mat_full = st.session_state.get("mimo_H_mat")
        freqs_full = st.session_state.get("mimo_freqs")
        n_out_ext: int = st.session_state.get("mimo_n_out", n_out)
        sel_out_ext: list = st.session_state.get("mimo_sel_outputs", sel_outputs)
        if H_mat_band is None or freqs_ext is None or H_mat_full is None or freqs_full is None:
            st.error("Build the stability diagram first.")
            st.stop()
        fn_arr = estimates_df["fn (Hz)"].values.astype(float)
        xi_arr = estimates_df["ξ (%)"].values.astype(float) / 100.0
        valid = (fn_arr > 0) & (xi_arr > 0)
        fn_arr, xi_arr = fn_arr[valid], xi_arr[valid]
        if len(fn_arr) == 0:
            st.error("No valid mode estimates. Enter fn > 0 and ξ > 0.")
            st.stop()
        with st.spinner("Extracting residues…"):
            result = extract_modes(H_mat_band, freqs_ext, freqs_full, fn_arr, xi_arr)
        poles = result["poles"]
        fn_fit = result["fn_hz"]
        xi_fit = result["xi"]
        residues = result["residues"]
        H_syn = result["H_synthesis_full"]
        nmse = result["nmse"]
        if len(freqs_ext) < 2 * len(poles):
            st.warning(
                f"Frequency band has {len(freqs_ext)} lines but {2 * len(poles)} are needed "
                f"for {len(poles)} modes — residue fit may be ill-conditioned."
            )
        res_A = residues[:n_out_ext, :]
        res_B = residues[n_out_ext:, :]
        r3d = np.stack([res_A, res_B], axis=1)
        n_modes_fit = residues.shape[1]
        mode_types = [
            "S" if np.linalg.norm(r3d[:, 0, m]) >= np.linalg.norm(r3d[:, 1, m]) else "A"
            for m in range(n_modes_fit)
        ]
        st.session_state["mimo_modal_results"] = {
            "fn": fn_fit,
            "xi": xi_fit,
            "poles": poles,
            "mode_shapes": r3d,
            "residues_flat": residues,
            "mode_types": mode_types,
            "output_channels": sel_out_ext,
            "freqs": freqs_full,
            "H_measured": H_mat_full,
            "H_synthesis": H_syn,
            "nmse": nmse,
        }
        st.rerun()

    # ── Charts ───────────────────────────────────────────────────────────────────
    with chart_col:
        cmif_vals = st.session_state.get("mimo_cmif")
        freqs_full_c = st.session_state.get("mimo_freqs")
        stab_results = st.session_state.get("mimo_stability_table")
        modal_res = st.session_state.get("mimo_modal_results")

        tab_cmif, tab_stab, tab_shapes, tab_spectral, tab_export = st.tabs(
            ["CMIF", "Stability Diagram", "Mode Shapes", "Spectral", "Export"]
        )

        # ── CMIF ────────────────────────────────────────────────────────────────
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
                for f_lo, f_hi in coh_yellow:
                    fig.add_vrect(
                        x0=f_lo, x1=f_hi,
                        fillcolor="rgba(255,200,0,0.15)", layer="below", line_width=0,
                    )
                for f_lo, f_hi in coh_red:
                    fig.add_vrect(
                        x0=f_lo, x1=f_hi,
                        fillcolor="rgba(220,50,50,0.20)", layer="below", line_width=0,
                    )
                st.plotly_chart(fig, use_container_width=True)
                st.caption("σ₁ shows all modes. σ₂ helps resolve repeated or closely-spaced modes.")

        # ── Stability Diagram ────────────────────────────────────────────────────
        with tab_stab:
            if stab_results is None:
                st.info("Click **Build Stability Diagram** to run the analysis.")
            else:
                fig = stability_diagram_figure(
                    stab_results,
                    cmif_vals,
                    freqs_full_c,
                    f_min_hz,
                    f_max_hz,
                    max_order,
                    coh_red,
                    coh_yellow,
                    eps,
                    title="Stability Diagram — pLSCF (Multi-Reference)",
                )
                st.plotly_chart(fig, use_container_width=True)
                stability_diagram_guide()

        # ── Mode Shapes ──────────────────────────────────────────────────────────
        with tab_shapes:
            if modal_res is None:
                st.info("Specify modes and click **Extract Mode Shapes**.")
            else:
                fn_fit = modal_res["fn"]
                xi_fit = modal_res["xi"]
                poles_fit = modal_res["poles"]
                r3d = modal_res["mode_shapes"]
                residues_flat = modal_res["residues_flat"]
                H_meas = modal_res["H_measured"]
                H_syn_res = modal_res["H_synthesis"]
                nmse = modal_res["nmse"]
                out_chs = modal_res["output_channels"]
                mode_types = modal_res["mode_types"]
                n_modes_fit = len(fn_fit)
                n_out_fit = len(out_chs)

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
                                fig.update_xaxes(
                                    title_text="Frequency (Hz)", row=row_ph, col=1
                                )
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

                with st.expander("Fit quality (NMSE per channel)"):
                    st.caption(
                        "NMSE = 10 log₁₀(error energy / signal energy). Lower (more negative) is better. "
                        "−20 dB means the error is 1 % of the measured signal energy. "
                        "Scale: Excellent < −30 dB · Good −30 to −20 dB · Acceptable −20 to −10 dB · Poor > −10 dB"
                    )
                    nmse_rows = []
                    for o, ch in enumerate(out_chs):
                        nmse_rows.append(
                            {
                                "Channel": ch,
                                "Run": "A",
                                "NMSE (dB)": round(float(nmse[o]), 2),
                                "Quality": nmse_quality_label(float(nmse[o])),
                            }
                        )
                        nmse_rows.append(
                            {
                                "Channel": ch,
                                "Run": "B",
                                "NMSE (dB)": round(float(nmse[n_out_fit + o]), 2),
                                "Quality": nmse_quality_label(float(nmse[n_out_fit + o])),
                            }
                        )
                    st.dataframe(pd.DataFrame(nmse_rows), use_container_width=True, hide_index=True)

        # ── Spectral ─────────────────────────────────────────────────────────────
        with tab_spectral:
            spec_chs = st.session_state.get("mimo_spectral_channels")
            spec_freqs = st.session_state.get("mimo_spectral_freqs")
            method_used = st.session_state.get("mimo_frf_method_used")
            if spec_chs is None or spec_freqs is None:
                st.info("Build the stability diagram to populate spectral data.")
            else:
                spectral_tab_content(
                    spec_chs,
                    spec_freqs,
                    method_used,
                    f_min_hz,
                    f_max_hz,
                    eps,
                    frf_key="mimo_spec_frf_est",
                    coh_caption="Coherence between Run A input and each output channel.",
                    input_label="Run A Input",
                )

        # ── Export ───────────────────────────────────────────────────────────────
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
                uff_bytes = write_uff58_shapes_mimo(fn_fit, xi_fit, r3d, out_chs, analysis_name)
                st.download_button(
                    "Download UFF58",
                    data=uff_bytes,
                    file_name=f"{analysis_name}_mimo_results.uff",
                    mime="application/octet-stream",
                )
