"""
Streamlit AppTest smoke tests — one per page.

Each test verifies: the page renders without exception, accepts minimal
input, and writes the expected session-state keys.

Pages 2, 3, 7, 8 rely on state written by upstream pages; that state is
pre-seeded directly into ``at.session_state`` before the first run.
Pages 4, 5, 6 manage their own data upload; DataFrames are pre-seeded
to bypass the file-upload UI and reach the computation buttons directly.
"""
from __future__ import annotations

import pathlib

from streamlit.testing.v1 import AppTest

ROOT = pathlib.Path(__file__).parent.parent

# Pages 4–6 build stability diagrams; give all pages a generous budget.
TIMEOUT = 60  # seconds


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _seed_page1_state(at: AppTest, sample_df) -> None:
    """Write the session-state keys that Page 1 (Time History) normally sets."""
    from core.data_loader import compute_sample_rate

    at.session_state["df"] = sample_df
    at.session_state["input_channel"] = "force"
    at.session_state["output_channels"] = ["acc_1", "acc_2"]
    at.session_state["sample_rate"] = float(compute_sample_rate(sample_df["time"].values))


# ---------------------------------------------------------------------------
# Page 9 — Method (no state; notebook display only)
# ---------------------------------------------------------------------------


def test_page9_method_renders():
    """Page 9 displays the methods notebook; it must load without exception."""
    at = AppTest.from_file(ROOT / "pages/9_Method.py", default_timeout=TIMEOUT)
    at.run()
    assert not at.exception


# ---------------------------------------------------------------------------
# Page 1 — Time History
# ---------------------------------------------------------------------------


def test_page1_time_history_writes_df():
    """Uploading a CSV writes df and sample_rate to session state."""
    at = AppTest.from_file(ROOT / "pages/1_Time_History.py", default_timeout=TIMEOUT)
    csv_bytes = (ROOT / "data/input/sample_3ch.csv").read_bytes()

    at.run()  # initial render — shows upload prompt, no exception expected
    at.file_uploader("th_upload").set_value([("sample_3ch.csv", csv_bytes, "text/csv")])
    at.run()  # processes the upload

    assert not at.exception
    assert "df" in at.session_state
    assert "sample_rate" in at.session_state
    assert at.session_state["sample_rate"] > 0


# ---------------------------------------------------------------------------
# Page 2 — FFT
# ---------------------------------------------------------------------------


def test_page2_fft_writes_fft_results(sample_df):
    """With pre-seeded Page 1 state, clicking Compute writes fft_results."""
    at = AppTest.from_file(ROOT / "pages/2_FFT.py", default_timeout=TIMEOUT)
    _seed_page1_state(at, sample_df)
    at.run()
    assert not at.exception

    # "Compute & Save FFT" has no explicit key; it is the only button on the page.
    at.button[0].click()
    at.run()

    assert not at.exception
    assert "fft_results" in at.session_state


# ---------------------------------------------------------------------------
# Page 3 — Spectral Analysis
# ---------------------------------------------------------------------------


def test_page3_spectral_writes_results(sample_df):
    """Welch path writes spectral_results without requiring pre-existing fft_results."""
    at = AppTest.from_file(ROOT / "pages/3_Spectral_Analysis.py", default_timeout=TIMEOUT)
    _seed_page1_state(at, sample_df)
    at.run()
    assert not at.exception

    at.radio("sa_method").set_value("Welch")
    at.button("sa_compute").click()
    at.run()

    assert not at.exception
    assert "spectral_results" in at.session_state


# ---------------------------------------------------------------------------
# Page 4 — SIMO
# ---------------------------------------------------------------------------


def test_page4_simo_builds_stability_table():
    """Pre-seeding simo_df then clicking Build writes si_stability_table."""
    from core.data_loader import compute_sample_rate, load_csv

    df, err = load_csv(str(ROOT / "data/input/sample_3ch.csv"))
    assert err is None, f"SIMO fixture load failed: {err}"

    at = AppTest.from_file(ROOT / "pages/4_SIMO.py", default_timeout=TIMEOUT)
    at.session_state["simo_df"] = df
    at.session_state["simo_sample_rate"] = float(compute_sample_rate(df["time"].values))
    at.run()
    assert not at.exception

    # Small max order keeps CI runtime bounded (orders 2, 4, 6, 8 only).
    at.slider("si_max_order").set_value(8)
    at.button("si_build").click()
    at.run()

    assert not at.exception
    assert "si_stability_table" in at.session_state
    assert "si_H_mat" in at.session_state
    assert "si_freqs" in at.session_state


