import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.geometry import parse_f06
from core.sysid import compute_mac

st.set_page_config(page_title="smodal · MAC", layout="wide")

from core import brand

brand.page_header()

st.title("Modal Assurance Criteria (MAC)")

# ── Section A: Experimental results ──────────────────────────────────────────

st.header("A — Experimental Results")

csv_upload = st.file_uploader(
    "Import modal results CSV (optional)",
    type=["csv"],
    key="mac_csv",
    help="CSV exported from Page 4 (SIMO) or Page 5 (MIMO).",
)

if csv_upload is not None:
    try:
        csv_df = pd.read_csv(csv_upload)
        is_mimo = any(c.startswith("phi_amp_A_") for c in csv_df.columns)
        fn = csv_df["fn_hz"].to_numpy()
        xi = csv_df["xi_pct"].to_numpy() / 100.0
        n_modes = len(fn)
        if is_mimo:
            channels = [c[len("phi_amp_A_") :] for c in csv_df.columns if c.startswith("phi_amp_A_")]
            n_out = len(channels)
            ms = np.zeros((n_out, 2, n_modes), dtype=complex)
            for i, ch in enumerate(channels):
                for run_idx, prefix in enumerate(["A", "B"]):
                    amp = csv_df[f"phi_amp_{prefix}_{ch}"].to_numpy()
                    phase_rad = np.deg2rad(csv_df[f"phi_phase_deg_{prefix}_{ch}"].to_numpy())
                    ms[i, run_idx] = amp * np.exp(1j * phase_rad)
            mode_types = csv_df["type"].tolist() if "type" in csv_df.columns else ["?"] * n_modes
            st.session_state["mimo_modal_results"] = {
                "fn": fn,
                "xi": xi,
                "mode_shapes": ms,
                "output_channels": channels,
                "mode_types": mode_types,
            }
            st.success(f"Loaded MIMO results: {n_modes} modes, {n_out} channels.")
        else:
            channels = [
                c[len("phi_amp_") :]
                for c in csv_df.columns
                if c.startswith("phi_amp_") and not c.startswith("phi_amp_A_") and not c.startswith("phi_amp_B_")
            ]
            n_out = len(channels)
            ms = np.zeros((n_out, n_modes), dtype=complex)
            for i, ch in enumerate(channels):
                amp = csv_df[f"phi_amp_{ch}"].to_numpy()
                phase_rad = np.deg2rad(csv_df[f"phi_phase_deg_{ch}"].to_numpy())
                ms[i] = amp * np.exp(1j * phase_rad)
            st.session_state["modal_results"] = {
                "fn": fn,
                "xi": xi,
                "mode_shapes": ms,
                "output_channels": channels,
            }
            st.success(f"Loaded SIMO results: {n_modes} modes, {n_out} channels.")
    except Exception as exc:
        st.error(f"Failed to parse CSV: {exc}")

has_simo = st.session_state.get("modal_results") is not None
has_mimo = st.session_state.get("mimo_modal_results") is not None

if not has_simo and not has_mimo:
    st.info("Run SIMO/MIMO analysis (Pages 4–5) or import a CSV above.")
    st.stop()

source_options = (["SIMO (Page 4)"] if has_simo else []) + (["MIMO (Page 5)"] if has_mimo else [])
if len(source_options) > 1:
    exp_source = st.radio("Results source", source_options, horizontal=True, key="mac_exp_source")
else:
    exp_source = source_options[0]
    st.caption(f"Using: {exp_source}")
    st.session_state["mac_exp_source"] = exp_source

exp_results = (
    st.session_state.get("mimo_modal_results", {})
    if "MIMO" in exp_source
    else st.session_state.get("modal_results", {})
)

exp_fn = exp_results["fn"]
exp_channels = exp_results["output_channels"]
is_mimo_source = "MIMO" in exp_source

st.metric("Experimental modes", len(exp_fn))

# ── Section B: Analytical model upload ───────────────────────────────────────

st.header("B — Analytical (FE) Model")

f06_upload = st.file_uploader(
    "NASTRAN SOL 103 F06 file",
    type=["f06", "out", "txt"],
    key="mac_f06_upload",
    help="NASTRAN SOL 103 output file with REAL EIGENVALUES and EIGENVECTOR sections.",
)

if f06_upload is not None:
    if st.session_state.get("_mac_f06_name") != f06_upload.name:
        try:
            st.session_state["mac_f06_data"] = parse_f06(f06_upload)
            st.session_state["_mac_f06_name"] = f06_upload.name
        except Exception as exc:
            st.error(f"Failed to parse F06: {exc}")

f06_data = st.session_state.get("mac_f06_data")

if f06_data is None:
    st.info("Upload a NASTRAN SOL 103 F06 file above.")
    st.stop()

n_fe_modes = len(f06_data["frequencies_hz"])
st.metric("FE modes", n_fe_modes)
if n_fe_modes > 0:
    st.caption(
        f"Modes: {', '.join(f'{f:.4g} Hz' for f in f06_data['frequencies_hz'][:6])}" + (" …" if n_fe_modes > 6 else "")
    )

