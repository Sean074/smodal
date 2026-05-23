from __future__ import annotations

import numpy as np

from core.mimo import compute_mimo_cmif


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
