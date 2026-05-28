from __future__ import annotations

import numpy as np
import pytest

from core.uff_writer import write_uff58_shapes, write_uff58_shapes_mimo


def _make_residues(n_ch: int, n_modes: int) -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.standard_normal((n_ch, n_modes)) + 1j * rng.standard_normal((n_ch, n_modes))


def test_returns_bytes():
    fn_hz = np.array([10.0, 25.0])
    xi = np.array([0.03, 0.05])
    residues = _make_residues(2, 2)
    result = write_uff58_shapes(fn_hz, xi, residues, ["ch1", "ch2"], "test")
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_dataset_count_matches_channels():
    fn_hz = np.array([10.0, 25.0, 40.0])
    xi = np.zeros(3) + 0.03
    n_ch = 4
    residues = _make_residues(n_ch, 3)
    text = write_uff58_shapes(fn_hz, xi, residues, [f"ch{i}" for i in range(n_ch)], "t").decode()
    assert text.count("    58") == n_ch


def test_known_values_present():
    fn_hz = np.array([15.0])
    xi = np.array([0.02])
    residues = np.array([[2.5 - 1.3j]])
    text = write_uff58_shapes(fn_hz, xi, residues, ["acc"], "mytest").decode()
    assert "1.50000E+01" in text   # natural frequency in data triplet
    assert "2.50000E+00" in text   # real part of residue
    assert "-1.30000E+00" in text  # imaginary part of residue


def test_analysis_name_and_damping_in_id_lines():
    fn_hz = np.array([20.0])
    xi = np.array([0.05])
    residues = np.ones((1, 1), dtype=complex)
    text = write_uff58_shapes(fn_hz, xi, residues, ["x"], "MY_ANALYSIS").decode()
    assert "MY_ANALYSIS" in text
    assert "5.000%" in text  # xi=0.05 → 5.000% in ID line 4


def test_mimo_dataset_count():
    n_out, n_modes = 3, 2
    fn_hz = np.array([10.0, 25.0])
    xi = np.array([0.03, 0.05])
    r3d = np.ones((n_out, 2, n_modes), dtype=complex)
    text = write_uff58_shapes_mimo(fn_hz, xi, r3d, ["ch1", "ch2", "ch3"], "test").decode()
    assert text.count("    58") == 2 * n_out


def test_mimo_run_labels_in_id_lines():
    fn_hz = np.array([10.0])
    xi = np.array([0.03])
    r3d = np.ones((2, 2, 1), dtype=complex)
    text = write_uff58_shapes_mimo(fn_hz, xi, r3d, ["x", "y"], "t").decode()
    assert "A_x" in text
    assert "B_x" in text


def test_single_mode_single_channel():
    """Minimal case: 1 mode, 1 channel — no indexing errors."""
    result = write_uff58_shapes(
        np.array([5.0]),
        np.array([0.01]),
        np.array([[0.5 + 0.1j]]),
        ["sole"],
    )
    assert isinstance(result, bytes)
