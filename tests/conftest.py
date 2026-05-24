from __future__ import annotations

import pathlib

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def sine_signal() -> np.ndarray:
    """Single 10 Hz sinusoid, 2 s at 1 kHz."""
    freq, fs, duration = 10.0, 1000.0, 2.0
    t = np.arange(0, duration, 1.0 / fs)
    return np.sin(2 * np.pi * freq * t)


@pytest.fixture
def sdof_frf():
    """Analytic SDOF FRF at fn=10 Hz, xi=3 %.

    Returns (freqs, H, fn, xi) where H is (n_freqs, 1) complex.
    """
    fn, xi = 10.0, 0.03
    freqs = np.linspace(0.5, 50.0, 2000)
    wn = 2.0 * np.pi * fn
    w = 2.0 * np.pi * freqs
    H = (1.0 / (wn**2 - w**2 + 2j * xi * wn * w))[:, np.newaxis]
    return freqs, H, fn, xi


@pytest.fixture
def sample_df():
    """DataFrame loaded from data/input/sample_3ch.csv."""
    from core.data_loader import load_csv

    df, err = load_csv(str(ROOT / "data" / "input" / "sample_3ch.csv"))
    assert err is None, f"sample_df fixture: {err}"
    return df
