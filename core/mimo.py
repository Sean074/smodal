from __future__ import annotations

import numpy as np
import pandas as pd

from core.spectral import compute_fft, compute_spectral_quantities, compute_welch_quantities


def compute_mimo_cmif(H: np.ndarray, n_out: int) -> np.ndarray:
    """SVD-based CMIF for MIMO FRF matrix.

    H: (n_freqs, n_out * 2) complex — stacked [H_A | H_B]
    Returns (n_freqs, 2) real — singular values σ₁, σ₂ per frequency line.
    σ₁ reveals all modes; σ₂ resolves repeated / closely-spaced modes.
    """
    n_freqs = H.shape[0]
    sv = np.zeros((n_freqs, 2))
    for i in range(n_freqs):
        s = np.linalg.svd(H[i].reshape(2, n_out).T, compute_uv=False)
        sv[i, 0] = s[0]
        sv[i, 1] = s[1] if len(s) > 1 else 0.0
    return sv


def compute_mimo_frfs(
    run_a_proc: pd.DataFrame,
    run_b_proc: pd.DataFrame,
    input_a: str,
    input_b: str,
    sel_outputs: list[str],
    fs: float,
    frf_method: str,
    frf_est: str,
    n_seg: int = 8,
    ovlp_pct: int = 50,
    welch_win: str = "hann",
) -> tuple[np.ndarray, np.ndarray]:
    """Compute stacked MIMO FRF matrix from two experimental runs.

    Returns (H_stacked, freqs_full) where H_stacked is (n_freqs, n_out * 2).
    Columns are ordered [H_A_out0, …, H_A_outN, H_B_out0, …, H_B_outN].
    """
    if not sel_outputs:
        raise ValueError("sel_outputs must not be empty")

    H_A_cols: list[np.ndarray] = []
    H_B_cols: list[np.ndarray] = []

    if frf_method == "Welch":
        n_proc = len(run_a_proc)
        nperseg = max(4, n_proc // n_seg)
        noverlap = int(nperseg * ovlp_pct / 100)
        for ch in sel_outputs:
            res_a = compute_welch_quantities(
                run_a_proc[input_a].values, run_a_proc[ch].values,
                fs, nperseg, noverlap, welch_win,
            )
            res_b = compute_welch_quantities(
                run_b_proc[input_b].values, run_b_proc[ch].values,
                fs, nperseg, noverlap, welch_win,
            )
            H_A_cols.append(res_a[frf_est])
            H_B_cols.append(res_b[frf_est])
        freqs_full: np.ndarray = res_a["freqs"]
    else:  # Single FFT
        freqs_full, Sx_a = compute_fft(run_a_proc[input_a].values, fs)
        _, Sx_b = compute_fft(run_b_proc[input_b].values, fs)
        for ch in sel_outputs:
            _, Sy_a = compute_fft(run_a_proc[ch].values, fs)
            _, Sy_b = compute_fft(run_b_proc[ch].values, fs)
            H_A_cols.append(compute_spectral_quantities(Sx_a, Sy_a)[frf_est])
            H_B_cols.append(compute_spectral_quantities(Sx_b, Sy_b)[frf_est])

    H_A = np.column_stack(H_A_cols)
    H_B = np.column_stack(H_B_cols)
    return np.column_stack([H_A, H_B]), freqs_full
