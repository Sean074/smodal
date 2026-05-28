from __future__ import annotations

import numpy as np
import pytest

from core.ema_pipeline import extract_modes, nmse_quality_label, prepare_band_arrays

# ---------------------------------------------------------------------------
# extract_modes
# ---------------------------------------------------------------------------

def test_extract_modes_returns_keys(sdof_frf):
    freqs, H, fn, xi = sdof_frf
    result = extract_modes(H, freqs, freqs, np.array([fn]), np.array([xi]))
    expected = {"poles", "fn_hz", "xi", "residues", "H_synthesis_band", "H_synthesis_full", "nmse"}
    assert expected == set(result.keys())


def test_extract_modes_shapes_simo(sdof_frf):
    freqs, H, fn, xi = sdof_frf
    n_freqs_full = len(freqs) + 50
    freqs_full = np.linspace(freqs[0], freqs[-1] * 1.5, n_freqs_full)
    result = extract_modes(H, freqs, freqs_full, np.array([fn]), np.array([xi]))
    assert result["residues"].shape == (1, 1)
    assert result["H_synthesis_band"].shape == H.shape
    assert result["H_synthesis_full"].shape == (n_freqs_full, 1)
    assert result["nmse"].shape == (1,)
    assert result["poles"].shape == (1,)
    assert result["fn_hz"].shape == (1,)
    assert result["xi"].shape == (1,)


def test_extract_modes_shapes_mimo(sdof_frf):
    """MIMO stacks two runs: H shape is (n_band, n_out*2)."""
    freqs, H_single, fn, xi = sdof_frf
    n_out = 3
    H_mimo = np.tile(H_single, (1, n_out * 2))  # (n_freqs, 6)
    result = extract_modes(H_mimo, freqs, freqs, np.array([fn]), np.array([xi]))
    assert result["residues"].shape == (n_out * 2, 1)
    assert result["H_synthesis_band"].shape == H_mimo.shape
    assert result["H_synthesis_full"].shape == H_mimo.shape


def test_extract_modes_nmse_acceptable(sdof_frf):
    """With exact fn/xi the modal fit NMSE should be well below -12 dB."""
    freqs, H, fn, xi = sdof_frf
    result = extract_modes(H, freqs, freqs, np.array([fn]), np.array([xi]))
    assert result["nmse"][0] < -12.0, f"NMSE {result['nmse'][0]:.1f} dB is too high"


def test_extract_modes_freqs_full_same_as_band(sdof_frf):
    """When freqs_full is freqs_band, H_synthesis_full should be the same object."""
    freqs, H, fn, xi = sdof_frf
    result = extract_modes(H, freqs, freqs, np.array([fn]), np.array([xi]))
    assert result["H_synthesis_full"] is result["H_synthesis_band"]


def test_extract_modes_fn_xi_recovery(sdof_frf):
    """fn_hz and xi returned from extract_modes should match the input estimates."""
    freqs, H, fn, xi = sdof_frf
    result = extract_modes(H, freqs, freqs, np.array([fn]), np.array([xi]))
    assert abs(result["fn_hz"][0] - fn) / fn < 0.001
    assert abs(result["xi"][0] - xi) / xi < 0.001


# ---------------------------------------------------------------------------
# nmse_quality_label
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("db,expected", [
    (-35.0, "Excellent"),
    (-30.1, "Excellent"),
    (-30.0, "Good"),       # boundary: < -30 is Excellent; -30 is not
    (-25.0, "Good"),
    (-20.0, "Acceptable"), # boundary: < -20 is Good; -20 is not
    (-15.0, "Acceptable"),
    (-10.0, "Poor"),       # boundary: < -10 is Acceptable; -10 is not
    (-5.0,  "Poor"),
    (0.0,   "Poor"),
])
def test_nmse_quality_label_thresholds(db, expected):
    assert nmse_quality_label(db) == expected


# ---------------------------------------------------------------------------
# prepare_band_arrays
# ---------------------------------------------------------------------------

def test_prepare_band_arrays_basic():
    freqs = np.linspace(0.0, 100.0, 1001)
    H = np.ones((1001, 2), dtype=complex)
    H_band, f_band = prepare_band_arrays(H, freqs, 20.0, 40.0)
    assert f_band[0] >= 20.0
    assert f_band[-1] <= 40.0
    assert H_band.shape[0] == len(f_band)
    assert H_band.shape[1] == 2


def test_prepare_band_arrays_empty_raises():
    freqs = np.linspace(0.0, 10.0, 100)
    H = np.ones((100, 1), dtype=complex)
    with pytest.raises(ValueError, match="No frequency points"):
        prepare_band_arrays(H, freqs, 50.0, 60.0)
