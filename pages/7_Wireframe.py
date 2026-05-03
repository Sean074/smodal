import numpy as np
import streamlit as st

from core.geometry import (
    GeomModel,
    build_mode_figure,
    build_static_figure,
    expand_rbe3_displacements,
    parse_wireframe_bdf,
)

st.set_page_config(page_title="Wireframe", layout="wide")
st.title("7 – Wireframe Mode Shape")

# ---------------------------------------------------------------------------
# 1. BDF geometry upload  (no prerequisites — works standalone)
# ---------------------------------------------------------------------------

st.subheader("Geometry")
uploaded = st.file_uploader(
    "Upload NASTRAN BDF / DAT geometry file",
    type=["bdf", "dat"],
    help=(
        "GRID cards define node positions; PLOTEL cards draw wireframe edges; "
        "RBE3 cards (optional) interpolate motion from measurement GRIDs to "
        "geometry-only GRIDs. `data/input/sample_plate.dat` is provided as an example."
    ),
)

if uploaded is None:
    st.info(
        "Upload a BDF/DAT file to preview the geometry.  \n"
        "**Example:** `data/input/sample_plate.dat` — 1 m × 5 m flat plate with "
        "18 mesh GRIDs, 27 PLOTELs, 2 accelerometer GRIDs (19 & 20), "
        "and 18 RBE3 interpolation elements."
    )
    st.stop()

try:
    geom: GeomModel = parse_wireframe_bdf(uploaded)
except Exception as exc:
    st.error(f"Failed to parse BDF file: {exc}")
    st.stop()

if len(geom.grids) == 0:
    st.error("No GRID cards found in the uploaded file.")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("GRIDs", len(geom.grids))
c2.metric("PLOTELs", len(geom.plotels))
c3.metric("RBE3s", len(geom.rbe3s))

if len(geom.plotels) == 0:
    st.warning(
        "No PLOTEL cards found — only GRID point markers will be drawn. "
        "Add PLOTEL cards to see wireframe edges."
    )

with st.expander("Geometry preview", expanded=True):
    st.plotly_chart(build_static_figure(geom), use_container_width=True)

# ---------------------------------------------------------------------------
# 2. Modal results — from session state or CSV import
# ---------------------------------------------------------------------------

st.subheader("Modal Results")

csv_upload = st.file_uploader(
    "Import modal results CSV (optional — skip if analysis is already loaded)",
    type=["csv"],
    help=(
        "Upload a CSV exported from Page 4 (SIMO) or Page 5 (MIMO). "
        "Columns must follow the standard export format."
    ),
)

if csv_upload is not None:
    import pandas as pd

    try:
        csv_df = pd.read_csv(csv_upload)
        is_mimo = any(c.startswith("phi_amp_A_") for c in csv_df.columns)

        fn = csv_df["fn_hz"].to_numpy()
        xi = csv_df["xi_pct"].to_numpy() / 100.0
        n_modes = len(fn)

        if is_mimo:
            channels = [c[len("phi_amp_A_"):] for c in csv_df.columns if c.startswith("phi_amp_A_")]
            n_out = len(channels)
            mode_shapes = np.zeros((n_out, 2, n_modes), dtype=complex)
            for i, ch in enumerate(channels):
                for run_idx, prefix in enumerate(["A", "B"]):
                    amp = csv_df[f"phi_amp_{prefix}_{ch}"].to_numpy()
                    phase_rad = np.deg2rad(csv_df[f"phi_phase_deg_{prefix}_{ch}"].to_numpy())
                    mode_shapes[i, run_idx] = amp * np.exp(1j * phase_rad)
            mode_types = csv_df["type"].tolist() if "type" in csv_df.columns else ["?"] * n_modes
            st.session_state["mimo_modal_results"] = {
                "fn": fn,
                "xi": xi,
                "mode_shapes": mode_shapes,
                "output_channels": channels,
                "mode_types": mode_types,
            }
            st.success(f"Loaded MIMO results: {n_modes} modes, {n_out} channels.")
        else:
            channels = [
                c[len("phi_amp_"):] for c in csv_df.columns
                if c.startswith("phi_amp_") and not c.startswith("phi_amp_A_") and not c.startswith("phi_amp_B_")
            ]
            n_out = len(channels)
            mode_shapes = np.zeros((n_out, n_modes), dtype=complex)
            for i, ch in enumerate(channels):
                amp = csv_df[f"phi_amp_{ch}"].to_numpy()
                phase_rad = np.deg2rad(csv_df[f"phi_phase_deg_{ch}"].to_numpy())
                mode_shapes[i] = amp * np.exp(1j * phase_rad)
            st.session_state["modal_results"] = {
                "fn": fn,
                "xi": xi,
                "mode_shapes": mode_shapes,
                "output_channels": channels,
            }
            st.success(f"Loaded SIMO results: {n_modes} modes, {n_out} channels.")

    except Exception as exc:
        st.error(f"Failed to parse CSV: {exc}")

