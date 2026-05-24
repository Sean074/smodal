from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.mimo import compute_mimo_cmif, compute_mimo_frfs


def test_compute_mimo_cmif_shape():
    rng = np.random.default_rng(0)
    n_freqs, n_out = 100, 3
    H = rng.standard_normal((n_freqs, n_out * 2)) + 1j * rng.standard_normal((n_freqs, n_out * 2))
    sv = compute_mimo_cmif(H, n_out)
    assert sv.shape == (n_freqs, 2)


def test_compute_mimo_cmif_nonnegative():
    rng = np.random.default_rng(1)
    n_freqs, n_out = 50, 2
    H = rng.standard_normal((n_freqs, n_out * 2)) + 1j * rng.standard_normal((n_freqs, n_out * 2))
    sv = compute_mimo_cmif(H, n_out)
    assert np.all(sv >= 0.0)


def test_compute_mimo_frfs_empty_outputs_raises():
    n = 128
    t = np.linspace(0, 1, n)
    df = pd.DataFrame({"time": t, "x": np.ones(n), "ch1": np.ones(n)})
    with pytest.raises(ValueError, match="sel_outputs must not be empty"):
        compute_mimo_frfs(df, df, "x", "x", [], fs=128.0, frf_method="Welch", frf_est="H1")
