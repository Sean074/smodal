import warnings

import numpy as np
import scipy.linalg
import scipy.signal


def compute_cmif(H: np.ndarray) -> np.ndarray:
    """H: (n_freqs, n_outputs) complex → (n_freqs,) first singular value."""
    if H.ndim == 1:
        return np.abs(H)
    return np.linalg.norm(H, axis=1)


def deduplicate_stable_poles(stab_results: list[dict], tol: float = 0.01) -> list[dict]:
    """Extract and deduplicate fully-stable poles from a stability table.

    Returns list of dicts with keys fn_hz, xi_pct, source — sorted by frequency.
    """
    green_poles = []
    for row in stab_results:
        for k, s in enumerate(row["stability"]):
            if s == "stable_all":
                green_poles.append({
                    "fn_hz": float(row["fn"][k]),
                    "xi_pct": float(row["xi"][k]) * 100.0,
                    "source": f"order {row['order']}",
                })
    deduped: list[dict] = []
    for g in sorted(green_poles, key=lambda x: x["fn_hz"]):
        if not deduped or abs(g["fn_hz"] - deduped[-1]["fn_hz"]) / (g["fn_hz"] + 1e-9) > tol:
            deduped.append(g)
    return deduped


def cmif_peak_estimates(cmif: np.ndarray, freqs: np.ndarray, n_modes: int) -> list[dict]:
    """Return top n_modes CMIF peaks sorted by prominence, as initial mode estimates."""
    peaks, props = scipy.signal.find_peaks(cmif, prominence=0)
    if len(peaks) == 0:
        # fallback: evenly spaced
        idx = np.linspace(0, len(freqs) - 1, n_modes, dtype=int)
        return [{"fn_hz": float(freqs[i]), "xi_pct": 2.0, "source": "uniform"} for i in idx]
    order = np.argsort(props["prominences"])[::-1]
    peaks = peaks[order][:n_modes]
    result = [{"fn_hz": float(freqs[p]), "xi_pct": 2.0, "source": "CMIF peak"} for p in peaks]
    result.sort(key=lambda d: d["fn_hz"])
    return result


def poles_from_estimates(fn_hz: np.ndarray, xi: np.ndarray) -> np.ndarray:
    """
    Convert fn (Hz) and ξ arrays into continuous-time complex poles.
    Returns (n_modes,) complex — positive-imaginary half only.
    """
    wn = 2.0 * np.pi * np.asarray(fn_hz, dtype=float)
    xi = np.asarray(xi, dtype=float)
    wd = wn * np.sqrt(np.maximum(1.0 - xi**2, 0.0))
    return -xi * wn + 1j * wd


def _physical_mask(poles_s: np.ndarray, f_min: float, f_max: float) -> np.ndarray:
    """Keep poles with positive imaginary part, damping 0–30 %, fn in [f_min, f_max]."""
    fn = np.abs(poles_s.imag) / (2.0 * np.pi)
    xi = -poles_s.real / (np.abs(poles_s) + 1e-30)
    return (poles_s.imag > 0) & (xi > 0) & (xi < 0.30) & (fn >= f_min) & (fn <= f_max)


