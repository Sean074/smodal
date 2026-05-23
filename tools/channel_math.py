"""Create or remove derived channels in a DataFrame.

Expressions use the existing column names as variable names, e.g.::

    "acc_1 - acc_2"
    "force * 0.001"
    "(ch_a + ch_b) / 2"

Typical usage::

    from tools.channel_math import add_channel, remove_channel

    df, err = add_channel(df, "diff", "acc_1 - acc_2")
    df, err = add_channel(df, "force_kN", "force * 0.001")
    df, err = remove_channel(df, "force")
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

_BLOCKED = re.compile(r'__|import|open|exec\b|eval\b|\bos\b|subprocess')


def list_channels(df: pd.DataFrame) -> list[str]:
    """Return all column names except 'time'."""
    return [c for c in df.columns if c != "time"]


def add_channel(
    df: pd.DataFrame,
    new_name: str,
    expression: str,
) -> tuple[pd.DataFrame, str | None]:
    """Evaluate *expression* using existing channels and store the result as *new_name*.

    Column names in the expression are resolved against the current DataFrame.
    Arithmetic operators and numpy functions available via pandas eval engine.

    Args:
        df: Source DataFrame with a 'time' column.
        new_name: Name for the new channel. Overwrites an existing column of the same
                  name (except 'time').
        expression: Arithmetic expression referencing existing column names,
                    e.g. ``"acc_1 - acc_2"`` or ``"force * 0.001"``.

    Returns:
        ``(df_new, error)`` — df_new is a copy with the new channel appended; the
        original DataFrame is not mutated.
    """
    if new_name == "time":
        return df, "Cannot overwrite the 'time' column."
    if _BLOCKED.search(expression):
        return df, "Expression contains disallowed tokens."

    local_vars = {col: df[col] for col in df.columns}
    try:
        result = pd.eval(expression, local_dict=local_vars, engine="numexpr")
    except Exception:
        try:
            result = pd.eval(expression, local_dict=local_vars, engine="python")
        except Exception as e:
            return df, f"Expression error: {e}"

    if not isinstance(result, (pd.Series, np.ndarray)):
        return df, "Expression must evaluate to a numeric series."

    df = df.copy()
    df[new_name] = result
    return df, None


def remove_channel(df: pd.DataFrame, name: str) -> tuple[pd.DataFrame, str | None]:
    """Drop a channel column from the DataFrame.

    Args:
        df: Source DataFrame.
        name: Column to remove. Cannot be 'time'.

    Returns:
        ``(df_new, error)``
    """
    if name == "time":
        return df, "Cannot remove the 'time' column."
    if name not in df.columns:
        return df, f"Channel '{name}' not found."
    return df.drop(columns=[name]), None
