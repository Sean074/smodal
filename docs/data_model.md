# Data Model & Core Module API

Authoritative reference for session state keys and core module function signatures.
Source of truth for `docs/workflow_pages.md` cross-references.

---

## Session state

All pages communicate through `st.session_state`. Keys and their owners:

| Key | Set by | Consumed by |
|---|---|---|
| `df` | `1_Time_History.py` (load) | `2_FFT.py`, `3_Spectral_Analysis.py` |
| `input_channel` | `1_Time_History.py` (channel assign) | `2_FFT.py`, `3_Spectral_Analysis.py` |
| `output_channels` | `1_Time_History.py` (channel assign) | `2_FFT.py`, `3_Spectral_Analysis.py` |
| `sample_rate` | `1_Time_History.py` (data summary) | `2_FFT.py`, `3_Spectral_Analysis.py` |
| `analysis_name`, `analyst`, `description` | `app.py` | `1_Time_History.py` (log save) |
| `comment` | `1_Time_History.py` | `1_Time_History.py` (log save) |
| `th_file_names` | `1_Time_History.py` (load) | `1_Time_History.py` (re-load guard) |
| `processed_df` | `1_Time_History.py` | `2_FFT.py`, `3_Spectral_Analysis.py` |
| `processing_info` | `1_Time_History.py` | `2_FFT.py` (display label) |
| `fft_results` | `2_FFT.py` | `3_Spectral_Analysis.py` |
| `spectral_results` | `3_Spectral_Analysis.py` | `3_Spectral_Analysis.py` (cached) |
| `simo_df` | `4_SIMO.py` (load) | `4_SIMO.py` (Build, preview) |
| `simo_sample_rate` | `4_SIMO.py` (load) | `4_SIMO.py` (`fs`) |
| `simo_file_name` | `4_SIMO.py` (load) | `4_SIMO.py` (re-load guard) |
| `si_freqs` | `4_SIMO.py` (Build) | `4_SIMO.py` (charts, Extract) |
| `si_stability_table` | `4_SIMO.py` (Build) | `4_SIMO.py` (Step 2, Stability tab) |
| `si_cmif` | `4_SIMO.py` (Build) | `4_SIMO.py` (Stability tab bg, CMIF tab) — shape `(n_freqs, 2)` |
| `si_H_mat` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_freqs_band` | `4_SIMO.py` (Build) | `4_SIMO.py` (Build) |
| `si_sel_outputs` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_frf_est_used` | `4_SIMO.py` (Build) | `4_SIMO.py` (reference) |
| `modal_results` | `4_SIMO.py` (Extract) | `7_MAC.py`, `8_Wireframe.py` |
| `mimo_run_a_df` | `5_MIMO.py` (load) | `5_MIMO.py` (Build) |
| `mimo_run_b_df` | `5_MIMO.py` (load) | `5_MIMO.py` (Build) |
| `mimo_sample_rate` | `5_MIMO.py` (load) | `5_MIMO.py` (Build) |
| `mimo_H_mat` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_freqs` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract, charts) |
| `mimo_freqs_band` | `5_MIMO.py` (Build) | `5_MIMO.py` (reference) |
| `mimo_cmif` | `5_MIMO.py` (Build) | `5_MIMO.py` (CMIF tab, Stability bg) |
| `mimo_stability_table` | `5_MIMO.py` (Build) | `5_MIMO.py` (Stability tab, Step 2) |
| `mimo_sel_outputs` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_n_out` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_modal_results` | `5_MIMO.py` (Extract) | `7_MAC.py`, `8_Wireframe.py` |
| `oma_df` | `6_OMA.py` (load) | `6_OMA.py` |
| `oma_sample_rate` | `6_OMA.py` (load) | `6_OMA.py` |
| `oma_file_name` | `6_OMA.py` (load) | `6_OMA.py` (re-load guard) |
| `oma_freqs` | `6_OMA.py` (Build) | `6_OMA.py` (plot, Extract) |
| `oma_sv` | `6_OMA.py` (Build) | `6_OMA.py` (plot, Extract) — shape `(n_freqs, n_out)` |
| `oma_svecs` | `6_OMA.py` (Build) | `6_OMA.py` (Extract) — shape `(n_freqs, n_out, n_out)` |
| `oma_Syy` | `6_OMA.py` (Build) | `6_OMA.py` — shape `(n_freqs, n_out, n_out)` |
| `oma_sel_outputs` | `6_OMA.py` (Build) | `6_OMA.py` (Extract) |
| `oma_modal_results` | `6_OMA.py` (Extract) | `7_MAC.py`, `8_Wireframe.py` |

Pages 2 and 3 guard against missing data with:
```python
if st.session_state.get("df") is None:
    st.warning("Go to Page 1 — Time History and upload a data file.")
    st.stop()
