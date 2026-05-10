# Page 6 MAC

## Purpose

Unlike the MAC plots on the SIMO and MIMO pages (which compare experimental runs against each other), this page compares an **analytical (FE) model** against **experimentally extracted** mode shapes and frequencies to produce a standard MAC matrix plot.

The user selects which FE model GRIDs correspond to the measured accelerometer locations (channels), extracts the mode shape values at those DOFs from both sources, and computes the MAC.

Data sources required:
- Experimental modal results from Page 4 (SIMO) or Page 5 (MIMO), or an imported CSV.
- Analytical results: a NASTRAN SOL 103 F06 output file (same format as Page 7 — Wireframe).

The user must select which FE GRIDs and DOF axes match each experimental output channel.

---

## MAC Plot Specification

- **X axis (Comparison):** Experimental mode labels — `Mode N — {fn:.4g} Hz`
- **Y axis (Reference):** Analytical (FE) mode labels — `Mode N — {fn:.4g} Hz`
- **Cell value:** MAC coefficient for that (exp mode, FE mode) pair.
- **Colorscale:** `darkblue` at 0.0 → `green` at 0.5 → `red` at 1.0
- Cell text annotation: MAC value to 2 decimal places.

## Frequency Comparison Table

Paired table matching each experimental mode to the closest FE mode (by MAC value or frequency proximity).

Columns: `FE Mode | FE Freq (Hz) | Exp Mode | Exp Freq (Hz) | Δf (Hz) | Δf (%)`

---

## References

- https://community.sw.siemens.com/s/article/modal-assurance-criterion-mac
- https://www.svibs.com/resources/ARTeMIS_Modal_Help/Generic%20Modal%20Assurance%20Criterion%20Window.html
- https://2022.help.altair.com/2022/hwdesktop/hwx/topics/panels/nvh_mac_hv_r.htm

---

## Code Standards

Follow patterns established in `pages/4_SIMO.py`, `pages/5_MIMO.py`, and `pages/7_Wireframe.py`.

### Imports

```python
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.geometry import parse_f06
from core.sysid import compute_mac   # new function — see core module section below
```

### Page config

```python
st.set_page_config(page_title="MAC", layout="wide")
st.title("Modal Assurance Criteria (MAC)")
```

### Section headers

Use the exact comment style from other pages:

```python
# ── Section A: Experimental results ──────────────────────────────────────────
```

### Guards

Check for required data at the top of each section. Use `st.info(...)` followed by `st.stop()` — not `st.warning`.

```python
if exp_results is None:
    st.info("Run SIMO/MIMO analysis (Pages 4–5) or import a CSV above.")
    st.stop()
```

### Session state keys (MAC page)

| Key | Set by | Consumed by |
|---|---|---|
| `mac_exp_source` | Section A radio | Section D (compute) |
| `mac_f06_data` | Section B upload | Section C, D |
| `mac_mapping` | Section C table | Section D (compute) |
| `mac_matrix` | Section D (compute) | Section E (plot) |
| `mac_fe_freqs` | Section D (compute) | Section E (plot), Section F (table) |
| `mac_exp_freqs` | Section D (compute) | Section E (plot), Section F (table) |

### Plotly heatmap pattern

```python
fig = go.Figure(go.Heatmap(
    z=mac_matrix,
    x=exp_labels,
    y=fe_labels,
    zmin=0.0,
    zmax=1.0,
    colorscale=[[0.0, "darkblue"], [0.5, "green"], [1.0, "red"]],
    text=[[f"{v:.2f}" for v in row] for row in mac_matrix],
    texttemplate="%{text}",
))
fig.update_layout(
    xaxis_title="Experimental Mode (Hz)",
    yaxis_title="Analytical Mode (Hz)",
    height=500,
)
st.plotly_chart(fig, use_container_width=True)
```

---

## Core Module Addition

Add `compute_mac` to **`core/sysid.py`** (no new file needed).

```python
def compute_mac(phi_ref: np.ndarray, phi_comp: np.ndarray) -> np.ndarray:
    """MAC matrix between two sets of mode shapes.

    Parameters
    ----------
    phi_ref  : (n_dof, n_ref)  — reference (FE) mode shapes, real or complex
    phi_comp : (n_dof, n_comp) — comparison (exp) mode shapes, real or complex

    Returns
    -------
    mac : (n_ref, n_comp) MAC values in [0, 1]
    """
    num = np.abs(phi_ref.conj().T @ phi_comp) ** 2
    denom = (
        np.sum(np.abs(phi_ref) ** 2, axis=0)[:, None]
        * np.sum(np.abs(phi_comp) ** 2, axis=0)[None, :]
    )
    return num / np.maximum(denom, np.finfo(float).tiny)
```

- `phi_ref` columns = FE mode shapes at sensor DOFs (n_sensors × n_fe_modes)
- `phi_comp` columns = experimental mode shapes at sensor DOFs (n_sensors × n_exp_modes)
- Result shape: `(n_fe_modes, n_exp_modes)` — rows = FE (y axis), cols = exp (x axis)

---

## Data Structures

### Experimental modal results (`modal_results` from SIMO)

```python
{
    "fn":              np.ndarray,   # (n_modes,) Hz
    "xi":              np.ndarray,   # (n_modes,) fraction (not %)
    "mode_shapes":     np.ndarray,   # (n_outputs, n_modes) complex residues
    "output_channels": list[str],    # channel names, len n_outputs
}
```

### Experimental modal results (`mimo_modal_results` from MIMO)

