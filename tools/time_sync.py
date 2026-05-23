"""Align and merge DataFrames recorded with different clock start times.

Use this when multiple loggers were started at different moments but share the
same (or very similar) sample rate.  The workflow is:

1. ``trim_to_overlap`` — identify the common time window and slice each dataset.
2. ``sync_and_merge`` — trim then join on nearest timestamps.

Typical usage::

    from tools.time_sync import sync_and_merge
    from core.data_loader import load_csv

    df_a, _ = load_csv("sensor_a.csv")
    df_b, _ = load_csv("sensor_b.csv")
    merged, err = sync_and_merge([df_a, df_b], tol_s=5e-4)
"""

from __future__ import annotations

import sys
import warnings
import numpy as np
import pandas as pd

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))
from core.data_loader import compute_sample_rate


def trim_to_overlap(
    dfs: list[pd.DataFrame],
) -> tuple[list[pd.DataFrame] | None, str | None]:
    """Trim each DataFrame to the shared time window.

    Args:
        dfs: List of DataFrames, each with a 'time' column.

    Returns:
        ``(trimmed_dfs, error)`` — error is None on success.
    """
    if len(dfs) < 2:
        return None, "At least two DataFrames are required."

    for i, df in enumerate(dfs):
        if "time" not in df.columns:
            return None, f"DataFrame {i} has no 'time' column."

    t_start = max(df["time"].iloc[0] for df in dfs)
    t_end = min(df["time"].iloc[-1] for df in dfs)

    if t_start >= t_end:
        return None, (
            f"No overlapping time window found. "
            f"Latest start: {t_start:.6f} s, earliest end: {t_end:.6f} s."
        )

    trimmed = []
    for df in dfs:
        mask = (df["time"] >= t_start) & (df["time"] <= t_end)
        trimmed.append(df.loc[mask].reset_index(drop=True))

    return trimmed, None


def sync_and_merge(
    dfs: list[pd.DataFrame],
    tol_s: float = 1e-4,
) -> tuple[pd.DataFrame | None, str | None]:
    """Trim to the overlapping window then merge on nearest timestamps.

    The first DataFrame's time column is used as the reference grid.  Each
    subsequent DataFrame is joined using ``pd.merge_asof`` with
    ``direction='nearest'`` and the given tolerance.

    Args:
        dfs: List of DataFrames, each with a 'time' column.
        tol_s: Maximum allowed time difference (seconds) for a match.
               Rows without a match within tolerance are dropped.

    Returns:
        ``(merged_df, error)`` — error is None on success.
    """
    trimmed, err = trim_to_overlap(dfs)
    if err:
        return None, err

    # Warn if sample rates differ significantly
    rates = [compute_sample_rate(df["time"].values) for df in trimmed]
    if max(rates) - min(rates) > 0.001 * np.mean(rates):
        warnings.warn(
            f"Sample rates differ: {[f'{r:.2f}' for r in rates]} Hz. "
            "Merged timestamps will follow the first dataset's grid.",
            stacklevel=2,
        )

    merged = trimmed[0].sort_values("time").reset_index(drop=True)

    for i, df in enumerate(trimmed[1:], start=1):
        right = df.sort_values("time").reset_index(drop=True)
        # Avoid duplicate column names
        overlap = set(merged.columns) & set(right.columns) - {"time"}
        if overlap:
            right = right.rename(columns={c: f"{c}__{i}" for c in overlap})

        merged = pd.merge_asof(
            merged,
            right,
            on="time",
            tolerance=tol_s,
            direction="nearest",
        )

    n_dropped = merged.isnull().any(axis=1).sum()
    if n_dropped:
        warnings.warn(
            f"{n_dropped} rows had no match within tol_s={tol_s} s and contain NaN.",
            stacklevel=2,
        )

    return merged, None