def plscf_poles(H: np.ndarray, freqs: np.ndarray, n_order: int) -> np.ndarray:
    """
    pLSCF for one model order.
    H: (n_freqs, n_outputs) complex
    freqs: (n_freqs,) Hz
    Returns physical continuous-time poles as complex ndarray.
    """
    n_freqs, n_out = H.shape
    dt = 1.0 / (2.0 * freqs[-1])
    z = np.exp(1j * 2.0 * np.pi * freqs * dt)  # (n_freqs,)

    # Vandermonde-like basis: Z[i, k] = z[i]^k, k=0..n_order
    k = np.arange(n_order + 1)
    Z = z[:, None] ** k  # (n_freqs, n_order+1)

    # For each output channel o: H_o * A(z) = B_o(z)
    # Eliminate B_o: collect columns for numerator (free) and denominator (constrained)
    # Normal equations approach (real-valued): stack real and imaginary parts
    # Right-hand-side: H * Z[:,0..n_order], solve for denominator coefficients
    # Formulation: [Z  -diag(H_o) Z] [b_o; a] = 0  → normal equations for a

    # Build the matrix T = Σ_o  conj(Z).T @ diag(H_o).T @ diag(H_o) @ Z - ...
    # Standard pLSCF normal equation (real-valued formulation):
    # Collect: for each row i, each output o: constraint is H_o[i]*A[i] = B_o[i]
    # i.e. sum_k alpha_k z[i]^k = sum_k beta_{o,k} z[i]^k / H_o[i]  (not quite)
    # Correct approach: separate numerator and denominator blocks.

    # Build overdetermined system [L_num | L_den] where L_den encodes -H*Z, L_num encodes Z
    # We solve for [vec(B); alpha_1..alpha_n] with alpha_0 = 1 (monic denominator)
    # Size: (2 * n_freqs * n_out) rows (real + imag stacked), cols: n_out*(n_order+1) + n_order

    n_rows = 2 * n_freqs * n_out
    n_num_cols = n_out * (n_order + 1)
    n_den_cols = n_order  # alpha_0 = 1 (monic), solve for alpha_1..alpha_n_order
    n_cols = n_num_cols + n_den_cols

    A_mat = np.zeros((n_rows, n_cols))

    for o in range(n_out):
        row_r = slice(o * n_freqs, (o + 1) * n_freqs)               # real block rows
        row_i = slice((n_out + o) * n_freqs, (n_out + o + 1) * n_freqs)  # imag block rows
        num_cols = slice(o * (n_order + 1), (o + 1) * (n_order + 1))

        # Numerator block: real part
        A_mat[row_r, num_cols] = Z.real
        A_mat[row_i, num_cols] = Z.imag

        # Denominator block: -H_o * Z[:,1..n_order]  (alpha_0=1 → rhs contribution)
        HZ = H[:, o:o+1] * Z[:, 1:]  # (n_freqs, n_order)
        A_mat[row_r, n_num_cols:] = -HZ.real
        A_mat[row_i, n_num_cols:] = -HZ.imag

    # Right-hand side: H_o * Z[:,0] * alpha_0 = H_o (monic term)
    rhs = np.zeros(n_rows)
    for o in range(n_out):
        HZ0 = H[:, o] * Z[:, 0]
        rhs[o * n_freqs:(o + 1) * n_freqs] = HZ0.real
        rhs[(n_out + o) * n_freqs:(n_out + o + 1) * n_freqs] = HZ0.imag

    sol, *_ = np.linalg.lstsq(A_mat, rhs, rcond=None)
    alpha = np.concatenate([[1.0], sol[n_num_cols:]])  # monic: alpha_0 = 1

    # Roots of denominator polynomial in z-domain
    # poly is alpha[0]*z^n + alpha[1]*z^(n-1) + ... + alpha[n]
    # Our basis is z^0..z^n, so polynomial coefficients in descending order = alpha reversed
    z_poles = np.roots(alpha[::-1])

    s_poles = np.log(z_poles) / dt
    mask = _physical_mask(s_poles, float(freqs[0]), float(freqs[-1]))
    return s_poles[mask]


def era_poles(
    H: np.ndarray, freqs: np.ndarray, n_order: int, fs: float
) -> tuple[np.ndarray, np.ndarray]:
    """
    ERA for one model order.
    H: (n_freqs, n_outputs) complex — H1 FRF matrix
    freqs: (n_freqs,) Hz
    fs: sample rate (Hz)
    Returns: (poles complex (n_physical,), mode_shapes (n_outputs, n_physical))
    """
    n_out = H.shape[1]

    # Compute IRF via irfft for each output channel
    # Stack IRF columns into (n_t, n_out)
    n_fft = 2 * (len(freqs) - 1)
    irf = np.fft.irfft(H, n=n_fft, axis=0)  # (n_t, n_out)
    n_t = irf.shape[0]

    # Build block Hankel matrix H0 and H1 (shifted by 1)
    # Size: (n_out * r) x s, choose r = s = n_t // 4 clipped so r*s feasible
    r = max(n_order, 4)
    s = max(n_order, 4)
    if r + s > n_t - 1:
        r = (n_t - 1) // 2
        s = (n_t - 1) - r

    def _hankel(irf_data, offset):
        rows = n_out * r
        cols = s
        mat = np.zeros((rows, cols))
        for i in range(r):
            for j in range(s):
                t = i + j + offset
                if t < n_t:
                    mat[i * n_out:(i + 1) * n_out, j] = irf_data[t]
        return mat

    H0 = _hankel(irf, 0)
    H1 = _hankel(irf, 1)

    U, sv, Vt = scipy.linalg.svd(H0, full_matrices=False)
    rank = min(n_order, len(sv))
    U_r = U[:, :rank]
    S_r = sv[:rank]
    V_r = Vt[:rank, :].T

    S_inv_half = np.diag(1.0 / np.sqrt(S_r))
    S_half = np.diag(np.sqrt(S_r))

    A_sys = S_inv_half @ U_r.T @ H1 @ V_r @ S_inv_half
    # Observability matrix O = U_r @ diag(sqrt(S_r)), C = O[:n_out, :]
    O = U_r @ S_half
    C_obs = O[:n_out, :]  # (n_out, rank)

    evals, evecs = scipy.linalg.eig(A_sys)
    dt = 1.0 / fs
    s_poles = np.log(evals) / dt

    mask = _physical_mask(s_poles, float(freqs[0]), float(freqs[-1]))
    s_phys = s_poles[mask]
    evecs_phys = evecs[:, mask]

    # Mode shapes: C_obs @ evecs
    mode_shapes = C_obs @ evecs_phys  # (n_out, n_physical)
    return s_phys, mode_shapes


