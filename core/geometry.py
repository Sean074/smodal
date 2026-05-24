"""NASTRAN BDF/F06 wireframe geometry: parsers, RBE3 interpolation, and Plotly 3D figures.

BDF parser handles only GRID, PLOTEL, and RBE3 cards — all other structural cards are
silently skipped (no CBAR, MAT1, PBAR, SPC, etc. are required).

F06 parser handles SOL 103 normal-modes output: real eigenvalue table and eigenvectors.

Adapted from sbeam/sbeam/parser/bdf_reader.py and sbeam/sbeam/viewer/geometry.py.
"""

from __future__ import annotations

import math
import re
import warnings
from dataclasses import dataclass, field
from typing import IO

import numpy as np
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Grid:
    gid: int
    x: float
    y: float
    z: float


@dataclass
class Plotel:
    eid: int
    g1: int
    g2: int


@dataclass
class Rbe3:
    eid: int
    refgrid: int
    refc: str
    wt_gc: list = field(default_factory=list)  # [(weight, dofs_str, [gid, ...])]


@dataclass
class GeomModel:
    grids: dict   # {gid: Grid}
    plotels: dict  # {eid: Plotel}
    rbe3s: dict   # {eid: Rbe3}


# ---------------------------------------------------------------------------
# BDF field parsing
# ---------------------------------------------------------------------------

_SILENT_KEYWORDS = frozenset({
    "BEGIN", "BEGINBULK", "ENDDATA", "SOL", "SUBCASE", "TITLE",
    "SPC", "SPC1", "FORCE", "MOMENT", "LOAD", "EIGRL",
    "PBAR", "CBAR", "CBEAM", "CROD", "PROD", "MAT1", "CONM2",
})


def _split_free(line: str) -> list:
    return [f.strip() for f in line.split(",")]


def _split_fixed(line: str) -> list:
    line = line.ljust(72)
    return [line[i:i + 8].strip() for i in range(0, 72, 8)]


def _split(line: str) -> list:
    return _split_free(line) if "," in line else _split_fixed(line)


def _f(s: str) -> float:
    s = s.strip()
    return float(s) if s else 0.0


def _i(s: str) -> int:
    return int(s.strip())


def _is_cont(fields: list) -> bool:
    return bool(fields) and fields[0].startswith("+")


# ---------------------------------------------------------------------------
# Card handlers
# ---------------------------------------------------------------------------

def _handle_grid(fields: list, grids: dict) -> None:
    gid = _i(fields[1])
    x = _f(fields[3]) if len(fields) > 3 else 0.0
    y = _f(fields[4]) if len(fields) > 4 else 0.0
    z = _f(fields[5]) if len(fields) > 5 else 0.0
    grids[gid] = Grid(gid=gid, x=x, y=y, z=z)


def _handle_plotel(fields: list, grids: dict, plotels: dict) -> None:
    eid = _i(fields[1])
    g1 = _i(fields[2])
    g2 = _i(fields[3])
    if g1 not in grids or g2 not in grids:
        warnings.warn(f"PLOTEL {eid}: referenced grid not found — skipped", UserWarning, stacklevel=3)
        return
    plotels[eid] = Plotel(eid=eid, g1=g1, g2=g2)


def _handle_rbe3(fields: list, conts: list, rbe3s: dict) -> None:
    eid = _i(fields[1])
    refgrid = _i(fields[3])
    refc = fields[4].strip()

    all_fields = [f.strip() for f in fields[5:] if f.strip()]
    for cont in conts:
        all_fields += [f.strip() for f in cont[1:] if f.strip()]

    wt_gc: list = []
    k = 0
    while k < len(all_fields):
        wt = _f(all_fields[k])
        k += 1
        if k >= len(all_fields):
            break
        c = all_fields[k].strip()
        k += 1
        gids: list = []
        while k < len(all_fields):
            tok = all_fields[k]
            if "." in tok or "e" in tok.lower():
                break
            try:
                gids.append(int(tok))
                k += 1
            except ValueError:
                k += 1
        wt_gc.append((wt, c, gids))

    rbe3s[eid] = Rbe3(eid=eid, refgrid=refgrid, refc=refc, wt_gc=wt_gc)


