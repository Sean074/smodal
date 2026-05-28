from __future__ import annotations

import pathlib

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def synthetic_modal_results():
    """Minimal valid modal_results dict for Pages 7–8 smoke tests.

    Shapes match what SIMO writes: fn/xi as 1-D numpy arrays,
    mode_shapes as (n_out, n_modes) complex array.
    Channel names match sample_3ch.csv so the MAC mapping UI renders correctly.
    """
    n_out, n_modes, n_freqs = 2, 2, 200
    return {
        "fn": np.array([10.0, 25.0]),
        "xi": np.array([0.03, 0.05]),
        "poles": np.array([-1.885 + 62.83j, -7.854 + 157.08j]),
        "mode_shapes": np.ones((n_out, n_modes), dtype=complex),
        "output_channels": ["acc_1", "acc_2"],
        "freqs": np.linspace(0, 500, n_freqs),
        "H_measured": np.ones((n_freqs, n_out), dtype=complex),
        "H_synthesis": np.ones((n_freqs, n_out), dtype=complex),
        "nmse": {"acc_1": 0.01, "acc_2": 0.01},
    }


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
