from __future__ import annotations

import numpy as np
from scipy.signal import get_window


WINDOW_SCIPY_NAMES = _WINDOW_SCIPY_NAMES = {
    "uniform": "boxcar",
    "hanning": "hann",
    "flattop": "flattop",
    "force": "hann",       # force window is typically a short hann; user may trim later
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
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
    return freqs, fft_complex


def compute_spectral_quantities(Sx: np.ndarray, Sy: np.ndarray) -> dict:
    """Compute single-realization spectral quantities from complex FFT arrays.

    Sx, Sy : complex 1-D arrays (output of np.fft.rfft) for input and output.

    Returns dict with keys:
        Gxx, Gyy             : float64 auto-power spectra
        Gyx, Gxy             : complex128 cross-power spectra
        H1, H2, Hv           : complex128 FRF estimators
        gamma2               : float64 ordinary coherence [0, 1]
    """
    eps = np.finfo(float).tiny
    Gxx = np.real(Sx * np.conj(Sx))
    Gyy = np.real(Sy * np.conj(Sy))
    Gyx = Sy * np.conj(Sx)
    Gxy = np.conj(Gyx)

    Gxx_safe = np.maximum(Gxx, eps)
    Gxy_safe = np.where(np.abs(Gxy) > eps, Gxy, eps + 0j)

    H1 = Gyx / Gxx_safe
    H2 = Gyy / Gxy_safe

    Hv_mag = np.sqrt(np.abs(H1) * np.abs(H2))
    Hv = Hv_mag * np.exp(1j * np.angle(H1))

    gamma2 = np.abs(Gyx) ** 2 / (Gxx_safe * np.maximum(Gyy, eps))

    return dict(Gxx=Gxx, Gyy=Gyy, Gyx=Gyx, Gxy=Gxy,
                H1=H1, H2=H2, Hv=Hv, gamma2=gamma2)


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
        Gyx, Gxy             : complex128 cross-power spectral densities
        H1, H2, Hv           : complex128 FRF estimators
        gamma2               : float64 ordinary coherence [0, 1]
    """
    from scipy.signal import welch, csd

    eps = np.finfo(float).tiny
    kw = dict(fs=sample_rate, window=window, nperseg=nperseg, noverlap=noverlap)

    freqs, Gxx = welch(x, **kw)
    _, Gyy = welch(y, **kw)
    _, Gyx = csd(x, y, **kw)   # Sx* · Sy = H · Gxx  (scipy: csd(a,b) = E[a* · b])
    Gxy = np.conj(Gyx)

    Gxx_safe = np.maximum(Gxx, eps)
    Gxy_safe = np.where(np.abs(Gxy) > eps, Gxy, eps + 0j)

    H1 = Gyx / Gxx_safe
    H2 = Gyy / Gxy_safe
    Hv_mag = np.sqrt(np.abs(H1) * np.abs(H2))
    Hv = Hv_mag * np.exp(1j * np.angle(H1))

    gamma2 = np.abs(Gyx) ** 2 / (Gxx_safe * np.maximum(Gyy, eps))

    return dict(freqs=freqs, Gxx=Gxx, Gyy=Gyy, Gyx=Gyx, Gxy=Gxy,
                H1=H1, H2=H2, Hv=Hv, gamma2=gamma2)
