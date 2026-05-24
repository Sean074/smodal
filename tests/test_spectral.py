from __future__ import annotations

import numpy as np
from scipy.signal import get_window

from core.spectral import (
    WINDOW_SCIPY_NAMES,
    compute_fft,
    compute_output_spectral_matrix,
    compute_spectral_quantities,
    compute_welch_quantities,
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
    for key in ("H1", "H2", "Hv", "gamma2"):
        assert np.all(np.isfinite(res[key])), f"{key} contains non-finite values for zero input"


def test_compute_fft_amplitude_correction():
    """After one-sided correction, |F[peak]| / N should equal the sine amplitude within 1%."""
    A = 2.0
    fs, duration, freq = 1000.0, 2.0, 10.0
    t = np.arange(0, duration, 1.0 / fs)
    signal = A * np.sin(2 * np.pi * freq * t)
    n = len(signal)
    _, fft_c = compute_fft(signal, fs, window="uniform")
    peak_idx = int(np.argmax(np.abs(fft_c)))
    assert abs(np.abs(fft_c[peak_idx]) / n - A) / A < 0.01


def test_single_fft_psd_hann_window_normalization():
    """Hann-windowed single-FFT PSD integrates to signal variance within 2%."""
    fs = 1000.0
    N = 1000  # Δf = 1 Hz; f0 = 100 Hz lands exactly on bin k0 = 100
    t = np.arange(N) / fs
    A = 2.0
    sig = A * np.sin(2 * np.pi * 100.0 * t)
    _, Sx = compute_fft(sig, fs, window="hanning")
    Gxx = compute_spectral_quantities(Sx, Sx)["Gxx"]
    scipy_win = WINDOW_SCIPY_NAMES.get("hanning", "boxcar")
    win_arr = get_window(scipy_win, N)
    W2 = float(np.sum(win_arr**2))
    psd = Gxx / (2.0 * fs * W2)
    power_est = float(np.sum(psd) * (fs / N))
    assert abs(power_est - A**2 / 2) / (A**2 / 2) < 0.02


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