def _mac(phi_a: np.ndarray, phi_b: np.ndarray) -> float:
    num = np.abs(phi_a.conj() @ phi_b) ** 2
    den = (phi_a.conj() @ phi_a).real * (phi_b.conj() @ phi_b).real
    return float(num / (den + 1e-30))


def build_stability_table(
    H: np.ndarray,
    freqs: np.ndarray,
    fs: float,
    max_order: int,
    method: str = "plscf",
    df_thr: float = 0.01,
    dd_thr: float = 0.05,
    mac_thr: float = 0.95,
) -> list[dict]:
    """
    Sweep model orders 2..max_order (step 2) and classify pole stability.
    Returns list of dicts per order: {order, poles, fn, xi, stability, mode_shapes}.
    """
    orders = range(2, max_order + 1, 2)
    results = []
    prev = None

    for n in orders:
        try:
            if method == "era":
                poles, mshapes = era_poles(H, freqs, n, fs)
            else:
                poles = plscf_poles(H, freqs, n)
                # Lightweight residue extraction for MAC computation
                if len(poles) > 0:
                    try:
                        res = extract_residues(H, freqs, poles)
                        mshapes = res.T  # (n_poles, n_out) → transpose for MAC use
                    except Exception:
                        mshapes = np.ones((len(poles), H.shape[1]), dtype=complex)
                else:
                    mshapes = np.zeros((0, H.shape[1]), dtype=complex)
        except Exception:
            results.append({"order": n, "poles": np.array([]), "fn": np.array([]),
                            "xi": np.array([]), "stability": [], "mode_shapes": np.zeros((0, H.shape[1]))})
            prev = None
            continue

        if len(poles) == 0:
            results.append({"order": n, "poles": poles, "fn": np.array([]),
                            "xi": np.array([]), "stability": [], "mode_shapes": mshapes})
            prev = None
            continue

        fn = np.abs(poles.imag) / (2.0 * np.pi)
        xi = -poles.real / (np.abs(poles) + 1e-30)
        stability = []

        for k in range(len(poles)):
            if prev is None or len(prev["poles"]) == 0:
                stability.append("new")
                continue
            # Find nearest previous pole by frequency
            df = np.abs(fn[k] - prev["fn"]) / (fn[k] + 1e-30)
            nearest = int(np.argmin(df))
            if df[nearest] > df_thr:
                stability.append("new")
                continue
            dd = abs(xi[k] - prev["xi"][nearest]) / (prev["xi"][nearest] + 1e-30)
            if dd > dd_thr:
                stability.append("stable_f")
                continue
            # MAC check
            if len(mshapes) > 0 and len(prev["mode_shapes"]) > 0:
                mac_val = _mac(mshapes[k], prev["mode_shapes"][nearest])
            else:
                mac_val = 0.0
            if mac_val >= mac_thr:
                stability.append("stable_all")
            else:
                stability.append("stable_fd")

        results.append({
            "order": n,
            "poles": poles,
            "fn": fn,
            "xi": xi,
            "stability": stability,
            "mode_shapes": mshapes,
        })
        prev = results[-1]

    return results


def extract_residues(H: np.ndarray, freqs: np.ndarray, poles: np.ndarray) -> np.ndarray:
    """
    Partial-fraction residue extraction via least squares.
    H: (n_freqs, n_outputs) complex
    poles: (n_modes,) complex (positive-imaginary, one per mode)
    Returns residues: (n_outputs, n_modes) complex
    """
    omega = 2.0 * np.pi * freqs  # (n_freqs,)

    # Build basis matrix Phi: (n_freqs, n_modes)
    # Phi[i, k] = 1/(j*omega[i] - s_k) + 1/(j*omega[i] - conj(s_k))
    jw = 1j * omega[:, None]  # (n_freqs, 1)
    Phi = 1.0 / (jw - poles[None, :]) + 1.0 / (jw - poles.conj()[None, :])  # (n_freqs, n_modes)

    if H.shape[0] < 2 * len(poles):
        warnings.warn(
            f"extract_residues: n_freqs ({H.shape[0]}) < 2×n_modes ({2 * len(poles)}); "
            "residue fit may be ill-conditioned.",
            RuntimeWarning,
            stacklevel=2,
        )

    # Complex least-squares: residues are complex (encode mode-shape amplitude+phase)
    residues, *_ = np.linalg.lstsq(Phi, H, rcond=None)  # (n_modes, n_out) complex
    return residues.T  # (n_out, n_modes)