# ---------------------------------------------------------------------------
# Public parse entry point
# ---------------------------------------------------------------------------

def parse_wireframe_bdf(file_like: IO | str) -> GeomModel:
    """Parse a NASTRAN BDF file and return a GeomModel with GRID, PLOTEL, and RBE3 data.

    Accepts a file-like object (e.g. from st.file_uploader) or a filepath string.
    Both free-field (comma-separated) and fixed-field (8-character column) formats are handled.
    All non-wireframe cards (CBAR, MAT1, SPC, etc.) are silently skipped.
    """
    if isinstance(file_like, str):
        with open(file_like) as fh:
            raw_lines = fh.readlines()
    else:
        content = file_like.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        raw_lines = content.splitlines()

    # Strip $ comments
    lines: list = []
    for raw in raw_lines:
        idx = raw.find("$")
        lines.append(raw[:idx].rstrip() if idx >= 0 else raw.rstrip())

    # Discard everything before BEGIN BULK (case control section)
    bulk_start = 0
    for idx, line in enumerate(lines):
        if line.strip().upper().startswith("BEGIN"):
            bulk_start = idx + 1
            break
    lines = lines[bulk_start:]

    grids: dict = {}
    plotels: dict = {}
    rbe3s: dict = {}

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        fields = _split(line)
        if not fields or not fields[0]:
            i += 1
            continue

        keyword = fields[0].upper()

        if _is_cont(fields) or keyword in _SILENT_KEYWORDS:
            i += 1
            continue

        if keyword == "GRID":
            _handle_grid(fields, grids)
            i += 1

        elif keyword == "PLOTEL":
            _handle_plotel(fields, grids, plotels)
            i += 1

        elif keyword == "RBE3":
            # Collect all continuation lines
            conts: list = []
            k = i + 1
            while k < len(lines):
                if not lines[k].strip():
                    k += 1
                    continue
                nf = _split(lines[k])
                if _is_cont(nf):
                    conts.append(nf)
                    k += 1
                else:
                    break
            _handle_rbe3(fields, conts, rbe3s)
            i = k

        else:
            warnings.warn(
                f"BDF card '{keyword}' is not used for wireframe geometry — skipped",
                UserWarning,
                stacklevel=2,
            )
            i += 1

    return GeomModel(grids=grids, plotels=plotels, rbe3s=rbe3s)


# ---------------------------------------------------------------------------
# F06 SOL 103 parser
# ---------------------------------------------------------------------------

_RE_EIGENVAL_LINE = re.compile(
    r"^\s+(\d+)\s+[\d.E+\-]+\s+[\d.E+\-]+\s+([\d.E+\-]+)",
    re.IGNORECASE,
)
_RE_EIGENVEC_HDR = re.compile(
    r"E\s+I\s+G\s+E\s+N\s+V\s+E\s+C\s+T\s+O\s+R\s+NO\.\s+(\d+)",
    re.IGNORECASE,
)
# Identify a GRID data row: leading integer, then "G", then numbers
_RE_EIGENVEC_ROW_ID = re.compile(r"^\s+(\d+)\s+G\s+", re.IGNORECASE)
# Extract all NASTRAN-format floating-point numbers (handles no-space adjacent negatives)
_RE_FLOAT = re.compile(r"[+-]?\d+\.?\d*[Ee][+-]\d+", re.IGNORECASE)


