from __future__ import annotations

import numpy as np
import streamlit as st
from scipy.signal import get_window

WINDOW_SCIPY_NAMES = _WINDOW_SCIPY_NAMES = {
    "uniform": "boxcar",
    "hanning": "hann",
    "flattop": "flattop",
    "force": "hann",  # force window is typically a short hann; user may trim later
    "exponential": "exponential",
}


def compute_fft(
    signal: np.ndarray,
    sample_rate: float,
    window: str = "uniform",
) -> tuple[np.ndarray, np.ndarray]:
    """Return (freqs_hz, fft_complex) for a real-valued signal.

    Uses one-sided (rfft) output. The window is applied before the transform.
    """
    n = len(signal)
    scipy_name = _WINDOW_SCIPY_NAMES.get(window, "boxcar")

    if scipy_name == "exponential":
        # scipy exponential window needs a centre argument
        win = get_window(("exponential", None, 1.0 / 8.686), n)
    else:
        win = get_window(scipy_name, n)

    windowed = signal * win
    fft_complex = np.fft.rfft(windowed)
    # One-sided amplitude correction: interior bins carry half the physical amplitude
    fft_complex = fft_complex.copy()
    if n % 2 == 0:
        fft_complex[1:-1] *= 2
    else:
        fft_complex[1:] *= 2
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
    return freqs, fft_complex


def compute_spectral_quantities(Sx: np.ndarray, Sy: np.ndarray) -> dict:
    """Compute single-realization spectral quantities from complex FFT arrays.

    Sx, Sy : complex 1-D arrays (output of np.fft.rfft) for input and output.

    Returns dict with keys:
        Gxx, Gyy             : float64 auto-power spectra
        Gxy, Gyx             : complex128 cross-power spectra (Gxy = E[X* Y], Gyx = conj)
        H1, H2, Hv           : complex128 FRF estimators
        gamma2               : float64 ordinary coherence [0, 1]
    """
    eps = np.finfo(float).tiny
    Gxx = np.real(Sx * np.conj(Sx))
    Gyy = np.real(Sy * np.conj(Sy))
    Gxy = Sy * np.conj(Sx)  # E[X* Y] = G_xy by standard convention
    Gyx = np.conj(Gxy)

    Gxx_safe = np.maximum(Gxx, eps)
    Gyx_safe = np.where(np.abs(Gyx) > eps, Gyx, eps + 0j)

    H1 = Gxy / Gxx_safe

    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        H2 = Gyy / Gyx_safe
        Hv_mag = np.sqrt(np.abs(H1) * np.abs(H2))
        Hv = Hv_mag * np.exp(1j * np.angle(H1))
        gamma2 = np.abs(Gxy) ** 2 / (Gxx_safe * np.maximum(Gyy, eps))

    H2 = np.where(np.isfinite(H2), H2, 0.0 + 0j)
    Hv_mag = np.where(np.isfinite(Hv_mag), Hv_mag, 0.0)
    Hv = np.where(np.isfinite(Hv), Hv, 0.0 + 0j)
    gamma2 = np.where(np.isfinite(gamma2), gamma2, 0.0)

    return dict(Gxx=Gxx, Gyy=Gyy, Gyx=Gyx, Gxy=Gxy, H1=H1, H2=H2, Hv=Hv, gamma2=gamma2)


def compute_psd(
    signal: np.ndarray,
    sample_rate: float,
    nperseg: int,
    noverlap: int,
    window: str = "hann",
) -> tuple[np.ndarray, np.ndarray]:
    """Return (freqs_hz, Pxx) auto-power spectral density via Welch averaging."""
    from scipy.signal import welch

    return welch(signal, fs=sample_rate, window=window, nperseg=nperseg, noverlap=noverlap)


@st.cache_data
def compute_output_spectral_matrix(
    signals: np.ndarray,
    fs: float,
    nperseg: int,
    noverlap: int,
    window: str = "hann",
) -> tuple[np.ndarray, np.ndarray]:
    """Compute the output PSD matrix via Welch-averaged CPSD.

    signals : (n_samples, n_out) array — output-only response channels
    Returns : (freqs (n_freqs,), Syy (n_freqs, n_out, n_out) complex)

    Diagonal entries are real auto-PSDs; off-diagonal are complex CPSDs.
    Conjugate symmetry is enforced: Syy[k, i, j] = conj(Syy[k, j, i]).
    """
    from scipy.signal import csd as scipy_csd
    from scipy.signal import welch

    n_out = signals.shape[1]
    kw = dict(fs=fs, window=window, nperseg=nperseg, noverlap=noverlap)

    freqs, _ = welch(signals[:, 0], **kw)
    n_freqs = len(freqs)
    Syy = np.zeros((n_freqs, n_out, n_out), dtype=complex)

    for i in range(n_out):
        _, Pii = welch(signals[:, i], **kw)
        Syy[:, i, i] = Pii
        for j in range(i + 1, n_out):
            _, Sij = scipy_csd(signals[:, i], signals[:, j], **kw)
            Syy[:, i, j] = Sij
            Syy[:, j, i] = np.conj(Sij)

    return freqs, Syy


