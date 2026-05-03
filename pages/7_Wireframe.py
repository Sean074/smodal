import numpy as np
import streamlit as st

from core.geometry import (
    GeomModel,
    build_mode_figure,
    build_static_figure,
    expand_rbe3_displacements,
    parse_wireframe_bdf,
)

st.set_page_config(page_title="Wireframe Mode Shape", layout="wide")
st.title("Wireframe Mode Shape")

# ---------------------------------------------------------------------------
# 0. Guards — require upstream data
# ---------------------------------------------------------------------------

if st.session_state.get("df") is None:
    st.warning("No data loaded. Return to the Home page and upload a CSV file.")
    st.stop()

has_simo = st.session_state.get("modal_results") is not None
has_mimo = st.session_state.get("mimo_modal_results") is not None

if not has_simo and not has_mimo:
    st.warning("No modal results found. Run System Identification (Page 4 or 5) first.")
    st.stop()

# ---------------------------------------------------------------------------
# 1. Source selection
# ---------------------------------------------------------------------------

source_options = []
if has_simo:
    source_options.append("SIMO (Page 4)")
if has_mimo:
    source_options.append("MIMO (Page 5)")

source = st.radio("Modal results source", source_options, horizontal=True)
results = (
    st.session_state["mimo_modal_results"]
    if "MIMO" in source
    else st.session_state["modal_results"]
)

fn_arr: np.ndarray = results["fn"]              # (n_modes,) Hz
xi_arr: np.ndarray = results["xi"]              # (n_modes,) fraction
mode_shapes: np.ndarray = results["mode_shapes"]  # (n_outputs, n_modes) complex
output_channels: list = results["output_channels"]
n_modes = int(fn_arr.shape[0])

# ---------------------------------------------------------------------------
# 2. BDF geometry upload
# ---------------------------------------------------------------------------

st.subheader("Geometry")
uploaded = st.file_uploader(
    "Upload NASTRAN BDF / DAT geometry file",
    type=["bdf", "dat"],
    help="Must contain GRID cards. PLOTEL cards define wireframe edges. "
         "RBE3 cards interpolate motion from measurement GRIDs to geometry-only GRIDs.",
)

if uploaded is None:
    st.info(
        "Upload a BDF file containing GRID, PLOTEL, and (optionally) RBE3 cards. "
        "CBAR, MAT1, SPC and other structural cards are ignored."
    )
    st.stop()

try:
    geom: GeomModel = parse_wireframe_bdf(uploaded)
except Exception as exc:
    st.error(f"Failed to parse BDF file: {exc}")
    st.stop()

n_grids = len(geom.grids)
n_plotels = len(geom.plotels)
n_rbe3s = len(geom.rbe3s)

col1, col2, col3 = st.columns(3)
col1.metric("GRIDs", n_grids)
col2.metric("PLOTELs", n_plotels)
col3.metric("RBE3s", n_rbe3s)

with st.expander("Geometry preview", expanded=True):
    st.plotly_chart(build_static_figure(geom), use_container_width=True)

if n_grids == 0:
    st.error("No GRID cards found in the uploaded BDF file.")
    st.stop()

if n_plotels == 0:
    st.warning(
        "No PLOTEL cards found. The animation will show GRID points only — "
        "no wireframe edges. Add PLOTEL cards connecting GRIDs to see a wireframe."
    )

# ---------------------------------------------------------------------------
# 3. Channel → GRID + DOF mapping
# ---------------------------------------------------------------------------

st.subheader("Channel mapping")
st.caption(
    "Map each output channel to the GRID ID at the accelerometer location "
    "and the axis the accelerometer measures."
)

grid_ids = sorted(geom.grids.keys())
dof_options = {"X (1)": 0, "Y (2)": 1, "Z (3)": 2}

mapping: list = []  # one (gid, dof_index) per output_channel

hdr = st.columns([3, 2, 2])
hdr[0].markdown("**Channel**")
hdr[1].markdown("**GRID ID**")
hdr[2].markdown("**Axis**")

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
# 4. Mode selection and animation controls
# ---------------------------------------------------------------------------

st.subheader("Mode selection")

mode_labels = [
    f"Mode {i + 1}  —  {fn_arr[i]:.4g} Hz  (ξ = {xi_arr[i] * 100:.2f}%)"
    for i in range(n_modes)
]
mode_idx = st.selectbox("Select mode", range(n_modes), format_func=lambda i: mode_labels[i])

col_sc, col_fr = st.columns(2)
scale = col_sc.slider(
    "Amplitude scale",
    min_value=0.01,
    max_value=100.0,
    value=1.0,
    step=0.01,
    format="%.2f",
    help="Peak visual displacement. Increase if deformation is too small to see.",
)
n_frames = int(col_fr.number_input(
    "Animation frames",
    min_value=4,
    max_value=60,
    value=20,
    step=1,
    help="Frames per animation cycle. More frames = smoother but slower.",
))

# ---------------------------------------------------------------------------
# 5. Build and display the animated mode shape
# ---------------------------------------------------------------------------

if st.button("Animate mode shape", type="primary"):
    # Extract real part of this mode's shape vector and normalise to peak = 1
    raw_shape = np.real(mode_shapes[:, mode_idx])  # (n_outputs,)
    peak = np.max(np.abs(raw_shape))
    if peak > 0.0:
        raw_shape = raw_shape / peak

    # Build measurement displacement dict: {gid: [dx, dy, dz]}
    meas_disps: dict = {}
    for ch_idx, (gid, dof_idx) in enumerate(mapping):
        d = np.zeros(3)
        d[dof_idx] = float(raw_shape[ch_idx])
        if gid in meas_disps:
            meas_disps[gid] = meas_disps[gid] + d
        else:
            meas_disps[gid] = d

    # Expand to all GRIDs via RBE3 interpolation
    gid_disps = expand_rbe3_displacements(geom, meas_disps)

    fig = build_mode_figure(
        geom,
        gid_disps,
        freq_hz=float(fn_arr[mode_idx]),
        scale=float(scale),
        n_frames=n_frames,
    )
    st.plotly_chart(fig, use_container_width=True)
