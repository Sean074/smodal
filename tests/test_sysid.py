from __future__ import annotations

import numpy as np
import pytest

from core.sysid import (
    build_stability_table,
    compute_cmif,
    compute_mac,
    deduplicate_stable_poles,
    era_poles,
    extract_residues,
    fdd_damping,
    fdd_svd,
    modal_fit_nmse,
    plscf_poles,
    poles_from_estimates,
    synthesize_frf,
)


# ---------------------------------------------------------------------------
# compute_cmif
# ---------------------------------------------------------------------------

def test_compute_cmif_shape(sdof_frf):
    freqs, H, fn, xi = sdof_frf
    cmif = compute_cmif(H)
    assert cmif.shape == (len(freqs),)


def test_compute_cmif_1d_input():
    arr = np.array([1 + 2j, 3 + 4j, 0 + 1j])
    out = compute_cmif(arr)
    np.testing.assert_allclose(out, np.abs(arr))


# ---------------------------------------------------------------------------
# deduplicate_stable_poles
# ---------------------------------------------------------------------------

def test_deduplicate_stable_poles_removes_duplicates():
    row = {
        "order": 4,
        "fn": np.array([10.0, 10.05]),   # 0.5 % apart — within default 1 % tol
        "xi": np.array([0.03, 0.031]),
        "stability": ["stable_all", "stable_all"],
    }
    result = deduplicate_stable_poles([row])
    assert len(result) == 1


def test_deduplicate_stable_poles_keeps_separate():
    row = {
        "order": 4,
        "fn": np.array([10.0, 15.0]),
        "xi": np.array([0.03, 0.03]),
        "stability": ["stable_all", "stable_all"],
    }
    result = deduplicate_stable_poles([row])
    assert len(result) == 2


def test_deduplicate_stable_poles_ignores_non_stable():
    row = {
        "order": 4,
        "fn": np.array([10.0, 12.0]),
        "xi": np.array([0.03, 0.03]),
        "stability": ["stable_f", "new"],   # neither is stable_all
    }
    result = deduplicate_stable_poles([row])
    assert len(result) == 0


# ---------------------------------------------------------------------------
# poles_from_estimates
# ---------------------------------------------------------------------------

def test_poles_from_estimates_basic():
    fn = np.array([10.0])
    xi = np.array([0.03])
    poles = poles_from_estimates(fn, xi)
    assert len(poles) == 1
    fn_recovered = np.abs(poles[0].imag) / (2 * np.pi)
    assert abs(fn_recovered - 10.0) / 10.0 < 0.001


def test_poles_from_estimates_negative_damping():
    fn = np.array([10.0])
    xi = np.array([-0.05])
    poles = poles_from_estimates(fn, xi)
    assert len(poles) == 1
    assert np.all(np.isfinite(poles))
    assert poles[0].imag > 0   # still has positive imaginary part


# ---------------------------------------------------------------------------
# plscf / build_stability_table — SDOF recovery
# ---------------------------------------------------------------------------

def test_plscf_recovers_sdof_frequency(sdof_frf):
    freqs, H, fn_true, xi_true = sdof_frf
    fs = 2.0 * freqs[-1]
    stab = build_stability_table(H, freqs, fs, max_order=12, method="plscf")
    stable_fn = [
        float(stab[o]["fn"][k])
        for o in range(len(stab))
        for k in range(len(stab[o]["fn"]))
        if stab[o]["stability"][k] == "stable_all"
    ]
    assert len(stable_fn) > 0, "No stable_all poles found in SDOF stability table"
    closest_pct = min(abs(f - fn_true) / fn_true for f in stable_fn) * 100
    assert closest_pct < 1.0, f"Closest stable_all pole is {closest_pct:.2f} % from fn={fn_true} Hz"


def test_build_stability_table_empty_frf():
    H = np.zeros((200, 1), dtype=complex)
    freqs = np.linspace(1.0, 50.0, 200)
    fs = 100.0
    result = build_stability_table(H, freqs, fs, max_order=6)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# ERA — SDOF recovery
# ---------------------------------------------------------------------------

def test_era_recovers_sdof_frequency(sdof_frf):
    freqs, H, fn_true, xi_true = sdof_frf
    fs = 2.0 * freqs[-1]
    poles, _ = era_poles(H, freqs, n_order=4, fs=fs)
    assert len(poles) > 0, "ERA returned no physical poles"
    fn_hz = np.abs(poles.imag) / (2 * np.pi)
    closest_pct = min(abs(f - fn_true) / fn_true for f in fn_hz) * 100
    # ERA reconstructs IRF via irfft, which assumes the spectrum starts at DC.
    # With a non-DC-starting FRF the IRF has slight aliasing, so 5 % tolerance.
    assert closest_pct < 5.0, f"ERA pole is {closest_pct:.2f} % from fn={fn_true} Hz"


# ---------------------------------------------------------------------------
# extract_residues / synthesize_frf / modal_fit_nmse — round-trip
# ---------------------------------------------------------------------------

def test_extract_synthesize_roundtrip(sdof_frf):
    freqs, H, fn_true, xi_true = sdof_frf
    poles = poles_from_estimates(np.array([fn_true]), np.array([xi_true]))
    residues = extract_residues(H, freqs, poles)
    H_syn = synthesize_frf(freqs, poles, residues)
    nmse = modal_fit_nmse(H, H_syn)
    # The symmetric basis (1/(jw-s) + 1/(jw-s*)) forces equal rather than
    # conjugate residues, so the lstsq fit is approximate (~-15 dB for SDOF).
    assert nmse[0] < -12.0, f"Round-trip NMSE = {nmse[0]:.1f} dB (expected < −12 dB)"