```python
{
    "fn":              np.ndarray,   # (n_modes,) Hz
    "xi":              np.ndarray,   # (n_modes,) fraction
    "mode_shapes":     np.ndarray,   # (n_outputs, 2, n_modes) complex — run A/B
    "output_channels": list[str],
}
```

### Analytical modal results (`parse_f06` return)

```python
{
    "frequencies_hz": np.ndarray,       # (n_fe_modes,)
    "mode_shapes":    list[dict],        # len n_fe_modes; each dict: gid (int) -> np.array([T1,T2,T3])
}
```

### Extracting mode shape vectors for MAC

To build the `(n_sensors, n_exp_modes)` experimental matrix:

```python
# SIMO: mode_shapes is (n_outputs, n_modes) complex
phi_exp = np.real(exp_results["mode_shapes"])   # take real part of residues

# MIMO: mode_shapes is (n_outputs, 2, n_modes) — use Run A
phi_exp = np.real(exp_results["mode_shapes"][:, 0, :])
```

To build the `(n_sensors, n_fe_modes)` FE matrix using the channel mapping:

```python
n_sensors = len(channels)
n_fe_modes = len(f06_data["frequencies_hz"])
phi_fe = np.zeros((n_sensors, n_fe_modes))
for ch_idx, (gid, dof_idx) in enumerate(mapping):
    for mode_j, shape_dict in enumerate(f06_data["mode_shapes"]):
        if gid in shape_dict:
            phi_fe[ch_idx, mode_j] = shape_dict[gid][dof_idx]
```

---

## Step-by-Step Implementation Plan

### Step 1 — Add `compute_mac` to `core/sysid.py`

File: `core/sysid.py`

- Append the `compute_mac` function (formula above) at the bottom of the file.
- No changes to existing functions.

---

### Step 2 — Replace the stub in `pages/6_MAC.py`

Replace the current 7-line stub entirely. Structure:

#### Section A: Experimental results

1. Show optional CSV import uploader (same pattern as `pages/7_Wireframe.py` lines 56–103).
2. Check session_state for `modal_results` and `mimo_modal_results`.
3. If both present, show source radio: `["SIMO (Page 4)", "MIMO (Page 5)"]`.
4. Extract `exp_fn`, `exp_xi`, `exp_mode_shapes`, `exp_channels` from the selected source.
5. Guard: if no experimental results available, `st.info(...)` + `st.stop()`.

#### Section B: Analytical model upload

1. `st.file_uploader` for F06 file (types `["f06", "out", "txt"]`) — name-guarded load like other pages.
2. On new file: call `parse_f06(upload)` from `core.geometry`, store in `st.session_state["mac_f06_data"]`.
3. Show metric: FE mode count; show first 6 frequencies as caption.
4. Guard: if no F06 loaded, `st.info(...)` + `st.stop()`.

#### Section C: Channel-to-DOF mapping

1. Extract unique GRID IDs present across all F06 mode shape dicts: `sorted({gid for s in f06_data["mode_shapes"] for gid in s})`.
2. Render mapping table (same layout as `pages/7_Wireframe.py` lines 132–150):
   - One row per experimental channel.
   - Columns: **Channel** | **GRID ID** (selectbox) | **Axis** (selectbox X/Y/Z).
   - Persist selections via session_state keys `mac_gid_{ch}` and `mac_dof_{ch}`.
3. Build `mapping: list[tuple[int, int]]` — `(gid, dof_idx)` per channel.

#### Section D: Compute MAC

1. "Compute MAC" button (`type="primary"`).
2. On click:
   - Build `phi_exp` matrix `(n_sensors, n_exp_modes)` — real part of experimental residues.
   - Build `phi_fe` matrix `(n_sensors, n_fe_modes)` — FE DOF values at mapped GRIDs.
   - Call `compute_mac(phi_fe, phi_exp)` → result shape `(n_fe_modes, n_exp_modes)`.
   - Store in `st.session_state["mac_matrix"]`, `"mac_fe_freqs"`, `"mac_exp_freqs"`.

#### Section E: MAC plot

1. Guard: if `mac_matrix` not in session_state, `st.info("Click Compute MAC above.")` + `st.stop()`.
2. Build label lists:
   - `exp_labels = [f"Mode {i+1}  —  {fn:.4g} Hz" for i, fn in enumerate(mac_exp_freqs)]`
   - `fe_labels  = [f"Mode {i+1}  —  {fn:.4g} Hz" for i, fn in enumerate(mac_fe_freqs)]`
3. Render `go.Heatmap` with colorscale and cell text annotations (see pattern above).
4. `st.plotly_chart(fig, use_container_width=True)`.

#### Section F: Frequency comparison table

1. For each FE mode, find the experimental mode with the highest MAC value.
2. Build a `pd.DataFrame` with columns:
   `FE Mode | FE Freq (Hz) | Exp Mode | Exp Freq (Hz) | Δf (Hz) | Δf (%) | MAC`
3. Format Δf (%) to 1 decimal place.
4. `st.dataframe(df, use_container_width=True)`.

---

## Verification Checklist

- [ ] `compute_mac` returns 1.0 on the diagonal when `phi_ref == phi_comp`.
- [ ] MAC matrix shape is `(n_fe_modes, n_exp_modes)` — FE on rows (y), exp on cols (x).
- [ ] Colorscale renders dark blue at 0, green at 0.5, red at 1.0.
- [ ] Frequency table Δf (%) is `(exp_f - fe_f) / fe_f * 100`.
- [ ] CSV import path works (loads same as SIMO/MIMO session state).
- [ ] Page shows `st.info` guard (not crash) when no data is present.
- [ ] MIMO path uses Run A (`mode_shapes[:, 0, :]`), not Run B.
