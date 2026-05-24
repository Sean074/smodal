from __future__ import annotations

import numpy as np
import streamlit as st

from core.geometry import (
    GeomModel,
    build_mode_figure,
    build_static_figure,
    build_static_mode_figure,
    expand_rbe3_displacements,
    parse_f06,
    parse_wireframe_bdf,
)

st.set_page_config(page_title="smodal · Wireframe", layout="wide")

from core import brand

brand.page_header()

st.title("Wireframe Mode Shape")

# ---------------------------------------------------------------------------
# 1. Geometry Setup — experimental geometry + modal results
# ---------------------------------------------------------------------------

geom_test: GeomModel | None = None
exp_fn: np.ndarray | None = None
exp_xi: np.ndarray | None = None
exp_mode_shapes: np.ndarray | None = None
exp_channels: list | None = None
n_exp_modes: int = 0
mapping: list = []

with st.expander("Experimental Setup", expanded=True):
    col_bdf, col_modal = st.columns(2)

    with col_bdf:
        st.markdown("**Test (Experimental) Geometry**")
        test_bdf = st.file_uploader(
            "Test BDF / DAT",
            type=["bdf", "dat"],
            key="wf_test_bdf",
            help="GRID + PLOTEL + optional RBE3 cards for the test wireframe.",
        )
        if test_bdf is not None:
            try:
                geom_test = parse_wireframe_bdf(test_bdf)
                c1, c2, c3 = st.columns(3)
                c1.metric("GRIDs", len(geom_test.grids))
                c2.metric("PLOTELs", len(geom_test.plotels))
                c3.metric("RBE3s", len(geom_test.rbe3s))
                with st.expander("Preview", expanded=False):
                    st.plotly_chart(build_static_figure(geom_test), use_container_width=True)
            except Exception as exc:
                st.error(f"Failed to parse Test BDF: {exc}")

    with col_modal:
        st.markdown("**Modal Results**")
        csv_upload = st.file_uploader(
            "Import modal results CSV (optional)",
            type=["csv"],
            key="wf_csv",
            help="CSV exported from Page 4 (SIMO) or Page 5 (MIMO).",
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
                    ms = np.zeros((n_out, 2, n_modes), dtype=complex)
                    for i, ch in enumerate(channels):
                        for run_idx, prefix in enumerate(["A", "B"]):
                            amp = csv_df[f"phi_amp_{prefix}_{ch}"].to_numpy()
                            phase_rad = np.deg2rad(csv_df[f"phi_phase_deg_{prefix}_{ch}"].to_numpy())
                            ms[i, run_idx] = amp * np.exp(1j * phase_rad)
                    mode_types = csv_df["type"].tolist() if "type" in csv_df.columns else ["?"] * n_modes
                    st.session_state["mimo_modal_results"] = {
                        "fn": fn, "xi": xi, "mode_shapes": ms,
                        "output_channels": channels, "mode_types": mode_types,
                    }
                    st.success(f"Loaded MIMO results: {n_modes} modes, {n_out} channels.")
                else:
                    channels = [
                        c[len("phi_amp_"):] for c in csv_df.columns
                        if c.startswith("phi_amp_") and not c.startswith("phi_amp_A_") and not c.startswith("phi_amp_B_")
                    ]
                    n_out = len(channels)
                    ms = np.zeros((n_out, n_modes), dtype=complex)
                    for i, ch in enumerate(channels):
                        amp = csv_df[f"phi_amp_{ch}"].to_numpy()
                        phase_rad = np.deg2rad(csv_df[f"phi_phase_deg_{ch}"].to_numpy())
                        ms[i] = amp * np.exp(1j * phase_rad)
                    st.session_state["modal_results"] = {
                        "fn": fn, "xi": xi, "mode_shapes": ms,
                        "output_channels": channels,
                    }
                    st.success(f"Loaded SIMO results: {n_modes} modes, {n_out} channels.")
            except Exception as exc:
                st.error(f"Failed to parse CSV: {exc}")

        has_simo = st.session_state.get("modal_results") is not None
        has_mimo = st.session_state.get("mimo_modal_results") is not None

        if has_simo or has_mimo:
            source_options = (["SIMO (Page 4)"] if has_simo else []) + (["MIMO (Page 5)"] if has_mimo else [])
            if len(source_options) > 1:
                source = st.radio("Results source", source_options, horizontal=True, key="wf_source")
            else:
                source = source_options[0]
                st.caption(f"Using: {source}")
            exp_results = (
                st.session_state["mimo_modal_results"] if "MIMO" in source
                else st.session_state["modal_results"]
            )
            exp_fn = exp_results["fn"]
            exp_xi = exp_results["xi"]
            exp_mode_shapes = exp_results["mode_shapes"]
            exp_channels = exp_results["output_channels"]
            n_exp_modes = int(exp_fn.shape[0])
            st.metric("Experimental modes", n_exp_modes)
        else:
            st.info("Run SIMO/MIMO analysis (Pages 4–5) or import a CSV above.")

    # Channel mapping — shown when both geometry and results are available
    if geom_test is not None and exp_channels is not None:
        with st.expander("Channel Mapping", expanded=False):
            st.caption(
                "Map each experimental output channel to the GRID at the sensor location "
                "and the axis the sensor measures."
            )
            grid_ids = sorted(geom_test.grids.keys())
            dof_options = {"X (1)": 0, "Y (2)": 1, "Z (3)": 2}

            hdr = st.columns([3, 2, 2])
            hdr[0].markdown("**Channel**")
            hdr[1].markdown("**GRID ID**")
            hdr[2].markdown("**Axis**")

            for ch in exp_channels:
                row = st.columns([3, 2, 2])
                row[0].write(ch)
                gid_sel = row[1].selectbox("", grid_ids, key=f"wf_gid_{ch}", label_visibility="collapsed")
                dof_sel = row[2].selectbox(
                    "", list(dof_options.keys()), index=2, key=f"wf_dof_{ch}", label_visibility="collapsed"
                )
                mapping.append((gid_sel, dof_options[dof_sel]))

# ---------------------------------------------------------------------------
# 2. Analytical Results — optional, collapsed by default
# ---------------------------------------------------------------------------

geom_fe: GeomModel | None = None
f06_data: dict | None = None

with st.expander("Analytical Results (optional)", expanded=False):
    col_fe_bdf, col_f06 = st.columns(2)

    with col_fe_bdf:
        st.markdown("**Model (FE) Geometry**")
        fe_bdf = st.file_uploader(
            "FE BDF / DAT",
            type=["bdf", "dat"],
            key="wf_fe_bdf",
            help="GRID + PLOTEL cards for the FE model wireframe.",
        )
        if fe_bdf is not None:
            try:
                geom_fe = parse_wireframe_bdf(fe_bdf)
                c1, c2 = st.columns(2)
                c1.metric("GRIDs", len(geom_fe.grids))
                c2.metric("PLOTELs", len(geom_fe.plotels))
                with st.expander("Preview", expanded=False):
                    st.plotly_chart(build_static_figure(geom_fe), use_container_width=True)
            except Exception as exc:
                st.error(f"Failed to parse FE BDF: {exc}")

    with col_f06:
        st.markdown("**F06 Modal Results**")
        f06_upload = st.file_uploader(
            "F06 modal results",
            type=["f06", "out", "txt"],
            key="wf_f06",
            help="NASTRAN SOL 103 output file with REAL EIGENVALUES and EIGENVECTOR sections.",
        )
        if f06_upload is not None:
            try:
                f06_data = parse_f06(f06_upload)
                n_fe_modes = len(f06_data["frequencies_hz"])
                st.metric("FE modes", n_fe_modes)
                if n_fe_modes > 0:
                    st.caption(
                        f"Modes: {', '.join(f'{f:.4g} Hz' for f in f06_data['frequencies_hz'][:6])}"
                        + (" …" if n_fe_modes > 6 else "")
                    )
            except Exception as exc:
                st.error(f"Failed to parse F06: {exc}")

# ---------------------------------------------------------------------------
# 3. Guard — need at least test data to proceed
# ---------------------------------------------------------------------------

has_test_data = geom_test is not None and exp_fn is not None
has_fe_data = geom_fe is not None and f06_data is not None and len(f06_data["frequencies_hz"]) > 0

if not has_test_data and not has_fe_data:
    st.info(
        "Upload a Test BDF and load experimental modal results in **Experimental Setup** above.  \n"
        "Optionally, expand **Analytical Results** to add an FE model comparison."
    )
    st.stop()

# ---------------------------------------------------------------------------
# 4. Global display controls
# ---------------------------------------------------------------------------

st.subheader("Display Controls")
ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([2, 2, 2, 2])

view = ctrl1.radio("View", ["3D", "X-Y", "X-Z", "Y-Z"], horizontal=False)
display_mode = ctrl2.radio("Display", ["Animate", "Static"], horizontal=False)
phase_deg = None
if display_mode == "Static":
    phase_deg = ctrl2.slider("Phase (°)", 0, 360, 90, step=5)

scale = ctrl3.slider("Amplitude scale", 0.01, 100.0, 1.0, step=0.01, format="%.2f")
n_frames = 20
if display_mode == "Animate":
    n_frames = int(ctrl4.number_input("Frames", min_value=4, max_value=60, value=20, step=1))

exp_phase_offset_deg = 0
ana_phase_offset_deg = 0
if has_test_data:
    exp_phase_offset_deg = ctrl4.slider(
        "Exp phase offset (°)", 0, 360, 0, step=5, key="wf_exp_phase_offset",
        help="Rotate experimental mode shape before display. Re-click 'Show Test' to apply.",
    )
if has_fe_data:
    ana_phase_offset_deg = ctrl4.slider(
        "FE phase offset (°)", 0, 360, 0, step=5, key="wf_ana_phase_offset",
        help="Rotate analytical mode shape before display. Re-click 'Show Model' to apply.",
    )

# ---------------------------------------------------------------------------
# 5. Display — single column (test) or two columns when FE data is present
# ---------------------------------------------------------------------------

if has_fe_data:
    col_model, col_test = st.columns(2)
else:
    col_model = None
    col_test = st.container()

# --- Model (FE) column ---
if has_fe_data:
    with col_model:
        st.markdown("### Model (FE)")
        fe_freqs = f06_data["frequencies_hz"]
        fe_labels = [f"Mode {i + 1}  —  {fe_freqs[i]:.4g} Hz" for i in range(len(fe_freqs))]
        fe_mode_idx = st.selectbox(
            "FE mode", range(len(fe_freqs)), format_func=lambda i: fe_labels[i], key="wf_fe_mode"
        )

        if st.button("Show Model", type="primary", key="wf_show_model"):
            raw = f06_data["mode_shapes"][fe_mode_idx]
            peak = max((np.linalg.norm(v) for v in raw.values()), default=1.0)
            if peak == 0.0:
                peak = 1.0
            cos_rot = np.cos(np.radians(ana_phase_offset_deg))
            gid_disps_fe = {gid: (v / peak) * cos_rot for gid, v in raw.items()}
            for gid in geom_fe.grids:
                gid_disps_fe.setdefault(gid, np.zeros(3))
            st.session_state["wf_gid_disps_fe"] = gid_disps_fe
            st.session_state["wf_fe_freq"] = float(fe_freqs[fe_mode_idx])

        if st.session_state.get("wf_gid_disps_fe") is not None:
            _gd = st.session_state["wf_gid_disps_fe"]
            _freq = st.session_state["wf_fe_freq"]
            if display_mode == "Animate":
                fig = build_mode_figure(geom_fe, _gd, freq_hz=_freq, scale=float(scale), n_frames=n_frames, view=view)
            else:
                fig = build_static_mode_figure(geom_fe, _gd, freq_hz=_freq, scale=float(scale), phase_deg=float(phase_deg), view=view)
            st.plotly_chart(fig, use_container_width=True)

# --- Test (Experimental) column ---
with col_test:
    if has_fe_data:
        st.markdown("### Test (Experiment)")

    if not has_test_data:
        st.info("Upload a Test BDF and load experimental modal results in Experimental Setup above.")
    else:
        exp_labels = [
            f"Mode {i + 1}  —  {exp_fn[i]:.4g} Hz  (ξ = {exp_xi[i] * 100:.2f}%)"
            for i in range(n_exp_modes)
        ]
        exp_mode_idx = st.selectbox(
            "Experimental mode", range(n_exp_modes), format_func=lambda i: exp_labels[i], key="wf_exp_mode"
        )

        if st.button("Show Test", type="primary", key="wf_show_test"):
            phase_rot = np.exp(1j * np.radians(exp_phase_offset_deg))
            if exp_mode_shapes.ndim == 3:
                raw_shape = np.real(exp_mode_shapes[:, 0, exp_mode_idx] * phase_rot)
            else:
                raw_shape = np.real(exp_mode_shapes[:, exp_mode_idx] * phase_rot)
            peak = np.max(np.abs(raw_shape))
            if peak > 0.0:
                raw_shape = raw_shape / peak

            meas_disps: dict = {}
            for ch_idx, (gid, dof_idx) in enumerate(mapping):
                d = np.zeros(3)
                d[dof_idx] = float(raw_shape[ch_idx])
                meas_disps[gid] = meas_disps.get(gid, np.zeros(3)) + d

            # Seed any grid referenced as an RBE3 independent node but absent from
            # meas_disps (e.g. fixed root) at zero so linear interpolation honours the BC.
            rbe3_ind_grids = {
                gid
                for rbe3 in geom_test.rbe3s.values()
                for _wt, _c, gids in rbe3.wt_gc
                for gid in gids
            }
            for gid in rbe3_ind_grids - meas_disps.keys():
                meas_disps[gid] = np.zeros(3)

            gid_disps_test = expand_rbe3_displacements(geom_test, meas_disps)
            st.session_state["wf_gid_disps_test"] = gid_disps_test
            st.session_state["wf_test_freq"] = float(exp_fn[exp_mode_idx])

        if st.session_state.get("wf_gid_disps_test") is not None:
            _gd = st.session_state["wf_gid_disps_test"]
            _freq = st.session_state["wf_test_freq"]
            _accel_gids = {gid for gid, _dof in mapping}
            if display_mode == "Animate":
                fig = build_mode_figure(geom_test, _gd, freq_hz=_freq, scale=float(scale), n_frames=n_frames, view=view, accel_gids=_accel_gids)
            else:
                fig = build_static_mode_figure(geom_test, _gd, freq_hz=_freq, scale=float(scale), phase_deg=float(phase_deg), view=view, accel_gids=_accel_gids)
            st.plotly_chart(fig, use_container_width=True)