def parse_f06(file_like: IO | str) -> dict:
    """Parse a NASTRAN SOL 103 F06 file and return frequencies and mode shapes.

    Parameters
    ----------
    file_like : file-like object or filepath string

    Returns
    -------
    dict with keys:
        'frequencies_hz' : np.ndarray, shape (n_modes,)
        'mode_shapes'    : list of dicts, len n_modes
                           each dict maps gid (int) -> np.ndarray([T1, T2, T3])
    """
    if isinstance(file_like, str):
        with open(file_like) as fh:
            lines = fh.readlines()
    else:
        content = file_like.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        lines = content.splitlines()

    frequencies_hz: list = []
    mode_shapes: list = []

    in_eigenval = False
    current_mode_idx: int = -1
    current_shape: dict = {}

    for line in lines:
        # Detect eigenvalue section header
        if "R E A L" in line and "E I G E N V A L U E S" in line:
            in_eigenval = True
            continue

        # Parse eigenvalue table rows (skip blank lines and column headers inside section)
        if in_eigenval:
            if not line.strip():
                # Blank line only ends the section if we already captured some rows
                if frequencies_hz:
                    in_eigenval = False
                continue
            m = _RE_EIGENVAL_LINE.match(line)
            if m:
                frequencies_hz.append(float(m.group(2)))
            continue

        # Detect eigenvector section header
        m_hdr = _RE_EIGENVEC_HDR.search(line)
        if m_hdr:
            # Save previous mode if any
            if current_mode_idx >= 0:
                mode_shapes.append(current_shape)
            current_mode_idx = int(m_hdr.group(1)) - 1  # 0-based
            current_shape = {}
            continue

        # Parse eigenvector data rows
        if current_mode_idx >= 0:
            m_id = _RE_EIGENVEC_ROW_ID.match(line)
            if m_id:
                gid = int(m_id.group(1))
                # Extract all floats after the "G" marker; need T1, T2, T3 (first three)
                nums = _RE_FLOAT.findall(line[m_id.end():])
                if len(nums) >= 3:
                    current_shape[gid] = np.array([float(nums[0]), float(nums[1]), float(nums[2])])

    # Flush last mode
    if current_mode_idx >= 0:
        mode_shapes.append(current_shape)

    return {
        "frequencies_hz": np.array(frequencies_hz),
        "mode_shapes": mode_shapes,
    }


# ---------------------------------------------------------------------------
# RBE3 displacement interpolation
# ---------------------------------------------------------------------------

def expand_rbe3_displacements(geom: GeomModel, meas_disps: dict) -> dict:
    """Expand measured displacements to all GRIDs via RBE3 weighted averaging.

    Parameters
    ----------
    geom        : GeomModel from parse_wireframe_bdf
    meas_disps  : {gid: np.ndarray shape (3,)} — measured [dx, dy, dz] per measurement GRID

    Returns
    -------
    {gid: np.ndarray shape (3,)} for every GRID in geom.grids:
    - Measurement GRIDs: their direct measured displacement
    - RBE3 refgrids: weighted average of their independent GRIDs' measured displacements
    - All other GRIDs: zero displacement
    """
    result: dict = {gid: meas_disps.get(gid, np.zeros(3)).copy() for gid in geom.grids}

    for rbe3 in geom.rbe3s.values():
        ref = rbe3.refgrid
        if ref not in geom.grids:
            continue

        total_w = 0.0
        weighted = np.zeros(3)
        for wt, _dofs, gids in rbe3.wt_gc:
            for gid in gids:
                if gid in meas_disps:
                    weighted += wt * meas_disps[gid]
                    total_w += wt

        if total_w > 0.0:
            result[ref] = weighted / total_w

    return result


# ---------------------------------------------------------------------------
# Plotly 3D — coordinate helpers
# ---------------------------------------------------------------------------

def _undeformed_coords(geom: GeomModel) -> dict:
    return {gid: (g.x, g.y, g.z) for gid, g in geom.grids.items()}


