"""UFF Dataset 58 writer for identified mode shapes."""

from __future__ import annotations

import datetime

import numpy as np

_DELIM = "    -1"
_HEADER = "    58"
_LINE_LEN = 80


def _pad(text: str) -> str:
    return f"{text:<{_LINE_LEN}}"


def _dataset58(
    fn_hz: np.ndarray,
    xi: np.ndarray,
    residues_ch: np.ndarray,
    channel_name: str,
    analysis_name: str,
    node_id: int,
) -> str:
    """Build one UFF Dataset 58 record string for a single channel."""
    n_modes = len(fn_hz)
    date_str = datetime.date.today().isoformat()

    xi_str = ", ".join(f"{x * 100:.3f}%" for x in xi)
    id1 = _pad(f"Analysis: {analysis_name}")
    id2 = _pad(f"Channel: {channel_name}  Node: {node_id}")
    id3 = _pad(f"Mode shapes  Date: {date_str}")
    id4 = _pad(f"xi: {xi_str}")
    id5 = _pad("")

    # Record 6: func_type=3 (ordinary mode shape), n_pts, abscissa_type=18 (Hz),
    #   spacing=0 (non-uniform), x_min=first natural freq, x_inc=0
    rec6 = (
        f"{3:5d}{n_modes:10d}{18:5d}{0:10d}"
        f"{fn_hz[0]:15.7E}{0.0:15.7E}"
    )

    # Record 7: y_char=0, y_num_format=5 (complex double), z fields=0
    rec7 = f"{0:10d}{5:5d}{0:5d}{0:5d}{0.0:15.7E}{0.0:15.7E}"

    # Record 8: response_node, response_dir=0 (scalar), ref_node=0, ref_dir=0, modal_mass=1, 0
    rec8 = f"{node_id:10d}{0:5d}{0:10d}{0:5d}{1.0:15.7E}{0.0:15.7E}"

    # Data: non-uniform complex → triplets (x, real, imag), 6 values (2 triplets) per line
    vals: list[float] = []
    for m in range(n_modes):
        vals.append(float(fn_hz[m]))
        vals.append(float(residues_ch[m].real))
        vals.append(float(residues_ch[m].imag))

    data_lines: list[str] = []
    for i in range(0, len(vals), 6):
        chunk = vals[i : i + 6]
        data_lines.append("".join(f"{v:13.5E}" for v in chunk))

    parts = [
        _DELIM,
        _HEADER,
        id1,
        id2,
        id3,
        id4,
        id5,
        rec6,
        rec7,
        rec8,
        *data_lines,
        _DELIM,
    ]
    return "\n".join(parts) + "\n"


def write_uff58_shapes(
    fn_hz: np.ndarray,
    xi: np.ndarray,
    residues: np.ndarray,
    channel_names: list[str],
    analysis_name: str = "",
) -> bytes:
    """Write identified mode shapes as UFF Dataset 58 (one dataset per channel).

    Parameters
    ----------
    fn_hz : (n_modes,) natural frequencies in Hz
    xi : (n_modes,) damping ratios (0–1 scale)
    residues : (n_channels, n_modes) complex residue array
    channel_names : list of str, length = n_channels
    analysis_name : label written to Dataset 58 ID lines

    Returns
    -------
    bytes
        Complete UFF file content (UTF-8).
    """
    fn_hz = np.asarray(fn_hz, dtype=float)
    xi = np.asarray(xi, dtype=float)
    residues = np.asarray(residues, dtype=complex)

    parts: list[str] = []
    for ch_idx, ch_name in enumerate(channel_names):
        parts.append(
            _dataset58(
                fn_hz,
                xi,
                residues[ch_idx],
                channel_name=ch_name,
                analysis_name=analysis_name,
                node_id=ch_idx + 1,
            )
        )
    return "".join(parts).encode("utf-8")


def write_uff58_shapes_mimo(
    fn_hz: np.ndarray,
    xi: np.ndarray,
    r3d: np.ndarray,
    channel_names: list[str],
    analysis_name: str = "",
) -> bytes:
    """Write MIMO mode shapes as UFF Dataset 58.

    Parameters
    ----------
    fn_hz : (n_modes,) natural frequencies in Hz
    xi : (n_modes,) damping ratios (0–1 scale)
    r3d : (n_out, 2, n_modes) complex — MIMO run A/B mode shapes
    channel_names : list of str, length = n_out (A_/B_ prefixed internally)
    analysis_name : label written to Dataset 58 ID lines

    Returns
    -------
    bytes
        Complete UFF file content (UTF-8). Produces 2 × n_out datasets.
    """
    r3d = np.asarray(r3d, dtype=complex)
    n_out = r3d.shape[0]
    # Stack run A then run B so node IDs are grouped by run
    flat_residues = np.concatenate([r3d[:, 0, :], r3d[:, 1, :]], axis=0)
    flat_names = (
        [f"A_{ch}" for ch in channel_names]
        + [f"B_{ch}" for ch in channel_names]
    )
    fn_hz = np.asarray(fn_hz, dtype=float)
    xi = np.asarray(xi, dtype=float)

    parts: list[str] = []
    for ch_idx, ch_name in enumerate(flat_names):
        node_id = (ch_idx % n_out) + 1 if ch_idx < n_out else n_out + (ch_idx % n_out) + 1
        parts.append(
            _dataset58(
                fn_hz,
                xi,
                flat_residues[ch_idx],
                channel_name=ch_name,
                analysis_name=analysis_name,
                node_id=node_id,
            )
        )
    return "".join(parts).encode("utf-8")
