## Page 7 — Wireframe Mode Shape

Two-column side-by-side comparison of **analytical (FE)** and **experimental (test)** mode shapes on 3D NASTRAN wireframe geometry.

Note: the sbeam project (`/Users/seanomeara/Documents/99-Tests/sbeam`) uses the same BDF/F06 format and its parser/viewer code may be referenced for implementation patterns.

Example BDF and F06: `data/input/example_model/`

---

### Data Inputs

| Column | Geometry | Mode Shapes |
|---|---|---|
| Model (FE) | NASTRAN BDF (GRID + PLOTEL cards) | NASTRAN F06 SOL 103 eigenvectors |
| Test (Exp) | NASTRAN BDF (GRID + PLOTEL + optional RBE3 cards) | SIMO/MIMO modal results from Pages 4–5 (or CSV import) |

---

### Implementation Plan

#### Step 1 — F06 parser (`core/geometry.py`)

Add `parse_f06(file_like)` → `{'frequencies_hz': ndarray(n_modes), 'mode_shapes': list[dict[gid → ndarray(3)]]}`.

- Parse `R E A L   E I G E N V A L U E S` table → extract Hz (CYCLES column).
- Parse each `E I G E N V E C T O R   NO. k` section → per-GRID T1/T2/T3 (TYPE == "G" rows).
- No channel mapping needed — GRID IDs in F06 map directly to the FE BDF GRIDs.

#### Step 2 — Camera view helper (`core/geometry.py`)

Add `_apply_camera(fig, view)` and `_CAMERA_VIEWS` dict:

- `'3D'` → Plotly default
- `'X-Y'` → camera eye (0, 0, 2.5) looking down Z
- `'X-Z'` → camera eye (0, −2.5, 0) looking along Y
- `'Y-Z'` → camera eye (2.5, 0, 0) looking along X

Add optional `view='3D'` parameter to `build_static_figure` and `build_mode_figure`.

#### Step 3 — Static mode figure (`core/geometry.py`)

Add `build_static_mode_figure(geom, gid_disps, freq_hz, scale, phase_deg, view)`.

Renders a single frozen frame: `amplitude = scale * sin(radians(phase_deg))`. Same ghost + deformed trace layout as `build_mode_figure` but no Plotly frames or play buttons.

#### Step 4 — Page restructure (`pages/7_Wireframe.py`)

**4a. Geometry Setup** (expander, expanded):
- Left sub-column: Test BDF upload → `geom_test`
- Right sub-column: FE BDF upload → `geom_fe`; F06 upload → `f06_data`

**4b. Test Channel Mapping** (expander, collapsed):
- Map each experimental output channel to a GRID ID and axis (X/Y/Z).
- Shown only when `geom_test` and experimental modal results are available.

**4c. Global Display Controls** (always visible once data is loaded):
- **View**: radio `[3D | X-Y | X-Z | Y-Z]`
- **Display**: radio `[Animate | Static]`
  - If Static: phase slider 0–360°
- **Scale**: slider 0.01–100 (default 1.0)
- **Frames**: number input 4–60 (default 20; hidden when Static)

**4d. Two-Column Comparison**:

```
| Model (FE)                        | Test (Experiment)                   |
|-----------------------------------|-------------------------------------|
| Mode selector (from F06 modes)    | Source selector (SIMO / MIMO)       |
|                                   | Mode selector (from exp results)    |
| [Show Model] button               | [Show Test] button                  |
| Plotly 3D figure                  | Plotly 3D figure                    |
```

Both figures use the shared view, display mode, scale and frame settings from §4c.

---

### Session State

| Key | Set by | Consumed by |
|---|---|---|
| `modal_results` | Page 4 (SIMO) | Test column |
| `mimo_modal_results` | Page 5 (MIMO) | Test column |

---

### Files Changed

| File | Changes |
|---|---|
| `core/geometry.py` | `parse_f06`, `_apply_camera`, `_CAMERA_VIEWS`, `build_static_mode_figure`; `view` param on existing figure builders |
| `pages/7_Wireframe.py` | Full restructure per §4 |
