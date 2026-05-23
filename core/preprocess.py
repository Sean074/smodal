from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import butter, sosfiltfilt
from typing import Union


_BTYPE = {
    "Lowpass": "low",
    "Highpass": "high",
    "Bandpass": "band",
    "Bandstop": "bandstop",
}


def build_butter_sos(ftype: str, order: int, cutoffs: Union[float, list[float]], fs: float) -> np.ndarray:
    """Return a Butterworth SOS filter array.

    ftype: 'Lowpass', 'Highpass', 'Bandpass', or 'Bandstop'
    cutoffs: float (Hz) for LP/HP; [low_hz, high_hz] for BP/BS
    fs: sample rate in Hz
    """
    return butter(order, cutoffs, btype=_BTYPE[ftype], fs=fs, output="sos")


def trim_and_filter(
    df: pd.DataFrame,
    t_min: float,
    t_max: float,
    ftype: str,
    order: int,
    cutoffs: Union[float, list[float]],
    fs: float,
) -> pd.DataFrame:
    """Trim a DataFrame to [t_min, t_max] then optionally apply a Butterworth filter.

    ftype 'None' or cutoffs None skips filtering.
    """
    proc = df[(df["time"] >= t_min) & (df["time"] <= t_max)].copy().reset_index(drop=True)
    if ftype == "None" or cutoffs is None:
        return proc
    sos = build_butter_sos(ftype, order, cutoffs, fs)
    for col in proc.columns:
        if col != "time":
            proc[col] = sosfiltfilt(sos, proc[col].values)
    return proc