def test_modal_fit_nmse_perfect_fit(sdof_frf):
    _, H, _, _ = sdof_frf
    nmse = modal_fit_nmse(H, H)
    assert nmse[0] <= -100.0, f"Perfect-fit NMSE = {nmse[0]:.1f} dB (expected ≤ −100 dB)"


# ---------------------------------------------------------------------------
# fdd_svd
# ---------------------------------------------------------------------------

def test_fdd_svd_shape():
    rng = np.random.default_rng(0)
    n_freqs, n_out = 100, 3
    A = rng.standard_normal((n_freqs, n_out, n_out)) + 1j * rng.standard_normal((n_freqs, n_out, n_out))
    Syy = np.array([A[k] @ A[k].conj().T for k in range(n_freqs)])
    sv, svecs = fdd_svd(Syy)
    assert sv.shape == (n_freqs, n_out)
    assert svecs.shape == (n_freqs, n_out, n_out)


def test_fdd_svd_nonnegative_singular_values():
    rng = np.random.default_rng(1)
    n_freqs, n_out = 50, 2
    A = rng.standard_normal((n_freqs, n_out, n_out))
    Syy = np.array([A[k] @ A[k].T for k in range(n_freqs)], dtype=complex)
    sv, _ = fdd_svd(Syy)
    assert np.all(sv >= 0)


# ---------------------------------------------------------------------------
# fdd_damping — known bandwidth
# ---------------------------------------------------------------------------

def test_fdd_damping_known_bandwidth():
    fn, xi_expected = 10.0, 0.03
    freqs = np.linspace(0.1, 50.0, 10000)
    wn = 2 * np.pi * fn
    w = 2 * np.pi * freqs
    sv1 = 1.0 / ((wn**2 - w**2) ** 2 + (2 * xi_expected * wn * w) ** 2)
    peak_idx = int(np.argmax(sv1))
    xi_pct, _, _ = fdd_damping(sv1, freqs, peak_idx)
    assert abs(xi_pct / 100.0 - xi_expected) / xi_expected < 0.20


def test_fdd_damping_peak_at_last_index_returns_sentinel():
    freqs = np.linspace(1.0, 50.0, 200)
    sv1 = np.zeros(200)
    sv1[-1] = 1.0  # peak at last index — no upper crossing possible
    xi_pct, _, _ = fdd_damping(sv1, freqs, 199)
    assert xi_pct == 0.0


def test_build_stability_warns_underdetermined():
    """RuntimeWarning from ill-conditioned residue fit propagates out of build_stability_table."""
    import warnings as _w
    from unittest.mock import patch

    freqs = np.linspace(1.0, 100.0, 20)
    H = np.ones((20, 1), dtype=complex)

    # 15 fake poles → n_freqs=20 < 2*15=30 → extract_residues warns
    fake_poles = np.array([
        -0.02 * 2 * np.pi * fn + 1j * 2 * np.pi * fn
        for fn in np.linspace(5.0, 90.0, 15)
    ])
    with patch("core.sysid.plscf_poles", return_value=fake_poles):
        with _w.catch_warnings(record=True) as caught:
            _w.simplefilter("always")
            build_stability_table(H, freqs, 200.0, max_order=30)
    assert any(issubclass(x.category, RuntimeWarning) for x in caught)


# ---------------------------------------------------------------------------
# compute_mac
# ---------------------------------------------------------------------------

def test_compute_mac_identity():
    phi = np.array([[1.0], [2.0], [3.0]])
    mac = compute_mac(phi, phi)
    np.testing.assert_allclose(mac[0, 0], 1.0, atol=1e-10)


def test_compute_mac_orthogonal():
    phi1 = np.array([[1.0], [0.0], [0.0]])
    phi2 = np.array([[0.0], [1.0], [0.0]])
    mac = compute_mac(phi1, phi2)
    assert mac[0, 0] < 0.02


def test_compute_mac_shape():
    rng = np.random.default_rng(0)
    phi_ref = rng.standard_normal((5, 3))
    phi_comp = rng.standard_normal((5, 4))
    mac = compute_mac(phi_ref, phi_comp)
    assert mac.shape == (3, 4)
    assert np.all((mac >= 0) & (mac <= 1 + 1e-10))


def test_compute_mac_complex_phase_scatter():
    # Mode shapes with DOF-level phase scatter (typical of damped EMA residues)
    rng = np.random.default_rng(42)
    phi = rng.standard_normal((6, 2)) + 1j * rng.standard_normal((6, 2))

    # Self-MAC must be 1.0 regardless of complex phase
    mac_self = compute_mac(phi, phi)
    np.testing.assert_allclose(np.diag(mac_self), 1.0, atol=1e-10)

    # Global phase rotation must not change MAC
    phi_rotated = phi * np.exp(1j * np.pi / 3)
    mac_rotated = compute_mac(phi, phi_rotated)
    np.testing.assert_allclose(np.diag(mac_rotated), 1.0, atol=1e-10)

    # Stripping imaginary part on a phase-scattered shape drops MAC below 1 —
    # this confirms that np.real() was incorrect and removal is the right fix
    mac_real_cast = compute_mac(phi, np.real(phi).astype(complex))
    assert np.any(np.diag(mac_real_cast) < 0.99), (
        "np.real() on complex mode shapes should reduce MAC for phase-scattered shapes"
    )
