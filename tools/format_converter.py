"""Convert non-standard data files into the CSV format expected by the app.

Required output format:
  - Column named 'time' (seconds, monotonically increasing)
  - One or more data channel columns

Typical usage::

    from tools.format_converter import from_delimited, rename_columns, save_csv

    df, err = from_delimited("run1.tsv", sep="\t", time_col="t_sec")
    if err:
        raise ValueError(err)
    df, err = rename_columns(df, {"ch0": "force", "ch1": "acc_1"})
    save_csv(df, "run1_converted.csv")
"""

from __future__ import annotations

import pathlib

import pandas as pd

_TIME_CANDIDATES = ["time", "Time", "TIME", "t", "T"]


def _normalise_time(df: pd.DataFrame, time_col: str | None) -> tuple[pd.DataFrame, str | None]:
    """Rename the time column to 'time'; auto-detect if time_col is None."""
    if time_col is not None:
        if time_col not in df.columns:
            return df, f"time_col '{time_col}' not found in columns: {list(df.columns)}"
        if time_col != "time":
            df = df.rename(columns={time_col: "time"})
        return df, None

    for candidate in _TIME_CANDIDATES:
        if candidate in df.columns:
            if candidate != "time":
                df = df.rename(columns={candidate: "time"})
            return df, None

    # Fall back to first monotonically increasing numeric column
    first = df.columns[0]
    if pd.api.types.is_numeric_dtype(df[first]) and df[first].is_monotonic_increasing:
        df = df.rename(columns={first: "time"})
        return df, None

    return df, (
        "No time column detected. Pass time_col= with the column name to use, "
        "or name it 'time' / 't' in the source file."
    )


def _apply_unit_scales(df: pd.DataFrame, unit_scales: dict[str, float] | None) -> tuple[pd.DataFrame, str | None]:
    if not unit_scales:
        return df, None
    df = df.copy()
    for col, scale in unit_scales.items():
        if col not in df.columns:
            return df, f"unit_scales: column '{col}' not in DataFrame"
        df[col] = df[col] * scale
    return df, None


def from_excel(
    path: str | pathlib.Path,
    sheet: int | str = 0,
    time_col: str | None = None,
    unit_scales: dict[str, float] | None = None,
) -> tuple[pd.DataFrame | None, str | None]:
    """Load an Excel workbook sheet and return an app-ready DataFrame.

    Args:
        path: Path to .xlsx / .xls file.
        sheet: Sheet index or name (default 0).
        time_col: Column to use as the time axis (renamed to 'time').
                  Auto-detected from common names if None.
        unit_scales: Optional ``{column: scale_factor}`` multiplied in-place.

    Returns:
        ``(df, error)`` — error is None on success.
    """
    try:
        df = pd.read_excel(path, sheet_name=sheet)
    except ImportError:
        return None, "openpyxl is required for Excel support: pip install openpyxl"
    except Exception as e:
        return None, f"Could not read Excel file: {e}"

    df, err = _normalise_time(df, time_col)
    if err:
        return None, err

    df, err = _apply_unit_scales(df, unit_scales)
    if err:
        return None, err

    return df, None


def from_delimited(
    path: str | pathlib.Path,
    sep: str = "\t",
    time_col: str | None = None,
    unit_scales: dict[str, float] | None = None,
) -> tuple[pd.DataFrame | None, str | None]:
    """Load a delimited text file (TSV, semicolon-separated, etc.).

    Args:
        path: Path to the file.
        sep: Column separator (default ``\\t`` for TSV; use ``';'`` for European CSV).
        time_col: Column to use as the time axis. Auto-detected if None.
        unit_scales: Optional ``{column: scale_factor}`` multiplied in-place.

    Returns:
        ``(df, error)`` — error is None on success.
    """
    try:
        df = pd.read_csv(path, sep=sep)
    except Exception as e:
        return None, f"Could not parse file: {e}"

    df, err = _normalise_time(df, time_col)
    if err:
        return None, err

    df, err = _apply_unit_scales(df, unit_scales)
    if err:
        return None, err

    return df, None


def rename_columns(df: pd.DataFrame, mapping: dict[str, str]) -> tuple[pd.DataFrame, str | None]:
    """Rename data columns.

    Args:
        df: Input DataFrame (must already have a 'time' column).
        mapping: ``{old_name: new_name}`` pairs. 'time' may not be remapped.

    Returns:
        ``(df_renamed, error)``
    """
    if "time" in mapping:
        return df, "Cannot remap the 'time' column via rename_columns."
    missing = [k for k in mapping if k not in df.columns]
    if missing:
        return df, f"Columns not found: {missing}"
    return df.rename(columns=mapping), None


def save_csv(df: pd.DataFrame, out_path: str | pathlib.Path) -> str | None:
    """Write the DataFrame to a CSV file suitable for loading into the app.

    Returns None on success, or an error string.
    """
    try:
        pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        return None
    except Exception as e:
        return f"Could not write CSV: {e}"