# ── Section C: Channel-to-DOF mapping ────────────────────────────────────────

st.header("C — Channel-to-DOF Mapping")
st.caption("Map each experimental output channel to the GRID at the sensor location and the axis the sensor measures.")

grid_ids = sorted({gid for shape in f06_data["mode_shapes"] for gid in shape})
dof_options = {"X (1)": 0, "Y (2)": 1, "Z (3)": 2}

hdr = st.columns([3, 2, 2])
hdr[0].markdown("**Channel**")
hdr[1].markdown("**GRID ID**")
hdr[2].markdown("**Axis**")

mapping: list[tuple[int, int]] = []
for ch in exp_channels:
    row = st.columns([3, 2, 2])
    row[0].write(ch)
    gid_sel = row[1].selectbox("", grid_ids, key=f"mac_gid_{ch}", label_visibility="collapsed")
    dof_sel = row[2].selectbox("", list(dof_options.keys()), index=2, key=f"mac_dof_{ch}", label_visibility="collapsed")
    mapping.append((gid_sel, dof_options[dof_sel]))

st.session_state["mac_mapping"] = mapping

# ── Section D: Compute MAC ────────────────────────────────────────────────────

st.header("D — Compute MAC")
if is_mimo_source:
    st.caption("MAC uses Run A (reference) mode shape amplitudes only.")

if st.button("Compute MAC", type="primary"):
    n_sensors = len(exp_channels)

    # Build experimental mode shape matrix (n_sensors, n_exp_modes)
    if is_mimo_source:
        phi_exp = exp_results["mode_shapes"][:, 0, :]
    else:
        phi_exp = exp_results["mode_shapes"]

    # Build FE mode shape matrix (n_sensors, n_fe_modes)
    phi_fe = np.zeros((n_sensors, n_fe_modes))
    for ch_idx, (gid, dof_idx) in enumerate(mapping):
        for mode_j, shape_dict in enumerate(f06_data["mode_shapes"]):
            if gid in shape_dict:
                phi_fe[ch_idx, mode_j] = shape_dict[gid][dof_idx]

    mac_matrix = compute_mac(phi_fe, phi_exp)  # (n_fe_modes, n_exp_modes)

    st.session_state["mac_matrix"] = mac_matrix
    st.session_state["mac_fe_freqs"] = f06_data["frequencies_hz"]
    st.session_state["mac_exp_freqs"] = exp_fn

# ── Section E: MAC plot ───────────────────────────────────────────────────────

st.header("E — MAC Matrix")

mac_matrix = st.session_state.get("mac_matrix")
if mac_matrix is None:
    st.info("Click Compute MAC above.")
    st.stop()

mac_fe_freqs: np.ndarray = st.session_state.get("mac_fe_freqs", np.array([]))
mac_exp_freqs: np.ndarray = st.session_state.get("mac_exp_freqs", np.array([]))

exp_labels = [f"Mode {i + 1}  —  {fn:.4g} Hz" for i, fn in enumerate(mac_exp_freqs)]
fe_labels = [f"Mode {i + 1}  —  {fn:.4g} Hz" for i, fn in enumerate(mac_fe_freqs)]

fig = go.Figure(
    go.Heatmap(
        z=mac_matrix,
        x=exp_labels,
        y=fe_labels,
        zmin=0.0,
        zmax=1.0,
        colorscale=[[0.0, "darkblue"], [0.5, "green"], [1.0, "red"]],
        text=[[f"{v:.2f}" for v in row] for row in mac_matrix],
        texttemplate="%{text}",
    )
)
fig.update_layout(
    xaxis_title="Experimental Mode (Hz)",
    yaxis_title="Analytical Mode (Hz)",
    height=500,
)
st.plotly_chart(fig, use_container_width=True)

# ── Section F: Frequency comparison table ────────────────────────────────────

st.header("F — Frequency Comparison")

rows = []
for fe_idx, fe_f in enumerate(mac_fe_freqs):
    best_exp_idx = int(np.argmax(mac_matrix[fe_idx, :]))
    exp_f = float(mac_exp_freqs[best_exp_idx])
    delta_f = exp_f - fe_f
    delta_pct = delta_f / fe_f * 100.0 if fe_f != 0 else float("nan")
    rows.append(
        {
            "FE Mode": fe_idx + 1,
            "FE Freq (Hz)": round(fe_f, 4),
            "Exp Mode": best_exp_idx + 1,
            "Exp Freq (Hz)": round(exp_f, 4),
            "Δf (Hz)": round(delta_f, 4),
            "Δf (%)": round(delta_pct, 1),
            "MAC": round(float(mac_matrix[fe_idx, best_exp_idx]), 3),
        }
    )

df_table = pd.DataFrame(rows)
st.dataframe(df_table, use_container_width=True)
