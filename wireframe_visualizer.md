# Wireframe Visualizer — Code Standard

## Purpose

Page 7 (`pages/7_Wireframe.py`) animates experimental mode shapes on a 3D structural wireframe. The geometry is defined in a NASTRAN BDF file; the mode shapes come from Pages 4 (SIMO) or 5 (MIMO).

---

## BDF Input Format

Only three card types are used. All other cards (CBAR, MAT1, PBAR, SPC, FORCE, EIGRL, etc.) are silently skipped.

### GRID — node geometry

Defines the 3D position of each node in the global coordinate system (CP = 0).

**Fixed-field (8-character columns):**
```
GRID    GID     CP      X1      X2      X3      CD      PS      SEID
GRID    101             0.0     0.0     0.0
GRID    102             1.5     0.0     0.0
```

**Free-field (comma-delimited):**
```
GRID, 101, , 0.0, 0.0, 0.0
GRID, 102, , 1.5, 0.0, 0.0
```

Fields used: `GID` (col 2), `X1` (col 4), `X2` (col 5), `X3` (col 6). All other fields are ignored.

---

### PLOTEL — wireframe edges

Defines a visual-only line element between two nodes. No structural stiffness — used exclusively for drawing.

```
PLOTEL  EID     G1      G2
PLOTEL  201     101     102
PLOTEL  202     102     103
```

Free-field:
```
PLOTEL, 201, 101, 102
```

Fields used: `EID` (col 2), `G1` (col 3), `G2` (col 4). Both G1 and G2 must reference previously-defined GRIDs.

---

### RBE3 — measurement interpolation

Interpolates motion from measurement GRIDs (independent) to geometry-only GRIDs (dependent/refgrid). Multi-line continuation with `+` prefix is supported.

**Semantics in this application:**
- `refgrid` = geometry-only node that has no direct accelerometer measurement
- Independent grids = nearby accelerometer GRIDs whose measured mode shape amplitudes are averaged

```
RBE3    EID             REFGRID REFC    WT1     C1      G1,1    G1,2
RBE3    301             501     123456  1.0     123456  101     102
```

Free-field with continuation:
```
RBE3, 301, , 501, 123456, 1.0, 123456, 101
+, 102
```

Fields used: `EID` (col 2), `REFGRID` (col 4), `REFC` (col 5), then alternating `(weight, dofs, grids...)` groups.

---

## Session State

| Key | Consumed | Type |
|---|---|---|
| `modal_results` | Page 7 (SIMO source) | dict — see Page 4 spec |
| `mimo_modal_results` | Page 7 (MIMO source) | dict — see Page 5 spec |

Page 7 produces no session state (display-only page).

### Required keys in the results dict

| Key | Shape / Type | Description |
|---|---|---|
| `fn` | `(n_modes,) float` | Natural frequencies (Hz) |
| `xi` | `(n_modes,) float` | Damping ratios (fraction) |
| `mode_shapes` | `(n_outputs, n_modes) complex` | Complex residues per output per mode |
| `output_channels` | `list[str]` | Channel names matching rows of `mode_shapes` |

---

## Core Module — `core/geometry.py`

### Public API

#### `parse_wireframe_bdf(file_like) -> GeomModel`

Parse a BDF file or file-like object. Returns a `GeomModel` containing:
- `.grids` — `{gid: Grid(gid, x, y, z)}`
- `.plotels` — `{eid: Plotel(eid, g1, g2)}`
- `.rbe3s` — `{eid: Rbe3(eid, refgrid, refc, wt_gc)}`

Issues `UserWarning` for unrecognised card types. Silently skips structural cards listed in `_SILENT_KEYWORDS`.

#### `expand_rbe3_displacements(geom, meas_disps) -> dict`

Interpolates measured displacements to all GRIDs.

- `meas_disps`: `{gid: np.ndarray(3)}` — measured `[dx, dy, dz]` at each accelerometer GRID
- Returns: `{gid: np.ndarray(3)}` for **every** GRID in `geom.grids`
  - Measurement GRIDs: their direct displacement
  - RBE3 refgrids: `sum(wt_i * meas_disps[gid_i]) / sum(wt_i)` over independent grids
  - All other GRIDs: `[0, 0, 0]`