@st.cache_data
def compute_welch_quantities(
    x: np.ndarray,
    y: np.ndarray,
    sample_rate: float,
    nperseg: int,
    noverlap: int,
    window: str = "hann",
) -> dict:
    """Compute Welch-averaged spectral quantities from time-domain signals.

    Returns dict with keys:
        freqs                : float64 frequency array (Hz)
        Gxx, Gyy             : float64 auto-power spectral densities
        Gxy, Gyx             : complex128 cross-power spectral densities (Gxy = E[X* Y], Gyx = conj)
        H1, H2, Hv           : complex128 FRF estimators
        gamma2               : float64 ordinary coherence [0, 1]
    """
    from scipy.signal import csd, welch

    eps = np.finfo(float).tiny
    kw = dict(fs=sample_rate, window=window, nperseg=nperseg, noverlap=noverlap)

    freqs, Gxx = welch(x, **kw)
    _, Gyy = welch(y, **kw)
    _, Gxy = csd(x, y, **kw)  # scipy csd(x,y) = E[X* Y] = G_xy by standard convention
    Gyx = np.conj(Gxy)

    Gxx_safe = np.maximum(Gxx, eps)
    Gyx_safe = np.where(np.abs(Gyx) > eps, Gyx, eps + 0j)

    H1 = Gxy / Gxx_safe

    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        H2 = Gyy / Gyx_safe
        Hv_mag = np.sqrt(np.abs(H1) * np.abs(H2))
        Hv = Hv_mag * np.exp(1j * np.angle(H1))
        gamma2 = np.abs(Gxy) ** 2 / (Gxx_safe * np.maximum(Gyy, eps))

    H2 = np.where(np.isfinite(H2), H2, 0.0 + 0j)
    Hv_mag = np.where(np.isfinite(Hv_mag), Hv_mag, 0.0)
    Hv = np.where(np.isfinite(Hv), Hv, 0.0 + 0j)
    gamma2 = np.where(np.isfinite(gamma2), gamma2, 0.0)

    return dict(freqs=freqs, Gxx=Gxx, Gyy=Gyy, Gyx=Gyx, Gxy=Gxy, H1=H1, H2=H2, Hv=Hv, gamma2=gamma2)


def _contiguous_intervals(below: np.ndarray, freqs: np.ndarray) -> list[tuple[float, float]]:
    intervals: list[tuple[float, float]] = []
    in_interval = False
    f_lo = 0.0
    for i, (f, b) in enumerate(zip(freqs, below)):
        if b and not in_interval:
            f_lo = float(f)
            in_interval = True
        elif not b and in_interval:
            intervals.append((f_lo, float(freqs[i - 1])))
            in_interval = False
    if in_interval:
        intervals.append((f_lo, float(freqs[-1])))
    return intervals


def band_coherence_stats(
    gamma2: np.ndarray,
    freqs: np.ndarray,
    f_min: float,
    f_max: float,
    threshold: float = 0.7,
) -> dict:
    """Return coherence quality summary for a frequency band.

    Returns dict with keys:
        pct_low   : fraction [0, 1] of lines in band with γ² < threshold
        mean_coh  : mean γ² in band
        low_bands : list of (f_lo, f_hi) contiguous sub-bands below threshold
        passes    : True when pct_low < 0.10
    """
    band = (freqs >= f_min) & (freqs <= f_max)
    g2_band = gamma2[band]
    f_band = freqs[band]
    if len(g2_band) == 0:
        return {"pct_low": 0.0, "mean_coh": 1.0, "low_bands": [], "passes": True}
    below = g2_band < threshold
    pct_low = float(np.mean(below))
    mean_coh = float(np.mean(g2_band))
    low_bands = _contiguous_intervals(below, f_band)
    return {"pct_low": pct_low, "mean_coh": mean_coh, "low_bands": low_bands, "passes": pct_low < 0.10}
