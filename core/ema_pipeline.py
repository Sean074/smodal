"""Shared EMA mode-extraction pipeline.

Both SIMO (pages/4) and MIMO (pages/5) call these functions so that fixes to the
residue/synthesis/NMSE chain propagate to both pages automatically.
"""

from __future__ import annotations

import numpy as np

from core.sysid import (
    extract_residues,
    modal_fit_nmse,
    poles_from_estimates,
    synthesize_frf,
)

__all__ = ["extract_modes", "nmse_quality_label", "prepare_band_arrays"]


def extract_modes(
    H_band: np.ndarray,
    freqs_band: np.ndarray,
    freqs_full: np.ndarray,
    fn_estimates: np.ndarray,
    xi_estimates: np.ndarray,
) -> dict:
    """Run the residue-extraction pipeline on a band-limited FRF matrix.

    Parameters
    ----------
    H_band:       (n_band, n_outputs) complex — band-limited FRF.
                  For SIMO n_outputs = n_out; for MIMO n_outputs = n_out * 2 (runs stacked).
    freqs_band:   (n_band,) Hz — frequency axis matching H_band rows.
    freqs_full:   (n_freqs,) Hz — full axis used to synthesise the plotting FRF.
                  Pass the same object as freqs_band to skip the second synthesis call.
    fn_estimates: (n_modes,) Hz — natural frequency estimates; caller must ensure fn > 0.
    xi_estimates: (n_modes,) ratio (not %) — damping estimates; caller must ensure xi > 0.

    Returns
    -------
    dict with keys:
        poles            (n_modes,)           complex — continuous-time poles
        fn_hz            (n_modes,)           float   — natural frequencies in Hz
        xi               (n_modes,)           float   — damping ratios (not %)
        residues         (n_outputs, n_modes) complex — partial-fraction residues
        H_synthesis_band (n_band, n_outputs)  complex — synthesised FRF over band (for NMSE)
        H_synthesis_full (n_freqs, n_outputs) complex — synthesised FRF over full range (for plots)
        nmse             (n_outputs,)         float   — fit NMSE in dB per output
    """
    poles = poles_from_estimates(fn_estimates, xi_estimates)
    residues = extract_residues(H_band, freqs_band, poles)
    H_syn_band = synthesize_frf(freqs_band, poles, residues)
    H_syn_full = H_syn_band if freqs_full is freqs_band else synthesize_frf(freqs_full, poles, residues)
    nmse = modal_fit_nmse(H_band, H_syn_band)
    fn_hz = np.abs(poles.imag) / (2.0 * np.pi)
    xi = -poles.real / (np.abs(poles) + 1e-30)
    return {
        "poles": poles,
        "fn_hz": fn_hz,
        "xi": xi,
        "residues": residues,
        "H_synthesis_band": H_syn_band,
        "H_synthesis_full": H_syn_full,
        "nmse": nmse,
    }


def nmse_quality_label(db: float) -> str:
    """Return a quality label for a modal fit NMSE value in dB."""
    if db < -30:
        return "Excellent"
    if db < -20:
        return "Good"
    if db < -10:
        return "Acceptable"
    return "Poor"


def prepare_band_arrays(
    H: np.ndarray,
    freqs: np.ndarray,
    f_min: float,
    f_max: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Slice H and freqs to the [f_min, f_max] Hz band using a single boolean mask.

    Raises ValueError if no frequency points fall within the band.
    Returns (H_band, freqs_band).
    """
    mask = (freqs >= f_min) & (freqs <= f_max)
    if not mask.any():
        raise ValueError(f"No frequency points in band [{f_min}, {f_max}] Hz")
    return H[mask], freqs[mask]
