from __future__ import annotations

import numpy as np
import pandas as pd

# Expected time column names, checked in order
_TIME_COLUMN_CANDIDATES = ["time", "Time", "TIME", "t", "T"]


def load_csv(file) -> tuple[pd.DataFrame | None, str | None]:
    """Load a CSV file and return (dataframe, error). Time column is normalised to 'time'."""
    try:
        df = pd.read_csv(file)
    except Exception as e:
        return None, f"Could not parse file: {e}"

    # Detect time column
    time_col = None
    for candidate in _TIME_COLUMN_CANDIDATES:
        if candidate in df.columns:
            time_col = candidate
            break

    if time_col is None:
        # Fall back to first column if it looks numeric and monotonically increasing
        first = df.columns[0]
        if pd.api.types.is_numeric_dtype(df[first]) and df[first].is_monotonic_increasing:
            time_col = first
        else:
            return None, (
                "No time column found. Expected a column named 'time' (or 't'), "
                "or a numeric monotonically increasing first column."
            )

    if time_col != "time":
        df = df.rename(columns={time_col: "time"})

    data_cols = [c for c in df.columns if c != "time"]
    if len(data_cols) == 0:
        return None, "File must contain at least one data channel column."

    if df.shape[0] < 2:
        return None, "File must contain at least two rows."

    return df, None


def compute_sample_rate(time: np.ndarray) -> float:
    dt_values = np.diff(time)
    dt_mean = dt_values.mean()
    dt_std = dt_values.std()
    if dt_std / dt_mean > 0.01:
        # More than 1 % jitter — warn but still return estimate
        pass
    return 1.0 / dt_mean


def compute_summary(df: pd.DataFrame, input_ch: str, output_chs: list[str]) -> list[dict]:
    time = df["time"].values
    fs = compute_sample_rate(time)
    duration = time[-1] - time[0]
    n_samples = len(time)

    rows = []
    for ch in [input_ch] + list(output_chs):
        signal = df[ch].values
        rows.append({
            "Channel": ch,
            "Type": "Input" if ch == input_ch else "Output",
            "Samples": n_samples,
            "Sample Rate (Hz)": round(fs, 2),
            "Duration (s)": round(duration, 4),
            "Min Time (s)": round(float(time[0]), 6),
            "Max Time (s)": round(float(time[-1]), 6),
            "Min Value": round(float(signal.min()), 6),
            "Max Value": round(float(signal.max()), 6),
            "RMS": round(float(np.sqrt(np.mean(signal**2))), 6),
        })
    return rows
