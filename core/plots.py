from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.spectral import compute_fft, compute_spectral_quantities

_eps = np.finfo(float).tiny


def fft_subplot(
    df_proc: pd.DataFrame,
    channels: list[str],
    fs: float,
    fmax: float,
) -> go.Figure:
    """Stacked magnitude-FFT figure (dB) for the given channels."""
    n_ch = len(channels)
    fig = make_subplots(
        rows=n_ch, cols=1, shared_xaxes=True,
        vertical_spacing=0.04, subplot_titles=channels,
    )
    for i, ch in enumerate(channels):
        if ch not in df_proc.columns:
            continue
        f, F = compute_fft(df_proc[ch].values, fs, "uniform")
        mask = f <= fmax
        fig.add_trace(
            go.Scatter(
                x=f[mask], y=20 * np.log10(np.maximum(np.abs(F[mask]), _eps)),
                mode="lines", line=dict(width=1.5), showlegend=False,
            ),
            row=i + 1, col=1,
        )
        fig.update_yaxes(title_text="|FFT| (dB)", row=i + 1, col=1)
        if i == n_ch - 1:
            fig.update_xaxes(title_text="Frequency (Hz)", row=i + 1, col=1)
    fig.update_layout(height=max(250, 200 * n_ch), margin=dict(t=30, b=50, l=70, r=20))
    return fig


def frf_subplot(
    df_proc: pd.DataFrame,
    input_ch: str,
    output_chs: list[str],
    fs: float,
    fmax: float,
) -> go.Figure:
    """Stacked magnitude + phase FRF figure (H1 estimator, single FFT)."""
    n_rows = len(output_chs) * 2
    titles = []
    for ch in output_chs:
        titles += [f"|H({input_ch}→{ch})| (dB)", f"∠H({input_ch}→{ch}) (°)"]
    fig = make_subplots(
        rows=n_rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.04, subplot_titles=titles,
    )
    f, Sx = compute_fft(df_proc[input_ch].values, fs, "uniform")
    mask = f <= fmax
    for i, ch in enumerate(output_chs):
        if ch not in df_proc.columns:
            continue
        _, Sy = compute_fft(df_proc[ch].values, fs, "uniform")
        H = compute_spectral_quantities(Sx, Sy)["H1"]
        row_m, row_p = i * 2 + 1, i * 2 + 2
        fig.add_trace(
            go.Scatter(
                x=f[mask], y=20 * np.log10(np.maximum(np.abs(H[mask]), _eps)),
                mode="lines", line=dict(width=1.5), showlegend=False,
            ),
            row=row_m, col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=f[mask], y=np.degrees(np.angle(H[mask])),
                mode="lines", line=dict(width=1.5), showlegend=False,
            ),
            row=row_p, col=1,
        )
        fig.update_yaxes(title_text="|H| (dB)", row=row_m, col=1)
        fig.update_yaxes(title_text="Phase (°)", row=row_p, col=1)
        if row_p == n_rows:
            fig.update_xaxes(title_text="Frequency (Hz)", row=row_p, col=1)
    fig.update_layout(height=max(250, 200 * n_rows), margin=dict(t=30, b=50, l=70, r=20))
    return fig