has_simo = st.session_state.get("modal_results") is not None
has_mimo = st.session_state.get("mimo_modal_results") is not None

if not has_simo and not has_mimo:
    st.info(
        "Geometry loaded successfully.  \n"
        "To animate mode shapes, either:  \n"
        "- Upload a modal results CSV above, **or**  \n"
        "- Run System Identification on Page 4 (SIMO) or Page 5 (MIMO) first."
    )
    st.stop()

# ---------------------------------------------------------------------------
# 3. Source + mode selection
# ---------------------------------------------------------------------------

st.subheader("Mode shape animation")

source_options = (["SIMO (Page 4)"] if has_simo else []) + (["MIMO (Page 5)"] if has_mimo else [])
source = st.radio("Modal results source", source_options, horizontal=True)
results = (
    st.session_state["mimo_modal_results"]
    if "MIMO" in source
    else st.session_state["modal_results"]
)

fn_arr: np.ndarray = results["fn"]               # (n_modes,)
xi_arr: np.ndarray = results["xi"]               # (n_modes,)
mode_shapes: np.ndarray = results["mode_shapes"]  # (n_outputs, n_modes) complex
output_channels: list = results["output_channels"]
n_modes = int(fn_arr.shape[0])

# ---------------------------------------------------------------------------
# 4. Channel → GRID + DOF mapping
# ---------------------------------------------------------------------------

st.caption(
    "Map each output channel to the GRID at the sensor location "
    "and the axis the sensor measures."
)

grid_ids = sorted(geom.grids.keys())
dof_options = {"X (1)": 0, "Y (2)": 1, "Z (3)": 2}

hdr = st.columns([3, 2, 2])
hdr[0].markdown("**Channel**")
hdr[1].markdown("**GRID ID**")
hdr[2].markdown("**Axis**")

mapping: list = []  # [(gid, dof_index), ...] — one entry per output channel
for ch in output_channels:
    row = st.columns([3, 2, 2])
    row[0].write(ch)
    gid_sel = row[1].selectbox(
        "",
        grid_ids,
        key=f"wf_gid_{ch}",
        label_visibility="collapsed",
    )
    dof_sel = row[2].selectbox(
        "",
        list(dof_options.keys()),
        index=2,  # default Z
        key=f"wf_dof_{ch}",
        label_visibility="collapsed",
    )
    mapping.append((gid_sel, dof_options[dof_sel]))

# ---------------------------------------------------------------------------
# 5. Animation controls
# ---------------------------------------------------------------------------

mode_labels = [
    f"Mode {i + 1}  —  {fn_arr[i]:.4g} Hz  (ξ = {xi_arr[i] * 100:.2f}%)"
    for i in range(n_modes)
]
mode_idx = st.selectbox(
    "Select mode", range(n_modes), format_func=lambda i: mode_labels[i]
)

c_sc, c_fr = st.columns(2)
scale = c_sc.slider(
    "Amplitude scale",
    min_value=0.01,
    max_value=100.0,
    value=1.0,
    step=0.01,
    format="%.2f",
    help="Peak visual displacement. Increase if deformation is too small to see.",
)
n_frames = int(c_fr.number_input(
    "Animation frames",
    min_value=4,
    max_value=60,
    value=20,
    step=1,
    help="Frames per animation cycle. More = smoother but slower to build.",
))

# ---------------------------------------------------------------------------
# 6. Build and display animated figure
# ---------------------------------------------------------------------------

if st.button("Animate mode shape", type="primary"):
    # MIMO stores (n_out, 2, n_modes); SIMO stores (n_outputs, n_modes)
    if mode_shapes.ndim == 3:
        raw_shape = np.real(mode_shapes[:, 0, mode_idx])
    else:
        raw_shape = np.real(mode_shapes[:, mode_idx])  # (n_outputs,)
    peak = np.max(np.abs(raw_shape))
    if peak > 0.0:
        raw_shape = raw_shape / peak

    # Assemble measured displacement dict {gid: [dx, dy, dz]}
    meas_disps: dict = {}
    for ch_idx, (gid, dof_idx) in enumerate(mapping):
        d = np.zeros(3)
        d[dof_idx] = float(raw_shape[ch_idx])
        meas_disps[gid] = meas_disps.get(gid, np.zeros(3)) + d

    gid_disps = expand_rbe3_displacements(geom, meas_disps)

    fig = build_mode_figure(
        geom,
        gid_disps,
        freq_hz=float(fn_arr[mode_idx]),
        scale=float(scale),
        n_frames=n_frames,
    )
    st.plotly_chart(fig, use_container_width=True)