def _deformed_coords(geom: GeomModel, gid_disps: dict, amplitude: float) -> dict:
    coords: dict = {}
    for gid, grid in geom.grids.items():
        d = gid_disps.get(gid, np.zeros(3)) * amplitude
        coords[gid] = (grid.x + float(d[0]), grid.y + float(d[1]), grid.z + float(d[2]))
    return coords


def _plotel_line_coords(geom: GeomModel, coords: dict) -> tuple:
    xs: list = []
    ys: list = []
    zs: list = []
    for plotel in geom.plotels.values():
        g1, g2 = coords[plotel.g1], coords[plotel.g2]
        xs += [g1[0], g2[0], None]
        ys += [g1[1], g2[1], None]
        zs += [g1[2], g2[2], None]
    return xs, ys, zs


def _grid_coord_lists(geom: GeomModel, coords: dict) -> tuple:
    gids = sorted(geom.grids.keys())
    return (
        [coords[g][0] for g in gids],
        [coords[g][1] for g in gids],
        [coords[g][2] for g in gids],
    )


# ---------------------------------------------------------------------------
# Plotly 3D — trace builders
# ---------------------------------------------------------------------------

def _add_triad(fig: go.Figure, geom: GeomModel) -> None:
    if geom.grids:
        vals = [(g.x, g.y, g.z) for g in geom.grids.values()]
        ranges = [max(v[i] for v in vals) - min(v[i] for v in vals) for i in range(3)]
        L = max(max(ranges) * 0.1, 1.0)
    else:
        L = 1.0
    for xs, ys, zs, color, label in [
        ([0.0, L], [0.0, 0.0], [0.0, 0.0], "#cc3333", "X"),
        ([0.0, 0.0], [0.0, L], [0.0, 0.0], "#33aa33", "Y"),
        ([0.0, 0.0], [0.0, 0.0], [0.0, L], "#3366cc", "Z"),
    ]:
        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="lines+text",
            line=dict(color=color, width=3),
            text=["", label],
            textfont=dict(color=color, size=12),
            hoverinfo="skip",
            showlegend=False,
        ))


_CAMERA_VIEWS: dict = {
    "3D": None,
    "X-Y": dict(eye=dict(x=0, y=0, z=2.5), up=dict(x=0, y=1, z=0)),
    "X-Z": dict(eye=dict(x=0, y=-2.5, z=0), up=dict(x=0, y=0, z=1)),
    "Y-Z": dict(eye=dict(x=2.5, y=0, z=0), up=dict(x=0, y=0, z=1)),
}


def _apply_camera(fig: go.Figure, view: str) -> None:
    camera = _CAMERA_VIEWS.get(view)
    if camera is not None:
        fig.update_layout(scene_camera=camera)


def _apply_layout(fig: go.Figure) -> None:
    fig.update_layout(
        scene=dict(aspectmode="data", xaxis_title="X", yaxis_title="Y", zaxis_title="Z"),
        legend=dict(orientation="v", x=0.01, y=0.99),
        margin=dict(l=0, r=0, t=30, b=0),
        height=600,
    )


# ---------------------------------------------------------------------------
# Public figure builders
# ---------------------------------------------------------------------------

