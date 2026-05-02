import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.sysid import (
    build_stability_table,
    cmif_peak_estimates,
    compute_cmif,
    extract_residues,
    modal_fit_nmse,
    poles_from_estimates,
    synthesize_frf,
)

st.set_page_config(page_title="SIMO — System Identification", layout="wide")
st.title("SIMO — System Identification (EMA)")

# ── Guard ─────────────────────────────────────────────────────────────────────
if st.session_state.get("df") is None:
    st.warning("No data loaded. Return to the Landing Page and load a data file.")
    st.stop()

res3 = st.session_state.get("spectral_results")
if res3 is None:
    st.warning(
        "No spectral results found. Visit **Page 3 — Spectral Analysis**, "
        "select output channels, and click **Compute**."
    )
    st.stop()

input_channel: str = st.session_state.get("input_channel", "")
output_channels: list = st.session_state.get("output_channels", [])
sample_rate: float = st.session_state.get("sample_rate", 1.0)

available_outputs = [ch for ch in res3["params"].get("output_channels", [])
                     if ch in res3["channels"]]
freqs: np.ndarray = res3["freqs"]
eps = np.finfo(float).tiny

# ── Layout ────────────────────────────────────────────────────────────────────
ctrl_col, chart_col = st.columns([1, 3])

# ── Controls ──────────────────────────────────────────────────────────────────
with ctrl_col:
    st.subheader("Step 1 — Stability Diagram")

    fit_method = st.radio("Curve fitting method", ["pLSCF", "ERA"],
                          horizontal=True, key="si_method")
    frf_est = st.radio("FRF estimator", ["H1", "H2", "Hv"],
                       horizontal=True, key="si_frf_est")

    sel_outputs = st.multiselect(
        "Output channels", options=available_outputs,
        default=available_outputs, key="si_outputs",
    )

    f_nyq = float(freqs[-1])
    f_step = round(f_nyq / 500, 4) or 0.01
    f_min, f_max = st.slider(
        "Frequency range (Hz)", min_value=0.0, max_value=f_nyq,
        value=(0.0, f_nyq), step=f_step, key="si_frange",
    )

    max_order = st.slider("Max model order", min_value=4, max_value=100,
                          value=40, step=2, key="si_max_order")

    with st.expander("Stability thresholds"):
        df_thr = st.number_input("Δf threshold (%)", value=1.0, step=0.5,
                                 min_value=0.1, key="si_df_thr") / 100.0
        dd_thr = st.number_input("Δξ threshold (%)", value=5.0, step=1.0,
                                 min_value=0.1, key="si_dd_thr") / 100.0
        mac_thr = st.slider("MAC threshold", min_value=0.5, max_value=1.0,
                            value=0.95, step=0.01, key="si_mac_thr")

    build_btn = st.button("Build Stability Diagram", type="primary",
                          use_container_width=True, key="si_build")

    st.divider()
    st.subheader("Step 2 — Mode Specification")

    stab_results = st.session_state.get("si_stability_table")
    cmif_cache = st.session_state.get("si_cmif")

    # Auto-suggest n_modes from green poles in last stability run
    if stab_results is not None:
        green_poles = []
        for row in stab_results:
            for k, s in enumerate(row["stability"]):
                if s == "stable_all":
                    green_poles.append({"fn_hz": float(row["fn"][k]),
                                        "xi_pct": float(row["xi"][k]) * 100.0,
                                        "source": f"order {row['order']}"})
        # Deduplicate by frequency (1 % tolerance)
        deduped: list[dict] = []
        for g in sorted(green_poles, key=lambda x: x["fn_hz"]):
            if not deduped or abs(g["fn_hz"] - deduped[-1]["fn_hz"]) / (g["fn_hz"] + 1e-9) > 0.01:
                deduped.append(g)
        auto_n = max(1, len(deduped))
    else:
        deduped = []
        auto_n = 1

    n_modes = st.number_input("Number of modes", min_value=1, max_value=20,
                              value=auto_n, step=1, key="si_n_modes")

    # Build initial estimates table
    if len(deduped) >= n_modes:
        init_rows = deduped[:n_modes]
    elif len(deduped) > 0:
        # pad with CMIF peaks
        if cmif_cache is not None:
            extra = cmif_peak_estimates(cmif_cache, freqs, n_modes - len(deduped))
            init_rows = deduped + extra
        else:
            init_rows = deduped + [{"fn_hz": 0.0, "xi_pct": 2.0, "source": "manual"}
                                   for _ in range(n_modes - len(deduped))]
    else:
        if cmif_cache is not None:
            init_rows = cmif_peak_estimates(cmif_cache, freqs, n_modes)
        else:
            init_rows = [{"fn_hz": 0.0, "xi_pct": 2.0, "source": "manual"}
                         for _ in range(n_modes)]

    init_df = pd.DataFrame({
        "fn (Hz)": [r["fn_hz"] for r in init_rows[:n_modes]],
        "ξ (%)": [r["xi_pct"] for r in init_rows[:n_modes]],
        "source": [r["source"] for r in init_rows[:n_modes]],
    })

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

    extract_btn = st.button("Extract Mode Shapes", type="secondary",
                            use_container_width=True, key="si_extract")