def synthesize_frf(
    freqs: np.ndarray, poles: np.ndarray, residues: np.ndarray
) -> np.ndarray:
    """
    Synthesise FRF from poles and residues.
    residues: (n_outputs, n_modes) complex
    Returns H_syn: (n_freqs, n_outputs) complex
    """
    omega = 2.0 * np.pi * freqs
    jw = 1j * omega[:, None]  # (n_freqs, 1)

    # basis: (n_freqs, n_modes)
    basis = 1.0 / (jw - poles[None, :]) + 1.0 / (jw - poles.conj()[None, :])
    return basis @ residues.T  # (n_freqs, n_outputs)


def modal_fit_nmse(H_measured: np.ndarray, H_syn: np.ndarray) -> np.ndarray:
    """NMSE per output channel in dB. Lower = better."""
    err = H_measured - H_syn
    nmse = np.sum(np.abs(err) ** 2, axis=0) / (np.sum(np.abs(H_measured) ** 2, axis=0) + 1e-30)
    return 10.0 * np.log10(nmse + 1e-30)


def fdd_svd(Syy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """SVD of the output spectral matrix at each frequency line.

    Syy : (n_freqs, n_out, n_out) complex
    Returns : (sv (n_freqs, n_out), svecs (n_freqs, n_out, n_out))
        sv    — singular values, first column is the Power CMIF
        svecs — left singular vectors; svecs[k, :, r] is the mode-shape
                estimate at frequency k for singular value r
    """
    n_freqs, n_out, _ = Syy.shape
    sv = np.zeros((n_freqs, n_out))
    svecs = np.zeros((n_freqs, n_out, n_out), dtype=complex)
    for k in range(n_freqs):
        U, s, _ = np.linalg.svd(Syy[k])
        sv[k] = s
        svecs[k] = U
    return sv, svecs


def fdd_damping(
    sv1: np.ndarray, freqs: np.ndarray, peak_idx: int
) -> tuple[float, float, float]:
    """Half-power bandwidth damping estimate for one FDD peak.

    sv1      : (n_freqs,) first singular values (linear scale, not dB)
    peak_idx : index of the peak in freqs / sv1
    Returns  : (xi_pct, f_a, f_b)
        xi_pct — damping ratio in percent
        f_a    — lower half-power frequency (Hz)
        f_b    — upper half-power frequency (Hz)
    """
    half_power = sv1[peak_idx] / 2.0

    # Lower half-power frequency
    f_a = float(freqs[0])
    for k in range(peak_idx - 1, -1, -1):
        if sv1[k] <= half_power:
            # Linear interpolation between k and k+1
            df = freqs[k + 1] - freqs[k]
            ds = sv1[k + 1] - sv1[k]
            f_a = float(freqs[k] + (half_power - sv1[k]) / ds * df) if ds != 0 else float(freqs[k])
            break

    # Upper half-power frequency
    f_b = float(freqs[-1])
    for k in range(peak_idx + 1, len(sv1)):
        if sv1[k] <= half_power:
            df = freqs[k] - freqs[k - 1]
            ds = sv1[k] - sv1[k - 1]
            f_b = float(freqs[k - 1] + (half_power - sv1[k - 1]) / ds * df) if ds != 0 else float(freqs[k])
            break

    fn = float(freqs[peak_idx])
    xi_pct = (f_b - f_a) / (2.0 * fn) * 100.0 if fn > 0 else 0.0
    return xi_pct, f_a, f_b


def compute_mac(phi_ref: np.ndarray, phi_comp: np.ndarray) -> np.ndarray:
    """MAC matrix between two sets of mode shapes.

    Parameters
    ----------
    phi_ref  : (n_dof, n_ref)  — reference (FE) mode shapes, real or complex
    phi_comp : (n_dof, n_comp) — comparison (exp) mode shapes, real or complex

    Returns
    -------
    mac : (n_ref, n_comp) MAC values in [0, 1]
    """
    num = np.abs(phi_ref.conj().T @ phi_comp) ** 2
    denom = (
        np.sum(np.abs(phi_ref) ** 2, axis=0)[:, None]
        * np.sum(np.abs(phi_comp) ** 2, axis=0)[None, :]
    )
    return num / np.maximum(denom, np.finfo(float).tiny)
