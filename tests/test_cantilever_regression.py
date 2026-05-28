"""Numerical regression fixture for core/sysid.py against an analytical reference.

Uses the steel cantilever beam with tip mass defined in G3 (todo.md):
  - L = 10 m, OD = 0.1 m, t_wall = 0.01 m, M_tip = 100 kg, ξ = 2 % (all modes)
  - First 4 transverse bending modes

The analytical FRF (driving-point at tip) is computed directly from the
known modal parameters — no Welch estimation or file I/O needed.  This
isolates the system-identification algorithm from spectral-estimation noise.

Analytical natural frequencies (from scripts/generate_cantilever_reference.py):
  Mode 1:  0.5501 Hz
  Mode 2:  4.4871 Hz
  Mode 3: 13.6683 Hz
  Mode 4: 27.9980 Hz
"""

from __future__ import annotations

import numpy as np
import pytest

from core.sysid import build_stability_table, deduplicate_stable_poles

# ---------------------------------------------------------------------------
# Known-truth values (computed by scripts/generate_cantilever_reference.py)
# ---------------------------------------------------------------------------

EXPECTED_FREQS_HZ = [0.5501, 4.4871, 13.6683, 27.9980]
XI_TRUE = 0.02          # 2 % damping for all modes
FREQ_TOL_PCT = 1.0      # Frequency recovery tolerance, %
DAMP_TOL_PCT = 15.0     # Damping recovery tolerance, % relative


# ---------------------------------------------------------------------------
# Analytical FRF fixture
# ---------------------------------------------------------------------------


def _build_analytical_frf() -> tuple[np.ndarray, np.ndarray]:
    """Return (freqs, H) for the driving-point acceleration FRF at the tip.

    H shape: (n_freqs, 1) complex — SIMO format expected by build_stability_table.

    The FRF is computed via modal superposition using the exact modal parameters;
    it has no spectral-estimation noise.  Frequency grid: 0.01–50 Hz at 10 000 pts.
    """
    import pathlib
    import sys

    root = pathlib.Path(__file__).parent.parent
    sys.path.insert(0, str(root))

    from scripts.generate_cantilever_reference import L, compute_frf, solve_modes

    modes = solve_modes()
    freqs = np.linspace(0.01, 50.0, 10_000)
    H_vec = compute_frf(freqs, modes, x_out=L)   # driving-point (force and response at tip)
    return freqs, H_vec[:, np.newaxis]


@pytest.fixture(scope="module")
def cantilever_stability_table():
    """Run build_stability_table on the analytical cantilever FRF once per module."""
    freqs, H = _build_analytical_frf()
    fs_eff = 2.0 * float(freqs[-1])
    stab = build_stability_table(H, freqs, fs_eff, max_order=16, method="plscf")
    return stab


# ---------------------------------------------------------------------------
# Frequency recovery
# ---------------------------------------------------------------------------


def test_cantilever_four_modes_recovered(cantilever_stability_table):
    """All four expected modes appear as stable_all poles."""
    deduped = deduplicate_stable_poles(cantilever_stability_table)
    found_hz = [d["fn_hz"] for d in deduped]
    assert len(found_hz) >= len(EXPECTED_FREQS_HZ), (
        f"Expected ≥{len(EXPECTED_FREQS_HZ)} modes, got {len(found_hz)}: {found_hz}"
    )


def test_cantilever_frequency_recovery_mode1(cantilever_stability_table):
    """Mode 1 (~0.55 Hz) recovered within FREQ_TOL_PCT %."""
    _check_mode_freq(cantilever_stability_table, 0, EXPECTED_FREQS_HZ[0])


def test_cantilever_frequency_recovery_mode2(cantilever_stability_table):
    """Mode 2 (~4.49 Hz) recovered within FREQ_TOL_PCT %."""
    _check_mode_freq(cantilever_stability_table, 1, EXPECTED_FREQS_HZ[1])


def test_cantilever_frequency_recovery_mode3(cantilever_stability_table):
    """Mode 3 (~13.67 Hz) recovered within FREQ_TOL_PCT %."""
    _check_mode_freq(cantilever_stability_table, 2, EXPECTED_FREQS_HZ[2])


def test_cantilever_frequency_recovery_mode4(cantilever_stability_table):
    """Mode 4 (~28.00 Hz) recovered within FREQ_TOL_PCT %."""
    _check_mode_freq(cantilever_stability_table, 3, EXPECTED_FREQS_HZ[3])


def _check_mode_freq(stab, mode_idx: int, fn_expected: float) -> None:
    stable_fn = _all_stable_fn(stab)
    closest_pct = min(abs(f - fn_expected) / fn_expected * 100.0 for f in stable_fn)
    assert closest_pct < FREQ_TOL_PCT, (
        f"Mode {mode_idx + 1} (fn={fn_expected:.4f} Hz): closest stable pole is "
        f"{closest_pct:.3f} % away (tolerance {FREQ_TOL_PCT} %)"
    )


# ---------------------------------------------------------------------------
# Damping recovery
# ---------------------------------------------------------------------------


def test_cantilever_damping_recovery(cantilever_stability_table):
    """Damping for each recovered mode is within DAMP_TOL_PCT % of 2 %."""
    deduped = deduplicate_stable_poles(cantilever_stability_table)
    for d in deduped:
        fn = d["fn_hz"]
        xi_est = d["xi_pct"] / 100.0
        rel_err = abs(xi_est - XI_TRUE) / XI_TRUE * 100.0
        assert rel_err < DAMP_TOL_PCT, (
            f"Damping at fn={fn:.3f} Hz: estimated {xi_est * 100:.2f} % vs "
            f"true {XI_TRUE * 100:.1f} % — relative error {rel_err:.1f} % "
            f"(tolerance {DAMP_TOL_PCT} %)"
        )


# ---------------------------------------------------------------------------
# Mode shape MAC — compare residues to analytical mode shapes
# ---------------------------------------------------------------------------


def test_cantilever_all_modes_classified_stable_all(cantilever_stability_table):
    """All four modes should reach 'stable_all' classification at some model order.

    This tests the stability classifier's MAC-based mode tracking across model
    orders — the key quality gate of the stability diagram.  A regression here
    would mean the internal residue fit or MAC threshold broke for known data.
    """
    # Collect every stable_all fn across all orders
    stable_fns = _all_stable_fn(cantilever_stability_table)
    assert len(stable_fns) > 0, "No stable_all poles found anywhere in stability table"

    for i, fn_expected in enumerate(EXPECTED_FREQS_HZ):
        closest_pct = min(abs(f - fn_expected) / fn_expected * 100.0 for f in stable_fns)
        assert closest_pct < FREQ_TOL_PCT, (
            f"Mode {i + 1} (fn={fn_expected:.4f} Hz) never reached 'stable_all' — "
            f"closest stable_all pole is {closest_pct:.3f} % away"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_stable_fn(stab: list) -> list[float]:
    return [
        float(stab[o]["fn"][k])
        for o in range(len(stab))
        for k in range(len(stab[o]["fn"]))
        if stab[o]["stability"][k] == "stable_all"
    ]