# ── Build Stability Diagram ───────────────────────────────────────────────────
if build_btn:
    if not sel_outputs:
        st.error("Select at least one output channel.")
        st.stop()

    H_mat = np.column_stack([res3["channels"][ch][frf_est] for ch in sel_outputs])
    mask = (freqs >= f_min) & (freqs <= f_max)
    H_band = H_mat[mask]
    f_band = freqs[mask]

    with st.spinner("Building stability diagram…"):
        table = build_stability_table(
            H_band, f_band, sample_rate,
            max_order=max_order,
            method=fit_method.lower(),
            df_thr=df_thr,
            dd_thr=dd_thr,
            mac_thr=mac_thr,
        )
        cmif_vals = compute_cmif(H_mat)

    st.session_state["si_stability_table"] = table
    st.session_state["si_cmif"] = cmif_vals
    st.session_state["si_H_mat"] = H_mat
    st.session_state["si_freqs_band"] = f_band
    st.session_state["si_sel_outputs"] = sel_outputs
    st.session_state["si_frf_est_used"] = frf_est
    st.session_state.pop("modal_results", None)
    st.rerun()

# ── Extract Mode Shapes ───────────────────────────────────────────────────────
if extract_btn:
    H_mat = st.session_state.get("si_H_mat")
    if H_mat is None:
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
    sel_out = st.session_state.get("si_sel_outputs", sel_outputs)

    with st.spinner("Extracting residues…"):
        residues = extract_residues(H_mat, freqs, poles)
        H_syn = synthesize_frf(freqs, poles, residues)
        nmse = modal_fit_nmse(H_mat, H_syn)

    fn_fit = np.abs(poles.imag) / (2.0 * np.pi)
    xi_fit = -poles.real / (np.abs(poles) + 1e-30)

    st.session_state["modal_results"] = {
        "fn": fn_fit,
        "xi": xi_fit,
        "poles": poles,
        "mode_shapes": residues,       # (n_outputs, n_modes) complex
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

    tab_cmif, tab_stab, tab_shapes, tab_export = st.tabs(
        ["CMIF", "Stability Diagram", "Mode Shapes", "Export"]
    )

    # ── CMIF ──────────────────────────────────────────────────────────────────
    with tab_cmif:
        if not sel_outputs:
            st.info("Select output channels and build the stability diagram.")
        else:
            H_live = np.column_stack([res3["channels"][ch][frf_est]
                                      for ch in sel_outputs if ch in res3["channels"]])
            cmif_live = compute_cmif(H_live) if H_live.ndim == 2 else np.abs(H_live)
            band_mask = (freqs >= f_min) & (freqs <= f_max)
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=freqs[band_mask], y=cmif_live[band_mask], mode="lines",
                line=dict(color="#1f77b4", width=1.5), name="CMIF (σ₁)",
            ))
            fig.update_yaxes(type="log", title_text="CMIF (σ₁)")
            fig.update_xaxes(title_text="Frequency (Hz)", range=[f_min, f_max])
            fig.update_layout(
                height=350, margin=dict(t=30, b=50, l=60, r=20),
                title="Complex Mode Indicator Function",
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Peaks indicate candidate mode locations.")

    # ── Stability Diagram ─────────────────────────────────────────────────────
    with tab_stab:
        if stab_results is None:
            st.info("Click **Build Stability Diagram** to run the analysis.")
        else:
            _style = {
                "new":       dict(color="lightgrey", symbol="circle-open", size=6),
                "stable_f":  dict(color="#1f77b4",   symbol="cross",        size=7),
                "stable_fd": dict(color="#ff7f0e",   symbol="x",            size=7),
                "stable_all":dict(color="#2ca02c",   symbol="star",         size=9),
            }
            _label = {
                "new": "New (o)",
                "stable_f": "Freq stable (f)",
                "stable_fd": "Freq+Damp stable (d)",
                "stable_all": "Fully stable (s)",
            }

            fig = go.Figure()

            # Background CMIF
            band_mask = (freqs >= f_min) & (freqs <= f_max)
            if cmif_vals is not None:
                cmif_norm = cmif_vals / (np.max(cmif_vals) + eps) * (max_order * 0.9)
                fig.add_trace(go.Scatter(
                    x=freqs[band_mask], y=cmif_norm[band_mask], mode="lines",
                    line=dict(color="rgba(150,150,150,0.3)", width=1),
                    name="CMIF (bg)", showlegend=False,
                ))

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
                    fig.add_trace(go.Scatter(
                        x=pts["x"], y=pts["y"], mode="markers",
                        marker=dict(color=st_cfg["color"], symbol=st_cfg["symbol"],
                                    size=st_cfg["size"]),
                        name=_label[cls],
                    ))

            fig.update_xaxes(title_text="Natural Frequency (Hz)", range=[f_min, f_max])
            fig.update_yaxes(title_text="Model Order")
            fig.update_layout(
                height=500,
                margin=dict(t=30, b=50, l=60, r=20),
                legend=dict(orientation="h", y=-0.12),
                title=f"Stability Diagram — {fit_method}",
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
            residues = modal_res["mode_shapes"]   # (n_out, n_modes)
            H_meas = modal_res["H_measured"]       # (n_freqs, n_out)
            H_syn = modal_res["H_synthesis"]
            nmse = modal_res["nmse"]
            out_chs = modal_res["output_channels"]
            n_modes_fit = len(fn_fit)
            n_out_fit = len(out_chs)

            # Summary table
            summary_rows = []
            for m in range(n_modes_fit):
                row: dict = {"Mode": m + 1, "fn (Hz)": round(float(fn_fit[m]), 4),
                             "ξ (%)": round(float(xi_fit[m]) * 100, 3)}
                for o, ch in enumerate(out_chs):
                    row[f"|φ| {ch}"] = round(float(np.abs(residues[o, m])), 6)
                    row[f"∠φ {ch} (°)"] = round(float(np.degrees(np.angle(residues[o, m]))), 2)
                summary_rows.append(row)
            st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

            # Individual modal FRF contributions
            show_modal = st.checkbox("Show individual modal contributions", value=False,
                                     key="si_show_modal")

            all_freqs = modal_res["freqs"]
            band_mask = (all_freqs >= f_min) & (all_freqs <= f_max)
            freqs_plot = all_freqs[band_mask]
            omega = 2.0 * np.pi * freqs_plot

            # Stacked FRF overlay plots (magnitude + phase per output channel)
            n_rows_fig = 2 * n_out_fit
            titles = []
            for ch in out_chs:
                titles += [f"|H| — {ch} (dB)", f"∠H — {ch} (°)"]

            fig = make_subplots(rows=n_rows_fig, cols=1, shared_xaxes=True,
                                vertical_spacing=0.04, subplot_titles=titles)

            def _color(i): return f"hsl({(i * 47) % 360}, 65%, 50%)"

            for o, ch in enumerate(out_chs):
                row_mag = 2 * o + 1
                row_ph = 2 * o + 2
                color = _color(o + 1)

                H_m = H_meas[band_mask, o]
                H_s = H_syn[band_mask, o]

                fig.add_trace(go.Scatter(
                    x=freqs_plot, y=20 * np.log10(np.maximum(np.abs(H_m), eps)),
                    mode="lines", name=f"Measured — {ch}",
                    line=dict(color=color, width=1.5),
                    showlegend=(o == 0),
                ), row=row_mag, col=1)
                fig.add_trace(go.Scatter(
                    x=freqs_plot, y=20 * np.log10(np.maximum(np.abs(H_s), eps)),
                    mode="lines", name="Synthesised",
                    line=dict(color="red", width=1.5, dash="dash"),
                    showlegend=(o == 0),
                ), row=row_mag, col=1)

                fig.add_trace(go.Scatter(
                    x=freqs_plot, y=np.degrees(np.angle(H_m)),
                    mode="lines", name=f"Measured — {ch}",
                    line=dict(color=color, width=1.5), showlegend=False,
                ), row=row_ph, col=1)
                fig.add_trace(go.Scatter(
                    x=freqs_plot, y=np.degrees(np.angle(H_s)),
                    mode="lines", name="Synthesised",
                    line=dict(color="red", width=1.5, dash="dash"), showlegend=False,
                ), row=row_ph, col=1)

                if show_modal:
                    for m in range(n_modes_fit):
                        pole = poles_fit[m]
                        res_m = residues[o, m]
                        H_mode = (res_m / (1j * omega - pole)
                                  + res_m.conj() / (1j * omega - pole.conj()))
                        fig.add_trace(go.Scatter(
                            x=freqs_plot,
                            y=20 * np.log10(np.maximum(np.abs(H_mode), eps)),
                            mode="lines",
                            name=f"Mode {m+1} — {ch}",
                            line=dict(dash="dot", width=1),
                            showlegend=(o == 0),
                        ), row=row_mag, col=1)

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
                row = {"mode": m + 1,
                       "fn_hz": round(float(fn_fit[m]), 4),
                       "xi_pct": round(float(xi_fit[m]) * 100, 3)}
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
