"""Reduce the sample rate of a time-series DataFrame.

Two methods are available:

* ``'decimate'`` — integer decimation using ``scipy.signal.decimate`` (applies a
  Chebyshev anti-aliasing filter before downsampling). Requires an integer decimation
  factor; target_fs must divide evenly into the current fs (within 1 %).
* ``'resample'`` — arbitrary ratio resampling using ``scipy.signal.resample``
  (FFT-based). Use when a non-integer factor is needed.

Typical usage::

    from tools.downsample import downsample

    df_low, err = downsample(df, target_fs=256.0)
    df_low, err = downsample(df, target_fs=100.0, method='resample')
"""

from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from scipy.signal import decimate as sp_decimate
from scipy.signal import resample as sp_resample

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from core.data_loader import compute_sample_rate


def downsample(
    df: pd.DataFrame,
    target_fs: float,
    method: str = "decimate",
) -> tuple[pd.DataFrame | None, str | None]:
    """Resample *df* to *target_fs* Hz.

    Args:
        df: Input DataFrame with a 'time' column.
        target_fs: Desired sample rate in Hz. Must be less than the current rate.
        method: ``'decimate'`` (integer factor, AA filter) or ``'resample'``
                (arbitrary ratio, FFT-based).

    Returns:
        ``(df_resampled, error)`` — error is None on success.
    """
    time = df["time"].values
    current_fs = compute_sample_rate(time)

    if target_fs >= current_fs:
        return None, (
            f"target_fs ({target_fs:.2f} Hz) must be less than the current "
            f"sample rate ({current_fs:.2f} Hz)."
        )

    channels = [c for c in df.columns if c != "time"]
    n = len(time)

    if method == "decimate":
        q_float = current_fs / target_fs
        q = int(round(q_float))
        if abs(q_float - q) / q_float > 0.01:
            return None, (
                f"'decimate' requires an integer decimation factor. "
                f"current_fs / target_fs = {q_float:.4f} (nearest integer: {q}). "
                f"Use method='resample' for non-integer ratios."
            )
        decimated = {ch: sp_decimate(df[ch].values, q, zero_phase=True) for ch in channels}
        new_time = time[::q][: len(next(iter(decimated.values())))]
        result = pd.DataFrame({"time": new_time, **decimated})

    elif method == "resample":
        n_new = int(round(n * target_fs / current_fs))
        resampled = {ch: sp_resample(df[ch].values, n_new) for ch in channels}
        new_time = np.linspace(time[0], time[-1], n_new)
        result = pd.DataFrame({"time": new_time, **resampled})

    else:
        return None, f"Unknown method '{method}'. Choose 'decimate' or 'resample'."

    return result, None