# ---------------------------------------------------------------------------
# Page 5 — MIMO
# ---------------------------------------------------------------------------


def test_page5_mimo_builds_stability_table():
    """Pre-seeding both run DataFrames then clicking Build writes mimo_stability_table."""
    from core.data_loader import compute_sample_rate, load_csv

    df, err = load_csv(str(ROOT / "data/input/sample_MIMO_asym.csv"))
    assert err is None, f"MIMO fixture load failed: {err}"

    at = AppTest.from_file(ROOT / "pages/5_MIMO.py", default_timeout=TIMEOUT)
    at.session_state["mimo_run_a_df"] = df
    at.session_state["mimo_run_b_df"] = df  # same file for both runs in smoke test
    at.session_state["mimo_sample_rate"] = float(compute_sample_rate(df["time"].values))
    at.run()
    assert not at.exception

    at.slider("mimo_max_order").set_value(8)
    at.button("mimo_build").click()
    at.run()

    assert not at.exception
    assert "mimo_stability_table" in at.session_state
    assert "mimo_H_mat" in at.session_state
    assert "mimo_freqs" in at.session_state


# ---------------------------------------------------------------------------
# Page 6 — OMA
# ---------------------------------------------------------------------------


def test_page6_oma_builds_power_cmif():
    """Pre-seeding oma_df then clicking Build writes oma_sv and oma_freqs."""
    from core.data_loader import compute_sample_rate, load_csv

    df, err = load_csv(str(ROOT / "data/input/sample_3ch.csv"))
    assert err is None, f"OMA fixture load failed: {err}"

    at = AppTest.from_file(ROOT / "pages/6_OMA.py", default_timeout=TIMEOUT)
    at.session_state["oma_df"] = df
    at.session_state["oma_sample_rate"] = float(compute_sample_rate(df["time"].values))
    at.run()
    assert not at.exception

    at.button("oma_build").click()
    at.run()

    assert not at.exception
    assert "oma_sv" in at.session_state
    assert "oma_freqs" in at.session_state
    assert "oma_peak_estimates" in at.session_state


# ---------------------------------------------------------------------------
# Page 7 — MAC
# ---------------------------------------------------------------------------


def test_page7_mac_renders_and_computes(synthetic_modal_results):
    """Pre-seeding modal_results + mac_f06_data, then Compute MAC writes mac_matrix."""
    at = AppTest.from_file(ROOT / "pages/7_MAC.py", default_timeout=TIMEOUT)
    at.session_state["modal_results"] = synthetic_modal_results

    # Minimal synthetic FE model: two GRIDs, two modes.
    # Selectboxes default to GRID 1, Z axis — compute_mac will run successfully.
    at.session_state["mac_f06_data"] = {
        "frequencies_hz": list(synthetic_modal_results["fn"]),
        "mode_shapes": [
            {1: [0.0, 0.0, 1.0], 2: [0.0, 0.0, 0.8]},
            {1: [0.0, 0.0, 0.5], 2: [0.0, 0.0, -0.3]},
        ],
    }
    at.session_state["_mac_f06_name"] = "synthetic.f06"  # suppresses the file reload guard

    at.run()
    assert not at.exception

    # "Compute MAC" has no explicit key; it is the only button on the page.
    at.button[0].click()
    at.run()

    assert not at.exception
    assert "mac_matrix" in at.session_state


# ---------------------------------------------------------------------------
# Page 8 — Wireframe
# ---------------------------------------------------------------------------


def test_page8_wireframe_renders(synthetic_modal_results):
    """Pre-seeding modal_results + uploading BDF lets the page render past the guard."""
    at = AppTest.from_file(ROOT / "pages/8_Wireframe.py", default_timeout=TIMEOUT)
    at.session_state["modal_results"] = synthetic_modal_results

    at.run()  # initial render — guard fires (no BDF yet), but no exception

    bdf_bytes = (ROOT / "data/input/example_model/experimental_wireframe.bdf").read_bytes()
    at.file_uploader("wf_test_bdf").set_value(("experimental_wireframe.bdf", bdf_bytes, "text/plain"))
    at.run()  # BDF parsed; has_test_data=True → guard passes; page renders fully

    assert not at.exception
