"""Smoke tests for core.plots.

`plots.py` builds Plotly figures for FFT and FRF displays. These tests don't
inspect rendered visuals — they verify the public functions accept the
documented inputs, return a Plotly Figure, and lay out the expected number of
subplots. Enough to catch accidental import breakage or API drift.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from core.plots import fft_subplot, frf_subplot


@pytest.fixture
def two_channel_df() -> tuple[pd.DataFrame, float]:
    """Two channels: 10 Hz sine (input) and 25 Hz sine (output), 1 s at 1 kHz."""
    fs = 1000.0
    t = np.arange(0.0, 1.0, 1.0 / fs)
    df = pd.DataFrame(
        {
            "time": t,
            "in": np.sin(2 * np.pi * 10.0 * t),
            "out": np.sin(2 * np.pi * 25.0 * t),
        }
    )
    return df, fs


def test_fft_subplot_returns_figure(two_channel_df):
    df, fs = two_channel_df
    fig = fft_subplot(df, channels=["in", "out"], fs=fs, fmax=100.0)
    assert isinstance(fig, go.Figure)
    # One trace per channel
    assert len(fig.data) == 2


def test_fft_subplot_ignores_missing_channel(two_channel_df):
    """A channel name not in the DataFrame should be silently skipped."""
    df, fs = two_channel_df
    fig = fft_subplot(df, channels=["in", "not_a_channel"], fs=fs, fmax=100.0)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1


def test_frf_subplot_returns_figure(two_channel_df):
    df, fs = two_channel_df
    fig = frf_subplot(df, input_ch="in", output_chs=["out"], fs=fs, fmax=100.0)
    assert isinstance(fig, go.Figure)
    # One output channel -> magnitude + phase = 2 traces
    assert len(fig.data) == 2


def test_frf_subplot_handles_multiple_outputs(two_channel_df):
    df, fs = two_channel_df
    # Duplicate the output channel under a second name to get two outputs
    df = df.assign(out2=df["out"])
    fig = frf_subplot(df, input_ch="in", output_chs=["out", "out2"], fs=fs, fmax=100.0)
    assert isinstance(fig, go.Figure)
    # Two output channels -> 2 * (mag + phase) = 4 traces
    assert len(fig.data) == 4
