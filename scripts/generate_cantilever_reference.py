#!/usr/bin/env python
"""Generate the G3 analytical reference dataset for a steel cantilever beam with tip mass.

Beam configuration
------------------
- Steel: E = 210 GPa, ρ = 7850 kg/m³
- Circular tube: OD = 0.1 m, wall thickness = 0.01 m
- Length: L = 10 m
- Tip mass: M = 100 kg at x = L
- Clamped at x = 0

Outputs (written to data/input/cantilever_beam/)
-------------------------------------------------
- cantilever_response.csv    300 s at 200 Hz; columns: time, force, acc_0m, acc_5m, acc_7m, acc_10m
- cantilever_wireframe.bdf   NASTRAN BDF with 11 GRID + 10 PLOTEL cards (wireframe for Page 8)
- cantilever_modes.f06       NASTRAN SOL 103 output with 4 real eigenmodes (for Page 7 MAC)

Run from the repo root:
    source .venv/bin/activate
    python scripts/generate_cantilever_reference.py
"""

from __future__ import annotations

import math
import pathlib
import sys

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq

# ---------------------------------------------------------------------------
# Beam parameters
# ---------------------------------------------------------------------------

E = 2.1e11      # Young's modulus, Pa (steel)
RHO = 7850.0    # Density, kg/m³
L = 10.0        # Beam length, m
OD = 0.1        # Outer diameter, m
T_WALL = 0.01   # Wall thickness, m
M_TIP = 100.0   # Concentrated tip mass, kg
XI = 0.02       # Modal damping ratio (2 % for all modes)

ID = OD - 2.0 * T_WALL                          # Inner diameter
A = math.pi / 4.0 * (OD**2 - ID**2)            # Cross-sectional area, m²
I_MOI = math.pi / 64.0 * (OD**4 - ID**4)       # Second moment of area, m⁴
EI = E * I_MOI                                  # Bending stiffness, N·m²
RHO_A = RHO * A                                 # Mass per unit length, kg/m
EPSILON = M_TIP / (RHO_A * L)                  # Dimensionless tip-mass ratio

# ---------------------------------------------------------------------------
# Discretisation parameters
# ---------------------------------------------------------------------------

N_MODES = 4
FS = 200.0          # Sample rate, Hz
N_SAMPLES = 60_000  # 300 s duration
SEED = 42           # Reproducibility seed
SNR_DB = 40.0       # Sensor noise level

# Sensor positions and beam node positions
X_SENSORS = [0.0, 5.0, 7.0, 10.0]
SENSOR_NAMES = ["force", "acc_0m", "acc_5m", "acc_7m", "acc_10m"]
X_NODES = [float(i) for i in range(11)]         # x = 0, 1, ..., 10 m (GIDs 1–11)

# Search intervals for the first four roots of the characteristic equation.
# Roots shift down from the standard cantilever values (1.875, 4.694, 7.855, 10.996)
# due to the added tip mass.
BETA_L_BRACKETS = [(0.5, 2.5), (3.5, 5.5), (6.5, 8.5), (9.5, 12.0)]

# Output directory
_ROOT = pathlib.Path(__file__).parent.parent
OUT_DIR = _ROOT / "data" / "input" / "cantilever_beam"

# ---------------------------------------------------------------------------
# Analytical eigensolution
# ---------------------------------------------------------------------------


def _char_eq(beta_L: float) -> float:
    """Characteristic equation for a cantilever beam with concentrated tip mass.

    Derived from clamped BC at x=0 and inertial BC at x=L:
        EI w'''(L) = -M ω² w(L)   (tip mass inertial reaction)
        EI w''(L) = 0              (free bending moment)

    Equation (with ε = M / (ρA L)):
        1 + cos(βL)·cosh(βL) + ε·βL·[sinh(βL)·cos(βL) - cosh(βL)·sin(βL)] = 0
    """
    ch = math.cosh(beta_L)
    c = math.cos(beta_L)
    sh = math.sinh(beta_L)
    s = math.sin(beta_L)
    return (1.0 + ch * c) + EPSILON * beta_L * (sh * c - ch * s)