def build_static_figure(geom: GeomModel, view: str = "3D") -> go.Figure:
    """Return a Plotly 3D figure of the undeformed wireframe geometry."""
    fig = go.Figure()
    coords = _undeformed_coords(geom)

    if geom.plotels:
        xs, ys, zs = _plotel_line_coords(geom, coords)
        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="lines",
            line=dict(color="#1f77b4", width=3),
            name="PLOTEL",
        ))

    if geom.grids:
        gids = sorted(geom.grids.keys())
        gxs = [coords[g][0] for g in gids]
        gys = [coords[g][1] for g in gids]
        gzs = [coords[g][2] for g in gids]
        customdata = [[gid, coords[gid][0], coords[gid][1], coords[gid][2]] for gid in gids]
        fig.add_trace(go.Scatter3d(
            x=gxs, y=gys, z=gzs,
            mode="markers+text",
            marker=dict(size=6, color="#333333"),
            text=[str(g) for g in gids],
            textposition="top center",
            textfont=dict(size=9),
            customdata=customdata,
            hovertemplate=(
                "<b>GRID %{customdata[0]}</b><br>"
                "X: %{customdata[1]:.4g}  "
                "Y: %{customdata[2]:.4g}  "
                "Z: %{customdata[3]:.4g}"
                "<extra></extra>"
            ),
            name="GRIDs",
        ))

    if geom.rbe3s:
        rxs: list = []
        rys: list = []
        rzs: list = []
        for rbe3 in geom.rbe3s.values():
            if rbe3.refgrid not in coords:
                continue
            ref = coords[rbe3.refgrid]
            for _wt, _c, gids in rbe3.wt_gc:
                for gid in gids:
                    if gid in coords:
                        ind = coords[gid]
                        rxs += [ref[0], ind[0], None]
                        rys += [ref[1], ind[1], None]
                        rzs += [ref[2], ind[2], None]
        if rxs:
            fig.add_trace(go.Scatter3d(
                x=rxs, y=rys, z=rzs,
                mode="lines",
                line=dict(color="#cc2222", width=2, dash="dash"),
                name="RBE3",
                hoverinfo="skip",
            ))

    _add_triad(fig, geom)
    _apply_layout(fig)
    _apply_camera(fig, view)
    return fig


def build_mode_figure(
    geom: GeomModel,
    gid_disps: dict,
    freq_hz: float = 0.0,
    scale: float = 1.0,
    n_frames: int = 20,
    view: str = "3D",
    accel_gids: set | None = None,
) -> go.Figure:
    """Return an animated Plotly 3D figure cycling through one mode shape.

    Parameters
    ----------
    geom       : GeomModel geometry
    gid_disps  : {gid: np.ndarray(3)} — normalised displacement vector per GRID
                 (from expand_rbe3_displacements)
    freq_hz    : natural frequency for the figure title
    scale      : peak displacement amplitude applied to gid_disps
    n_frames   : number of animation frames (one full cycle)
    view       : camera preset — '3D', 'X-Y', 'X-Z', or 'Y-Z'
    """
    fig = go.Figure()
    undeformed = _undeformed_coords(geom)

    # Ghost undeformed PLOTEL lines
    if geom.plotels:
        xs, ys, zs = _plotel_line_coords(geom, undeformed)
        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="lines",
            line=dict(color="#cccccc", width=2),
            name="Undeformed",
            opacity=0.5,
        ))

    # Initial animated traces at zero amplitude (trace indices 1 and 2)
    def_0 = _deformed_coords(geom, gid_disps, 0.0)
    dxs0, dys0, dzs0 = _plotel_line_coords(geom, def_0) if geom.plotels else ([], [], [])
    gxs0, gys0, gzs0 = _grid_coord_lists(geom, def_0)

    accel_set = accel_gids or set()
    gids_sorted = sorted(geom.grids.keys())
    grid_colors = ["#cc2222" if g in accel_set else "#ff7f0e" for g in gids_sorted]
    grid_texts = [str(g) if g in accel_set else "" for g in gids_sorted]

    fig.add_trace(go.Scatter3d(
        x=dxs0, y=dys0, z=dzs0,
        mode="lines",
        line=dict(color="#ff7f0e", width=4),
        name="Mode shape",
    ))
    fig.add_trace(go.Scatter3d(
        x=gxs0, y=gys0, z=gzs0,
        mode="markers+text" if accel_set else "markers",
        marker=dict(size=6, color=grid_colors),
        text=grid_texts,
        textposition="top center",
        textfont=dict(size=10, color="#cc2222"),
        name="Mode GRIDs",
        showlegend=False,
    ))

    _add_triad(fig, geom)

    # Build animation frames
    frames: list = []
    for frame_i in range(n_frames):
        amp = scale * math.sin(2.0 * math.pi * frame_i / n_frames)
        def_c = _deformed_coords(geom, gid_disps, amp)
        dxs, dys, dzs = _plotel_line_coords(geom, def_c) if geom.plotels else ([], [], [])
        gxs, gys, gzs = _grid_coord_lists(geom, def_c)
        frames.append(go.Frame(
            name=str(frame_i),
            data=[
                go.Scatter3d(x=dxs, y=dys, z=dzs),
                go.Scatter3d(x=gxs, y=gys, z=gzs),
            ],
            traces=[1, 2],
        ))
    fig.frames = frames

    fig.update_layout(
        title=f"Mode shape  —  f = {freq_hz:.4g} Hz",
        updatemenus=[dict(
            type="buttons",
            showactive=False,
            y=0.02,
            x=0.1,
            xanchor="right",
            buttons=[
                dict(
                    label="▶",
                    method="animate",
                    args=[None, {"frame": {"duration": 50, "redraw": True},
                                 "fromcurrent": True, "loop": True}],
                ),
                dict(
                    label="⏸",
                    method="animate",
                    args=[[None], {"frame": {"duration": 0}, "mode": "immediate"}],
                ),
            ],
        )],
    )
    _apply_layout(fig)
    _apply_camera(fig, view)
    return fig