#### `build_static_figure(geom) -> go.Figure`

Plotly 3D figure of the undeformed wireframe. Includes:
- PLOTEL edges (blue solid lines)
- GRID points (dark markers + GID labels)
- RBE3 connections (red dashed lines, refgrid ↔ independent grids)
- Coordinate triad (X=red, Y=green, Z=blue)

#### `build_mode_figure(geom, gid_disps, freq_hz, scale, n_frames) -> go.Figure`

Animated Plotly 3D figure for one mode shape.

- Ghost trace: undeformed wireframe (grey, 50% opacity)
- Animated traces: deformed PLOTEL lines + GRID markers (orange)
- Frame `i` amplitude: `scale × sin(2π × i / n_frames)`
- Play/Pause buttons embedded in the figure

---

## Mode Shape Handling

Mode shapes from the system identification are complex residues. For animation:

1. Extract the real part: `shape = Re(mode_shapes[:, mode_idx])`
2. Normalise to peak = 1: `shape = shape / max(|shape|)`
3. Assign each component to its GRID and DOF axis based on the channel mapping
4. The `scale` slider controls the peak visual displacement

**Why real part only:** Complex residue phase indicates the phase relationship between measurement points. For a lightly damped real-normal mode, the imaginary part is small. Taking the real part gives the dominant deformation shape. For heavily damped or closely spaced modes, users may want to consider phase-referenced animation (not yet implemented).

---

## Channel Mapping Convention

Each output channel is mapped to:
1. A **GRID ID** — the node at the accelerometer physical location
2. A **DOF axis** — the measurement direction (X=0, Y=1, Z=2 in array indexing)

The displacement vector for GRID `g` on axis `d` is:
```
meas_disps[g][d] = normalised_shape[channel_index]
```

If two channels map to the same GRID on different axes, their contributions are summed:
```python
meas_disps[gid] += d_vector
```

---

## BDF Geometry File Guidelines

1. **All measurement GRIDs must be in the BDF.** Their GID must be known when mapping channels.
2. **PLOTEL elements define the visual wireframe.** Without them, only GRID points are drawn.
3. **RBE3 elements are optional.** Include them only when geometry GRIDs exist that are not measurement points and whose motion should be interpolated.
4. **Coordinate system CP=0 (global Cartesian) is assumed.** The parser ignores the CP field.
5. **Free-field and fixed-field formats are both accepted** in the same file.
6. **Comments** start with `$` and are stripped before parsing.

### Minimal working example

```
$ Simple 3-node wireframe with one intermediate measurement-only node
$
$ Measurement grids (accelerometer locations)
GRID, 1, , 0.0, 0.0, 0.0
GRID, 2, , 1.0, 0.0, 0.0
GRID, 3, , 2.0, 0.0, 0.0
$
$ Geometry-only grid (no accelerometer — interpolated via RBE3)
GRID, 10, , 0.5, 0.0, 0.0
GRID, 11, , 1.5, 0.0, 0.0
$
$ Wireframe edges
PLOTEL, 101, 1,  10
PLOTEL, 102, 10, 2
PLOTEL, 103, 2,  11
PLOTEL, 104, 11, 3
$
$ RBE3: GRID 10 gets weighted average of GRIDs 1 and 2
RBE3, 201, , 10, 123456, 1.0, 123456, 1, 2
$
$ RBE3: GRID 11 gets weighted average of GRIDs 2 and 3
RBE3, 202, , 11, 123456, 1.0, 123456, 2, 3
```

---

## Plotly Figure Conventions

- `aspectmode="data"` — axes scaled to data extents (no distortion)
- Height: 600 px fixed, width fills container (`use_container_width=True`)
- Animation duration: 50 ms per frame
- Ghost opacity: 0.5
- Colors: undeformed = `#cccccc`, deformed = `#ff7f0e`, PLOTEL = `#1f77b4`, RBE3 = `#cc2222`, triad RGB = `#cc3333` / `#33aa33` / `#3366cc`
