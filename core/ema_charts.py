"""Shared chart-rendering helpers for SIMO and MIMO EMA pages."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from core.spectral import band_coherence_stats
from core.sysid import cmif_peak_estimates


def coherence_gate_warnings(spec_chs, spec_freqs, frf_method_used, f_min, f_max):
    """Compute coherence shading intervals and display warnings.

    Returns (red_bands, yellow_bands) — lists of (f_lo, f_hi) tuples.
    """
    if spec_chs is None or spec_freqs is None:
        return [], []
    if frf_method_used == "Single FFT":
        st.caption("Coherence shading suppressed — Single FFT coherence is 1.0 everywhere.")
        return [], []
    g2_arrays = [cd["gamma2"] for cd in spec_chs.values()]
    min_len = min(len(g) for g in g2_arrays)
    g2_min = np.min(np.stack([g[:min_len] for g in g2_arrays], axis=0), axis=0)
    freqs_aligned = spec_freqs[:min_len]
    stats_70 = band_coherence_stats(g2_min, freqs_aligned, f_min, f_max, threshold=0.7)
    stats_85 = band_coherence_stats(g2_min, freqs_aligned, f_min, f_max, threshold=0.85)
    if not stats_70["passes"]:
        st.warning(
            f"Low coherence (γ² < 0.7) covers {stats_70['pct_low']:.0%} of the analysis band "
            f"(mean γ² = {stats_70['mean_coh']:.2f}). "
            "Modes extracted here may not reflect physical resonances."
        )
    elif stats_85["pct_low"] > 0:
        st.info(
            f"Moderate coherence (γ² < 0.85) covers {stats_85['pct_low']:.0%} of the analysis band. "
            "Interpret results with care."
        )
    return stats_70["low_bands"], stats_85["low_bands"]


def stability_diagram_figure(
    stab_results,
    cmif_vals,
    freqs,
    f_min,
    f_max,
    max_order,
    coh_red,
    coh_yellow,
    eps,
    title="Stability Diagram — pLSCF",
):
    """Build and return a Plotly stability diagram figure."""
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
    if cmif_vals is not None and freqs is not None:
        bm = (freqs >= f_min) & (freqs <= f_max)
        cmif_norm = cmif_vals[:, 0] / (np.max(cmif_vals[:, 0]) + eps) * (max_order * 0.9)
        fig.add_trace(
            go.Scatter(
                x=freqs[bm],
                y=cmif_norm[bm],
                mode="lines",
                line=dict(color="rgba(150,150,150,0.3)", width=1),
                name="CMIF (bg)",
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
    fig.update_xaxes(title_text="Natural Frequency (Hz)", range=[f_min, f_max])
    fig.update_yaxes(title_text="Model Order")
    fig.update_layout(
        height=500,
        margin=dict(t=30, b=50, l=60, r=20),
        legend=dict(orientation="h", y=-0.12),
        title=title,
    )
    for f_lo, f_hi in coh_yellow:
        fig.add_vrect(x0=f_lo, x1=f_hi, fillcolor="rgba(255,200,0,0.15)", layer="below", line_width=0)
    for f_lo, f_hi in coh_red:
        fig.add_vrect(x0=f_lo, x1=f_hi, fillcolor="rgba(220,50,50,0.20)", layer="below", line_width=0)
    if coh_red:
        fig.add_annotation(
            text="⚠ Low coherence (γ²<0.7)",
            x=0.01,
            y=0.99,
            xref="paper",
            yref="paper",
            showarrow=False,
            font=dict(size=10, color="darkred"),
            bgcolor="rgba(255,240,240,0.8)",
            bordercolor="darkred",
            borderwidth=1,
        )
    return fig


def stability_diagram_guide():
    """Render the stability diagram legend/guide expander."""
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


def spectral_tab_content(
    spec_chs,
    spec_freqs,
    frf_method_used,
    f_min,
    f_max,
    eps,
    frf_key,
    coh_caption=None,
    input_label="Input",
):
    """Render FRF / Coherence / Auto-PSD nested sub-tabs inside an active parent tab."""
    band_mask = (spec_freqs >= f_min) & (spec_freqs <= f_max)
    freqs_sp = spec_freqs[band_mask]
    sub_frf, sub_coh, sub_psd = st.tabs(["FRF", "Coherence", "Auto-PSD"])

    with sub_frf:
        frf_sel = st.radio("FRF estimator", ["H1", "H2", "Hv"], horizontal=True, key=frf_key)
        n_sp = len(spec_chs)
        fig_frf = make_subplots(
            rows=2 * n_sp,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=[t for ch in spec_chs for t in (f"|H| — {ch} (dB)", f"∠H — {ch} (°)")],
        )
        for i, (ch, cd) in enumerate(spec_chs.items()):
            H_sp = cd[frf_sel][band_mask]
            clr = f"hsl({i * 47 % 360},65%,50%)"
            fig_frf.add_trace(
                go.Scatter(
                    x=freqs_sp,
                    y=20 * np.log10(np.maximum(np.abs(H_sp), eps)),
                    mode="lines",
                    name=ch,
                    line=dict(color=clr, width=1.5),
                    showlegend=True,
                ),
                row=2 * i + 1,
                col=1,
            )
            fig_frf.add_trace(
                go.Scatter(
                    x=freqs_sp,
                    y=np.degrees(np.angle(H_sp)),
                    mode="lines",
                    name=ch,
                    line=dict(color=clr, width=1.5),
                    showlegend=False,
                ),
                row=2 * i + 2,
                col=1,
            )
            fig_frf.update_yaxes(title_text="|H| (dB)", row=2 * i + 1, col=1)
            fig_frf.update_yaxes(title_text="Phase (°)", row=2 * i + 2, col=1)
        fig_frf.update_xaxes(
            title_text="Frequency (Hz)", row=2 * n_sp, col=1, range=[f_min, f_max]
        )
        fig_frf.update_layout(
            height=280 * 2 * n_sp,
            margin=dict(t=40, b=60, l=70, r=20),
            legend=dict(orientation="h", y=-0.04),
        )
        st.plotly_chart(fig_frf, use_container_width=True)

    with sub_coh:
        if frf_method_used == "Single FFT":
            st.info("Coherence is 1.0 for a single-realization FFT.")
        else:
            fig_coh = go.Figure()
            for i, (ch, cd) in enumerate(spec_chs.items()):
                fig_coh.add_trace(
                    go.Scatter(
                        x=freqs_sp,
                        y=cd["gamma2"][band_mask],
                        mode="lines",
                        name=ch,
                        line=dict(color=f"hsl({i * 47 % 360},65%,50%)", width=1.5),
                    )
                )
            fig_coh.add_hline(y=0.85, line=dict(color="grey", dash="dash", width=1))
            fig_coh.update_yaxes(title_text="γ²", range=[0, 1.05])
            fig_coh.update_xaxes(title_text="Frequency (Hz)", range=[f_min, f_max])
            fig_coh.update_layout(
                height=350,
                margin=dict(t=30, b=50, l=60, r=20),
                legend=dict(orientation="h", y=-0.15),
            )
            st.plotly_chart(fig_coh, use_container_width=True)
            if coh_caption:
                st.caption(coh_caption)

    with sub_psd:
        first_cd = next(iter(spec_chs.values()))
        n_rows_psd = 1 + len(spec_chs)
        titles_psd = [f"Gxx — {input_label}"] + [f"Gyy — {ch}" for ch in spec_chs]
        fig_psd = make_subplots(
            rows=n_rows_psd,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=titles_psd,
        )
        fig_psd.add_trace(
            go.Scatter(
                x=freqs_sp,
                y=10 * np.log10(np.maximum(first_cd["Gxx"][band_mask], eps)),
                mode="lines",
                name="Gxx",
                line=dict(color="#1f77b4", width=1.5),
                showlegend=False,
            ),
            row=1,
            col=1,
        )
        fig_psd.update_yaxes(title_text="PSD (dB)", row=1, col=1)
        for i, (ch, cd) in enumerate(spec_chs.items()):
            fig_psd.add_trace(
                go.Scatter(
                    x=freqs_sp,
                    y=10 * np.log10(np.maximum(cd["Gyy"][band_mask], eps)),
                    mode="lines",
                    name=ch,
                    line=dict(color=f"hsl({i * 47 % 360},65%,50%)", width=1.5),
                    showlegend=False,
                ),
                row=i + 2,
                col=1,
            )
            fig_psd.update_yaxes(title_text="PSD (dB)", row=i + 2, col=1)
        fig_psd.update_xaxes(
            title_text="Frequency (Hz)", row=n_rows_psd, col=1, range=[f_min, f_max]
        )
        fig_psd.update_layout(
            height=max(300, 200 * n_rows_psd), margin=dict(t=40, b=60, l=70, r=20)
        )
        st.plotly_chart(fig_psd, use_container_width=True)


def mode_estimates_init_df(deduped: list, cmif_cache, freqs_cache, n_modes: int) -> pd.DataFrame:
    """Build the initial mode-estimates DataFrame for the Step 2 data editor.

    Parameters
    ----------
    deduped:
        Pre-computed list of stable-pole dicts (from deduplicate_stable_poles).
    cmif_cache:
        CMIF array (n_freqs, n_sv) or None.
    freqs_cache:
        Frequency array matching cmif_cache, or None.
    n_modes:
        Number of mode rows to generate.
    """
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
            init_rows = [{"fn_hz": 0.0, "xi_pct": 2.0, "source": "manual"} for _ in range(n_modes)]
    return pd.DataFrame(
        {
            "fn (Hz)": [r["fn_hz"] for r in init_rows[:n_modes]],
            "ξ (%)": [r["xi_pct"] for r in init_rows[:n_modes]],
            "source": [r["source"] for r in init_rows[:n_modes]],
        }
    )