def build_static_mode_figure(
    geom: GeomModel,
    gid_disps: dict,
    freq_hz: float = 0.0,
    scale: float = 1.0,
    phase_deg: float = 90.0,
    view: str = "3D",
    accel_gids: set | None = None,
) -> go.Figure:
    """Return a static (non-animated) Plotly 3D figure frozen at a given phase angle.

    Parameters
    ----------
    geom      : GeomModel geometry
    gid_disps : {gid: np.ndarray(3)} — normalised displacement per GRID
    freq_hz   : natural frequency for the figure title
    scale     : displacement scale factor
    phase_deg : phase angle in degrees (0–360); 90° = peak positive
    view      : camera preset — '3D', 'X-Y', 'X-Z', or 'Y-Z'
    """
    amplitude = scale * math.sin(math.radians(phase_deg))

    fig = go.Figure()
    undeformed = _undeformed_coords(geom)

    if geom.plotels:
        xs, ys, zs = _plotel_line_coords(geom, undeformed)
        fig.add_trace(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="lines",
            line=dict(color="#cccccc", width=2),
            name="Undeformed",
            opacity=0.5,
        ))

    def_c = _deformed_coords(geom, gid_disps, amplitude)

    if geom.plotels:
        dxs, dys, dzs = _plotel_line_coords(geom, def_c)
        fig.add_trace(go.Scatter3d(
            x=dxs, y=dys, z=dzs,
            mode="lines",
            line=dict(color="#ff7f0e", width=4),
            name="Mode shape",
        ))

    accel_set = accel_gids or set()
    gids_sorted = sorted(geom.grids.keys())
    grid_colors = ["#cc2222" if g in accel_set else "#ff7f0e" for g in gids_sorted]
    grid_texts = [str(g) if g in accel_set else "" for g in gids_sorted]

    gxs, gys, gzs = _grid_coord_lists(geom, def_c)
    fig.add_trace(go.Scatter3d(
        x=gxs, y=gys, z=gzs,
        mode="markers+text" if accel_set else "markers",
        marker=dict(size=6, color=grid_colors),
        text=grid_texts,
        textposition="top center",
        textfont=dict(size=10, color="#cc2222"),
        name="Mode GRIDs",
        showlegend=False,
    ))

    _add_triad(fig, geom)
    fig.update_layout(title=f"Mode shape  —  f = {freq_hz:.4g} Hz  (φ = {phase_deg:.0f}°)")
    _apply_layout(fig)
    _apply_camera(fig, view)
    return fig
