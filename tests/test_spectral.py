from __future__ import annotations

import numpy as np

from core.spectral import (
    compute_fft,
    compute_spectral_quantities,
    compute_welch_quantities,
    compute_output_spectral_matrix,
)


def test_compute_fft_peak_at_known_frequency(sine_signal):
    fs = 1000.0
    freqs, fft_c = compute_fft(sine_signal, fs, window="hanning")
    peak_idx = int(np.argmax(np.abs(fft_c)))
    freq_resolution = fs / len(sine_signal)
    assert abs(freqs[peak_idx] - 10.0) <= freq_resolution


def test_compute_fft_uniform_window(sine_signal):
    fs = 1000.0
    freqs, fft_c = compute_fft(sine_signal, fs, window="uniform")
    peak_idx = int(np.argmax(np.abs(fft_c)))
    freq_resolution = fs / len(sine_signal)
    assert abs(freqs[peak_idx] - 10.0) <= freq_resolution


def test_compute_spectral_quantities_identity(sine_signal):
    fs = 1000.0
    _, fft_c = compute_fft(sine_signal, fs)
    res = compute_spectral_quantities(fft_c, fft_c)
    np.testing.assert_allclose(np.abs(res["H1"]), 1.0, atol=1e-6)
    np.testing.assert_allclose(res["gamma2"], 1.0, atol=1e-6)


def test_compute_spectral_quantities_zero_input(sine_signal):
    fs = 1000.0
    _, fft_c = compute_fft(sine_signal, fs)
    zeros = np.zeros_like(fft_c)
    res = compute_spectral_quantities(zeros, fft_c)
    # H1 divides by Gxx_safe (clamped to eps), so it stays finite when Sx=0.
    # gamma2 and H2 are not guaranteed finite when power is zero at a bin
    # (eps*eps underflows), so we only assert the guarded quantity.
    assert np.all(np.isfinite(res["H1"]))


def test_compute_welch_quantities_returns_expected_keys(sine_signal):
    fs = 1000.0
    res = compute_welch_quantities(sine_signal, sine_signal, fs, nperseg=256, noverlap=128)
    for key in ("H1", "H2", "Hv", "gamma2", "freqs"):
        assert key in res


def test_compute_output_spectral_matrix_shape():
    rng = np.random.default_rng(0)
    fs, n_out, n_samples = 200.0, 3, 1000
    signals = rng.standard_normal((n_samples, n_out))
    freqs, Syy = compute_output_spectral_matrix(signals, fs, nperseg=128, noverlap=64)
    assert Syy.shape == (len(freqs), n_out, n_out)


def test_compute_output_spectral_matrix_conjugate_symmetry():
    rng = np.random.default_rng(1)
    fs, n_out = 200.0, 3
    signals = rng.standard_normal((1000, n_out))
    freqs, Syy = compute_output_spectral_matrix(signals, fs, nperseg=128, noverlap=64)
    for k in range(len(freqs)):
        np.testing.assert_allclose(Syy[k], Syy[k].conj().T, atol=1e-10)