```

---

## Core module API

### `core/data_loader.py`
- `load_csv(file)` — accepts a file-like object, normalises the time column name, returns `(df, error_string)`.
- `compute_sample_rate(time)` — estimates Hz from mean `diff` of the time array.
- `compute_summary(df, input_ch, output_chs)` — returns a list of dicts (one per channel) with samples, sample rate, duration, min/max time, min/max value, RMS.

### `core/preprocess.py`
- `build_butter_sos(ftype: str, order: int, cutoffs: Union[float, list[float]], fs: float) -> np.ndarray` — constructs a Butterworth SOS filter; `cutoffs` is a float (Hz) for LP/HP or `[low, high]` for BP/BS.
- `trim_and_filter(df, t_min, t_max, ftype, order, cutoffs: Union[float, list[float]], fs) -> pd.DataFrame` — trims a DataFrame to the time window then applies the filter in-place; `ftype='None'` or `cutoffs=None` skips filtering.

### `core/spectral.py`
- `compute_fft(signal, sample_rate, window)` — applies a scipy window and returns `(freqs_hz, fft_complex)` via `np.fft.rfft`.
- `compute_psd(signal, sample_rate, nperseg, noverlap, window)` — single-channel auto-PSD via Welch; returns `(freqs_hz, Pxx)`.
- `compute_spectral_quantities(Sx, Sy)` — computes single-realisation spectral quantities from complex FFT arrays; returns dict with `Gxx`, `Gyy`, `Gyx`, `Gxy`, `H1`, `H2`, `Hv`, `gamma2`.
- `compute_welch_quantities(x, y, sample_rate, nperseg, noverlap, window)` — Welch-averaged spectral quantities using `scipy.signal.welch` and `csd`; returns the same keys as above plus `freqs`.
- `compute_output_spectral_matrix(signals, fs, nperseg, noverlap, window)` — output-only PSD matrix for OMA; `signals` is `(n_samples, n_out)`; returns `(freqs, Syy)` where `Syy` is `(n_freqs, n_out, n_out)` complex, conjugate symmetric.

Windows supported by `compute_fft`: `uniform` (boxcar), `hanning`, `flattop`, `force` (hann), `exponential`.
Windows supported by `compute_welch_quantities`: any scipy window name (typically `hann`, `flattop`, `boxcar`).

### `core/sysid.py`
- `compute_cmif(H)` — `np.linalg.norm(H, axis=1)`; Euclidean norm per frequency line (equivalent to first singular value of a row vector).
- `deduplicate_stable_poles(stab_results, tol)` — extracts and deduplicates fully-stable (`stable_all`) poles from a stability table; returns list of dicts with `fn_hz`, `xi_pct`, `source`.
- `cmif_peak_estimates(cmif, freqs, n_modes)` — top-N peaks by `scipy.signal.find_peaks` prominence; falls back to evenly spaced frequencies.
- `poles_from_estimates(fn_hz, xi)` — converts fn (Hz) and ξ arrays to continuous-time complex poles `s = −ξωₙ + jωd`.
- `plscf_poles(H, freqs, n_order)` — pLSCF for one model order; real-valued normal equations, monic denominator, `numpy.roots`, `s = log(z)/Δt`; returns physical poles only.
- `era_poles(H, freqs, n_order, fs)` — ERA for one model order; IRF via `irfft`, block Hankel, SVD, state-space eigendecomposition; returns `(poles, mode_shapes)`.
- `build_stability_table(H, freqs, fs, max_order, method, df_thr, dd_thr, mac_thr)` — sweeps orders 2..max_order step 2; classifies each pole as `new` / `stable_f` / `stable_fd` / `stable_all`; returns list of dicts.
- `extract_residues(H, freqs, poles)` — complex LS fit of partial-fraction basis to H; returns `(n_outputs, n_modes)` complex residues. Note: fires a `RuntimeWarning` when `n_freqs < 2 × n_modes` (ill-conditioned fit).
- `synthesize_frf(freqs, poles, residues)` — partial-fraction sum; returns `(n_freqs, n_outputs)` complex.
- `modal_fit_nmse(H_measured, H_syn)` — NMSE per output channel in dB (lower = better).
- `fdd_svd(Syy)` — SVD of the output spectral matrix at every frequency; `Syy` is `(n_freqs, n_out, n_out)`; returns `(sv, svecs)` where `sv[:,0]` is the Power CMIF.
- `fdd_damping(sv1, freqs, peak_idx)` — half-power bandwidth damping estimate; returns `(xi_pct, f_a, f_b)`.
- `compute_mac(phi_ref, phi_comp)` — MAC matrix `(n_ref, n_comp)` between two sets of mode shapes.

### `core/mimo.py`
- `compute_mimo_cmif(H, n_out)` — SVD per frequency line of the (n_out × 2) MIMO FRF slice; returns `(n_freqs, 2)` singular values σ₁, σ₂.
- `compute_mimo_frfs(run_a_proc, run_b_proc, input_a, input_b, sel_outputs, fs, frf_method, frf_est, n_seg, ovlp_pct, welch_win)` — assembles the stacked MIMO FRF matrix from two processed runs; returns `(H_stacked, freqs_full)` where `H_stacked` is `(n_freqs, n_out * 2)`.

### `core/plots.py`
- `fft_subplot(df_proc, channels, fs, fmax)` — returns a stacked Plotly figure of magnitude FFT (dB) for each channel.
- `frf_subplot(df_proc, input_ch, output_chs, fs, fmax)` — returns a stacked magnitude + phase FRF figure (H1 estimator, single FFT) for each output channel.

### `core/geometry.py`
- `parse_wireframe_bdf(file)` — parses a NASTRAN BDF (free-field or 8-char fixed-field) for `GRID` and `PLOTEL` cards; returns a `GeomModel` dataclass with `.grids` and `.plotels` dicts.
- `parse_f06(file)` — parses a NASTRAN F06 output file for real eigenvalues and eigenvectors; returns `{"frequencies_hz": [...], "mode_shapes": [{gid: [T1,T2,T3]}, ...]}`.
- `expand_rbe3_displacements(geom, meas_disps)` — propagates measured grid displacements through RBE3 elements by weighted average; fills zeros for unmeasured grids; returns `{gid: np.ndarray}`.