def _sigma(beta_L: float) -> float:
    """Compute the σ factor from the clamped BC at x=0."""
    ch = math.cosh(beta_L)
    c = math.cos(beta_L)
    sh = math.sinh(beta_L)
    s = math.sin(beta_L)
    return (ch + c) / (sh + s)


def _phi_raw(x: float, beta: float, sigma: float) -> float:
    """Unnormalized mode shape: φ(x) = cosh(βx) - cos(βx) - σ·(sinh(βx) - sin(βx))."""
    bx = beta * x
    return math.cosh(bx) - math.cos(bx) - sigma * (math.sinh(bx) - math.sin(bx))


def solve_modes() -> list[dict]:
    """Solve for the first N_MODES modes. Returns a list of mode dicts."""
    alpha = math.sqrt(EI / RHO_A)  # Characteristic velocity, m²/s

    modes: list[dict] = []
    for lo, hi in BETA_L_BRACKETS:
        beta_L = brentq(_char_eq, lo, hi, xtol=1e-12)
        beta = beta_L / L
        omega_n = beta**2 * alpha   # Natural angular frequency, rad/s
        f_n = omega_n / (2.0 * math.pi)
        sig = _sigma(beta_L)

        # Mass normalization: ∫₀ᴸ ρA φ²(x) dx + M φ²(L) = 1
        integral, _ = quad(lambda x: _phi_raw(x, beta, sig) ** 2, 0.0, L)
        phi_tip = _phi_raw(L, beta, sig)
        norm = math.sqrt(RHO_A * integral + M_TIP * phi_tip**2)

        modes.append(
            {
                "beta_L": beta_L,
                "beta": beta,
                "omega_n": omega_n,
                "f_n": f_n,
                "sigma": sig,
                "norm": norm,
            }
        )

    return modes


def phi(x: float, mode: dict) -> float:
    """Mass-normalized mode shape at position x."""
    return _phi_raw(x, mode["beta"], mode["sigma"]) / mode["norm"]


# ---------------------------------------------------------------------------
# FRF computation
# ---------------------------------------------------------------------------


def compute_frf(freqs_hz: np.ndarray, modes: list[dict], x_out: float) -> np.ndarray:
    """Compute the acceleration FRF H(f) for a single output location.

    Model: unit harmonic force at x = L (tip), acceleration output at x = x_out.

        H_acc(ω) = Σₙ −ω² · φₙ(x_out) · φₙ(L) / (ωₙ² − ω² + 2j ξ ωₙ ω)

    Parameters
    ----------
    freqs_hz : array (n_freqs,)
    modes    : list of mode dicts from solve_modes()
    x_out    : sensor position, m

    Returns
    -------
    H : complex array (n_freqs,)
    """
    omega = 2.0 * math.pi * freqs_hz
    H = np.zeros(len(freqs_hz), dtype=complex)
    for mode in modes:
        phi_out = phi(x_out, mode)
        phi_in = phi(L, mode)
        omega_n = mode["omega_n"]
        denom = omega_n**2 - omega**2 + 2j * XI * omega_n * omega
        H += -omega**2 * phi_out * phi_in / denom
    return H


# ---------------------------------------------------------------------------
# Time-history generation
# ---------------------------------------------------------------------------


