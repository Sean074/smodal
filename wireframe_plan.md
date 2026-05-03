# Wireframe Visualizer — Implementation Plan

## Overview

Implement Page 7 (Wireframe Mode Shape) of the modal analysis Streamlit app. The page animates experimental mode shapes from Pages 4/5 on a 3D structural wireframe defined by a NASTRAN BDF geometry file. Geometry-only nodes (without direct accelerometer measurement) get their motion interpolated from nearby measurement nodes via RBE3 elements.

---

## Existing Resources

The `sbeam` project at `../sbeam` already contains production-quality BDF parsing and Plotly 3D visualization code. The wireframe page adapts this rather than starting from scratch:

| sbeam source | Adapted into |
|---|---|
| `sbeam/parser/bdf_reader.py` — GRID, PLOTEL, RBE3 handlers | `core/geometry.py` |
| `sbeam/viewer/geometry.py` — Plotly 3D traces and animated mode figure | `core/geometry.py` |
| `sbeam/sample/beam_vib.bdf` — sample BDF with PLOTEL and RBE3 | Use as test file |

No `sbeam` package import is used — logic is extracted and adapted directly.

---

## Implementation Steps

### Step 1 — `core/geometry.py` (complete)

**Status: Done**

New module containing:
- Dataclasses: `Grid`, `Plotel`, `Rbe3`, `GeomModel`
- `parse_wireframe_bdf(file_like)` — BDF parser (GRID, PLOTEL, RBE3 only)
- `expand_rbe3_displacements(geom, meas_disps)` — weighted interpolation to all GRIDs
- `build_static_figure(geom)` — undeformed wireframe preview
- `build_mode_figure(geom, gid_disps, freq_hz, scale, n_frames)` — animated mode shape

---

### Step 2 — `pages/7_Wireframe.py` (complete)

**Status: Done**

Replaced the stub page with a full Streamlit page:

1. **Guard** — requires `df` in session state AND at least one of `modal_results` / `mimo_modal_results`
2. **Source selector** — radio button to choose SIMO or MIMO results (only shows options that exist)
3. **BDF upload** — `st.file_uploader` → `parse_wireframe_bdf` → metrics (n_grids, n_plotels, n_rbe3s) + static preview
4. **Channel mapping** — one row per output channel: selectbox for GRID ID + selectbox for axis (X/Y/Z defaulting to Z)
5. **Mode selector + controls** — selectbox (fn, damping label) + scale slider + frame count
6. **Animate button** — builds `meas_disps`, calls `expand_rbe3_displacements`, calls `build_mode_figure`, renders chart

---

### Step 3 — `wireframe_visualizer.md` (complete)

**Status: Done**

Code standard document covering BDF format, session state, `core/geometry.py` public API, mode shape handling, channel mapping convention, and Plotly figure conventions.

---

## Testing

### Quick smoke test (geometry only)

1. Upload `../sbeam/sample/beam_vib.bdf` as the BDF file.
2. Verify: 7 GRIDs, 1 PLOTEL, 1 RBE3 shown in metrics.
3. Verify the static preview shows 7 nodes, one dashed PLOTEL edge (nodes 5→7), and one red RBE3 link (node 7 ← node 6).

### End-to-end test (with modal results)

1. Run Pages 1 → 4 with `data/input/sample_3ch.csv`.
2. Navigate to Page 7.
3. Upload `../sbeam/sample/beam_vib.bdf`.
4. Map one channel to GRID 6, axis Z.
5. Select Mode 1, leave scale at 1.0.
6. Click **Animate mode shape**.
7. Confirm: orange deformed PLOTEL line oscillates; GRID 7 moves proportionally to GRID 6 (via RBE3 interpolation).

---

## Building a Geometry BDF

Minimum required content:

```
$ Measurement grids (at accelerometer locations)
GRID, <gid>, , <x>, <y>, <z>
...

$ Optional geometry-only grids
GRID, <gid>, , <x>, <y>, <z>
...

$ Wireframe edges
PLOTEL, <eid>, <g1>, <g2>
...

$ Optional: interpolate geometry-only grids from measurement grids
RBE3, <eid>, , <refgrid>, 123456, 1.0, 123456, <meas_gid1>, <meas_gid2>
...
```

**Rules:**
- All GRIDs referenced in PLOTEL or RBE3 must be defined before those cards (or the parser will warn and skip them).
- CP field (coordinate system) is ignored — positions must be in global Cartesian.
- Free-field (comma) and fixed-field (8-char columns) formats are both accepted.
- `$` starts an inline comment on any line.

---

## Extension Points (future work)

| Feature | Notes |
|---|---|
| Complex mode animation | Use `Re(shape * exp(jωt))` instead of `Re(shape) * sin(ωt)` — captures phase relationships |
| Multi-DOF per channel | Currently one axis per channel; extend mapping to allow 3-axis accelerometers |
| Auto-mapping by channel name | Parse GRID IDs from channel names (e.g., `G101_Z`) to pre-populate mapping |
| MAC colour overlay | Colour GRID markers by MAC value to show spatial correlation |
| Export geometry CSV | Allow download of deformed GRID coordinates per frame |