def generate_time_history(modes: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate force and acceleration time histories via modal superposition.

    Force: band-limited white noise (0–80 Hz), normalised to 1 N RMS.
    Response: frequency-domain convolution H(ω) · F(ω), then IFFT.
    Noise: Gaussian measurement noise added at SNR_DB.

    Returns
    -------
    t          : (N_SAMPLES,) time vector, s
    force      : (N_SAMPLES,) force, N
    responses  : (N_SAMPLES, 4) accelerations at X_SENSORS, m/s²
    """
    rng = np.random.default_rng(SEED)
    dt = 1.0 / FS
    t = np.arange(N_SAMPLES) * dt

    # Force: Gaussian white noise, band-limited to 0–80 Hz
    raw = rng.standard_normal(N_SAMPLES)
    F_fft = np.fft.rfft(raw)
    freqs = np.fft.rfftfreq(N_SAMPLES, d=dt)
    F_fft[freqs > 80.0] = 0.0
    force_raw = np.fft.irfft(F_fft, n=N_SAMPLES)
    # Normalise to 1 N RMS
    force = force_raw / (np.std(force_raw) + 1e-30)
    F_fft_norm = np.fft.rfft(force)

    responses = np.empty((N_SAMPLES, len(X_SENSORS)))
    snr_linear = 10.0 ** (SNR_DB / 20.0)

    for i, x_s in enumerate(X_SENSORS):
        # Compute acceleration FRF at each frequency bin
        omega = 2.0 * math.pi * freqs
        H = np.zeros(len(freqs), dtype=complex)
        for mode in modes:
            phi_s = phi(x_s, mode)
            phi_tip = phi(L, mode)
            omega_n = mode["omega_n"]
            denom = omega_n**2 - omega**2 + 2j * XI * omega_n * omega
            # Avoid divide-by-zero at DC (omega=0 → H_acc=0 anyway)
            with np.errstate(divide="ignore", invalid="ignore"):
                H_mode = np.where(freqs > 0.0, -omega**2 * phi_s * phi_tip / denom, 0.0 + 0j)
            H += H_mode

        # Convolve in frequency domain
        R_fft = H * F_fft_norm
        response = np.fft.irfft(R_fft, n=N_SAMPLES)

        # Add Gaussian measurement noise at the specified SNR
        sig_std = float(np.std(response))
        noise = rng.standard_normal(N_SAMPLES) * (sig_std / snr_linear)
        responses[:, i] = response + noise

    return t, force, responses


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------


def _nastran_float(val: float) -> str:
    """Format a float in NASTRAN 7-significant-figure exponential notation."""
    return f"{val:.6E}"


def write_csv(t: np.ndarray, force: np.ndarray, responses: np.ndarray) -> pathlib.Path:
    """Write cantilever_response.csv."""
    out_path = OUT_DIR / "cantilever_response.csv"
    header = "time," + ",".join(SENSOR_NAMES)
    data = np.column_stack([t, force, responses])
    np.savetxt(out_path, data, delimiter=",", header=header, comments="", fmt="%.6e")
    return out_path


def write_bdf() -> pathlib.Path:
    """Write cantilever_wireframe.bdf — 11 GRIDs (x=0..10 m) + 10 PLOTELs."""
    out_path = OUT_DIR / "cantilever_wireframe.bdf"
    lines: list[str] = [
        "$ Cantilever beam reference model",
        "$ Steel tube: OD=0.1m, wall=0.01m, L=10m, tip mass=100kg",
        "$ Generated by scripts/generate_cantilever_reference.py",
        "$",
        "$ GID 1  = x=0m  (clamped wall — zero motion in all modes)",
        "$ GID 6  = x=5m  (sensor acc_5m)",
        "$ GID 8  = x=7m  (sensor acc_7m)",
        "$ GID 11 = x=10m (sensor acc_10m = tip)",
        "$",
        "$ GRID, GID, CP, X1,   X2,  X3",
    ]
    for i, x in enumerate(X_NODES):
        gid = i + 1
        lines.append(f"GRID, {gid:3d}, , {x:5.1f}, 0.0, 0.0")
    lines.append("$")
    lines.append("$ PLOTEL, EID, G1, G2")
    for i in range(len(X_NODES) - 1):
        lines.append(f"PLOTEL, {i + 1:2d}, {i + 1:2d}, {i + 2:2d}")
    lines.append("$")
    out_path.write_text("\n".join(lines) + "\n")
    return out_path


def write_f06(modes: list[dict]) -> pathlib.Path:
    """Write cantilever_modes.f06 — SOL 103 output with 4 real eigenmodes."""
    out_path = OUT_DIR / "cantilever_modes.f06"
    lines: list[str] = [
        "1                                                                                          cantilever",
        "                                          SOL 103 NORMAL MODES",
        "                                          cantilever SOL 103",
        "                                          DATE: 2026-05-27 00:00:00",
        "",
        "                           SUBCASE 1",
        "",
        "                                          R E A L   E I G E N V A L U E S",
        "",
        "   MODE NO.      EIGENVALUE            RADIANS             CYCLES             GENERALIZED MASS",
    ]
    for k, mode in enumerate(modes):
        eigenvalue = mode["omega_n"] ** 2
        lines.append(
            f"         {k + 1}   "
            f"{_nastran_float(eigenvalue)}   "
            f"{_nastran_float(mode['omega_n'])}   "
            f"{_nastran_float(mode['f_n'])}   "
            f"{_nastran_float(1.0)}"
        )
    lines.append("")

    for k, mode in enumerate(modes):
        lines.append(
            f"                          E I G E N V E C T O R   NO. {k + 1}"
            f"     FREQ = {_nastran_float(mode['f_n'])} Hz"
        )
        lines.append("")
        lines.append(
            "      POINT ID.   TYPE          T1             T2             T3"
            "             R1             R2             R3"
        )
        for i, x in enumerate(X_NODES):
            gid = i + 1
            t3 = phi(x, mode)
            zero = _nastran_float(0.0)
            t3_s = _nastran_float(t3)
            lines.append(
                f"             {gid:2d}     G"
                f"   {zero} {zero} {t3_s}"
                f" {zero} {zero} {zero}"
            )
        lines.append("")

    lines.append("                                       * * * END OF JOB * * *")
    lines.append("")
    out_path.write_text("\n".join(lines) + "\n")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Solving cantilever beam eigenproblem...")
    print(f"  E = {E:.3e} Pa,  ρ = {RHO} kg/m³,  L = {L} m")
    print(f"  OD = {OD} m,  t_wall = {T_WALL} m,  A = {A:.4e} m²,  I = {I_MOI:.4e} m⁴")
    print(f"  EI = {EI:.4e} N·m²,  ρA = {RHO_A:.4f} kg/m")
    print(f"  Tip mass M = {M_TIP} kg,  mass ratio ε = {EPSILON:.4f}")
    print()

    modes = solve_modes()

    print(f"{'Mode':>4}  {'βL':>8}  {'fn (Hz)':>10}  {'ωn (rad/s)':>12}  {'φ(0m)':>10}  {'φ(10m)':>10}")
    print("-" * 65)
    for k, mode in enumerate(modes):
        print(
            f"{k + 1:>4}  {mode['beta_L']:8.4f}  {mode['f_n']:10.4f}  "
            f"{mode['omega_n']:12.4f}  "
            f"{phi(0.0, mode):10.4e}  {phi(10.0, mode):10.4e}"
        )
    print()

    print("Generating time-history data (this may take 10–30 s)...")
    t, force, responses = generate_time_history(modes)
    print(f"  Generated {N_SAMPLES} samples at fs={FS} Hz ({N_SAMPLES / FS:.0f} s)")

    csv_path = write_csv(t, force, responses)
    print(f"  Wrote: {csv_path.relative_to(_ROOT)}")

    bdf_path = write_bdf()
    print(f"  Wrote: {bdf_path.relative_to(_ROOT)}")

    f06_path = write_f06(modes)
    print(f"  Wrote: {f06_path.relative_to(_ROOT)}")

    print()
    print("Analytical natural frequencies (for regression test constants):")
    print("EXPECTED_FREQS_HZ = [")
    for mode in modes:
        print(f"    {mode['f_n']:.4f},  # Mode {modes.index(mode) + 1}")
    print("]")


if __name__ == "__main__":
    main()
