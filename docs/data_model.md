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
| `fft_results` | `2_FFT.py` | `3_Spectral_Analysis.py` — includes `n_samples` (original signal length) used by Single FFT PSD normalisation |
| `spectral_results` | `3_Spectral_Analysis.py` | `3_Spectral_Analysis.py` (cached) |
| `simo_df` | `4_SIMO.py` (load) | `4_SIMO.py` (Build, preview) |
| `simo_sample_rate` | `4_SIMO.py` (load) | `4_SIMO.py` (`fs`) |
| `simo_file_name` | `4_SIMO.py` (load) | `4_SIMO.py` (re-load guard) |
| `si_freqs` | `4_SIMO.py` (Build) | `4_SIMO.py` (charts, Extract) |
| `si_stability_table` | `4_SIMO.py` (Build) | `4_SIMO.py` (Step 2, Stability tab) |
| `si_cmif` | `4_SIMO.py` (Build) | `4_SIMO.py` (Stability tab bg, CMIF tab) — shape `(n_freqs, 2)` |
| `si_H_mat` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_freqs_band` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_H_mat_band` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) — band-limited FRF matrix `(n_band, n_outputs)` matching `si_freqs_band` |
| `si_sel_outputs` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_frf_est_used` | `4_SIMO.py` (Build) | `4_SIMO.py` (reference) |
| `si_spectral_channels` | `4_SIMO.py` (Build) | `4_SIMO.py` (Spectral tab) — `dict[ch → {Gxx, Gyy, Gxy, Gyx, H1, H2, Hv, gamma2}]` |
| `si_spectral_freqs` | `4_SIMO.py` (Build) | `4_SIMO.py` (Spectral tab) — frequency axis matching spectral channel arrays |
| `si_frf_method_used` | `4_SIMO.py` (Build) | `4_SIMO.py` (Spectral tab coherence gate) — `"Welch"` or `"Single FFT"` |
| `modal_results` | `4_SIMO.py` (Extract) | `7_MAC.py`, `8_Wireframe.py` |
| `mimo_run_a_df` | `5_MIMO.py` (load) | `5_MIMO.py` (Build) |
| `mimo_run_b_df` | `5_MIMO.py` (load) | `5_MIMO.py` (Build) |
| `mimo_sample_rate` | `5_MIMO.py` (load) | `5_MIMO.py` (Build) |
| `mimo_file_a_name` | `5_MIMO.py` (load) | `5_MIMO.py` (re-load guard) |
| `mimo_file_b_name` | `5_MIMO.py` (load) | `5_MIMO.py` (re-load guard) |
| `mimo_H_mat` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_freqs` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract, charts) |
| `mimo_freqs_band` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_H_mat_band` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) — band-limited FRF matrix `(n_band, n_out*2)` matching `mimo_freqs_band` |
| `mimo_cmif` | `5_MIMO.py` (Build) | `5_MIMO.py` (CMIF tab, Stability bg) |
| `mimo_stability_table` | `5_MIMO.py` (Build) | `5_MIMO.py` (Stability tab, Step 2) |
| `mimo_sel_outputs` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_n_out` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_frf_est_used` | `5_MIMO.py` (Build) | `5_MIMO.py` (reference) |
| `mimo_spectral_channels` | `5_MIMO.py` (Build) | `5_MIMO.py` (Spectral tab) — `dict[ch → {Gxx, Gyy, Gxy, Gyx, H1, H2, Hv, gamma2}]` (Run A input reference) |
| `mimo_spectral_freqs` | `5_MIMO.py` (Build) | `5_MIMO.py` (Spectral tab) — frequency axis matching spectral channel arrays |
| `mimo_frf_method_used` | `5_MIMO.py` (Build) | `5_MIMO.py` (Spectral tab coherence gate) — `"Welch"` or `"Single FFT"` |
| `mimo_modal_results` | `5_MIMO.py` (Extract) | `7_MAC.py`, `8_Wireframe.py` |
| `oma_df` | `6_OMA.py` (load) | `6_OMA.py` |
| `oma_sample_rate` | `6_OMA.py` (load) | `6_OMA.py` |
| `oma_file_name` | `6_OMA.py` (load) | `6_OMA.py` (re-load guard) |
| `oma_freqs` | `6_OMA.py` (Build) | `6_OMA.py` (plot, Extract) |
| `oma_sv` | `6_OMA.py` (Build) | `6_OMA.py` (plot, Extract) — shape `(n_freqs, n_out)` |
| `oma_svecs` | `6_OMA.py` (Build) | `6_OMA.py` (Extract) — shape `(n_freqs, n_out, n_out)` |
| `oma_Syy` | `6_OMA.py` (Build) | `6_OMA.py` — shape `(n_freqs, n_out, n_out)` |
| `oma_sel_outputs` | `6_OMA.py` (Build) | `6_OMA.py` (Extract) |
| `oma_peak_estimates` | `6_OMA.py` (Build) | `6_OMA.py` (Step 2 init) — list of dicts `{fn_hz, xi_pct, source}` from FDD auto-peak detection; replaced on each Build |
| `oma_peak_seed_ver` | `6_OMA.py` (Build, file reload) | `6_OMA.py` (data_editor key) — integer version counter; incrementing forces `st.data_editor` to re-initialise from seed data |
| `oma_modal_results` | `6_OMA.py` (Extract) | `7_MAC.py`, `8_Wireframe.py` |
| `mac_exp_source` | `7_MAC.py` (radio) | `7_MAC.py` (mode shape selection) |
| `mac_mapping` | `7_MAC.py` (channel-DOF form) | `7_MAC.py` (Compute MAC) |
| `mac_matrix` | `7_MAC.py` (Compute MAC) | `7_MAC.py` (heatmap, frequency table) — shape `(n_fe_modes, n_exp_modes)` |
| `mac_fe_freqs` | `7_MAC.py` (Compute MAC) | `7_MAC.py` (heatmap labels, freq table) |
| `mac_exp_freqs` | `7_MAC.py` (Compute MAC) | `7_MAC.py` (heatmap labels, freq table) |
| `mac_f06_data` | `7_MAC.py` (F06 upload) | `7_MAC.py` (Compute MAC) |
| `_mac_f06_name` | `7_MAC.py` (F06 upload guard) | `7_MAC.py` (re-load guard) |

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
- `fdd_damping(sv1, freqs, peak_idx)` — half-power bandwidth damping estimate; returns `(xi_pct, f_a, f_b)`. Returns `(0.0, freqs[0], freqs[-1])` sentinel when no upper half-power crossing is found (peak at or near last frequency index); callers should clamp 0.0 to a minimum damping value.
- `compute_mac(phi_ref, phi_comp)` — MAC matrix `(n_ref, n_comp)` between two sets of mode shapes.

### `core/ema_pipeline.py`
Shared EMA mode-extraction pipeline. Both SIMO (page 4) and MIMO (page 5) call these functions so that fixes to the residue/synthesis/NMSE chain propagate to both pages automatically.

- `extract_modes(H_band, freqs_band, freqs_full, fn_estimates, xi_estimates) → dict` — runs `poles_from_estimates → extract_residues → synthesize_frf (band + full) → modal_fit_nmse` in one call. `H_band` and synthesis arrays share the same `n_outputs` dimension: `(n_out,)` for SIMO, `(n_out*2,)` for MIMO stacked runs. MIMO-specific residue reshape stays in the page. Returns dict with keys: `poles`, `fn_hz`, `xi`, `residues` `(n_outputs, n_modes)`, `H_synthesis_band`, `H_synthesis_full`, `nmse`.
- `nmse_quality_label(nmse_db: float) → str` — returns `"Excellent"` / `"Good"` / `"Acceptable"` / `"Poor"` for thresholds `< -30` / `< -20` / `< -10` / `>= -10` dB. Used in the fit-quality expander on both pages 4 and 5.
- `prepare_band_arrays(H, freqs, f_min, f_max) → (H_band, freqs_band)` — slices `H` and `freqs` to `[f_min, f_max]` Hz using a single boolean mask. Raises `ValueError` if the band is empty.

### `core/mimo.py`
- `compute_mimo_cmif(H, n_out)` — SVD per frequency line of the (n_out × 2) MIMO FRF slice; returns `(n_freqs, 2)` singular values σ₁, σ₂.
- `compute_mimo_frfs(run_a_proc, run_b_proc, input_a, input_b, sel_outputs, fs, frf_method, frf_est, n_seg, ovlp_pct, welch_win)` — assembles the stacked MIMO FRF matrix from two processed runs; returns `(H_stacked, freqs_full)` where `H_stacked` is `(n_freqs, n_out * 2)`. Raises `ValueError` if `sel_outputs` is empty.

### `core/plots.py`
- `fft_subplot(df_proc, channels, fs, fmax)` — returns a stacked Plotly figure of magnitude FFT (dB) for each channel.
- `frf_subplot(df_proc, input_ch, output_chs, fs, fmax)` — returns a stacked magnitude + phase FRF figure (H1 estimator, single FFT) for each output channel.

### `core/uff_writer.py`
- `write_uff58_shapes(fn_hz, xi, residues, channel_names, analysis_name="") → bytes` — writes identified mode shapes as UFF Dataset 58 (one dataset per channel). `fn_hz`: `(n_modes,)` Hz; `xi`: `(n_modes,)` damping ratios 0–1; `residues`: `(n_channels, n_modes)` complex. Each dataset uses function type 3 (Ordinary Mode Shape), abscissa type 18 (frequency Hz), non-uniform abscissa with data stored as `(fn, real, imag)` triplets in `6E13.5` format. Damping values written to ID line 4.
- `write_uff58_shapes_mimo(fn_hz, xi, r3d, channel_names, analysis_name="") → bytes` — MIMO variant. `r3d`: `(n_out, 2, n_modes)` complex (run A / run B). Produces `2 × n_out` datasets with channel names prefixed `A_` / `B_`.

### `core/geometry.py`
- `parse_wireframe_bdf(file)` — parses a NASTRAN BDF (free-field or 8-char fixed-field) for `GRID` and `PLOTEL` cards; returns a `GeomModel` dataclass with `.grids` and `.plotels` dicts.
- `parse_f06(file)` — parses a NASTRAN F06 output file for real eigenvalues and eigenvectors; returns `{"frequencies_hz": [...], "mode_shapes": [{gid: [T1,T2,T3]}, ...]}`.
- `expand_rbe3_displacements(geom, meas_disps)` — propagates measured grid displacements through RBE3 elements by weighted average; fills zeros for unmeasured grids; returns `{gid: np.ndarray}`.

---

## Tools API

Standalone Python utilities in `tools/`. Run directly in scripts or interactively — not part of the Streamlit app. All functions follow the same `(result, error_string | None)` convention as the core modules. See `tools/README.md` for usage examples.

### `tools/format_converter.py`
- `from_excel(path, sheet=0, time_col=None, unit_scales=None)` — load an Excel workbook sheet; requires `openpyxl`. Returns `(df, error)`.
- `from_delimited(path, sep='\t', time_col=None, unit_scales=None)` — load a delimited text file (TSV, semicolon-CSV, etc.). Returns `(df, error)`.
- `rename_columns(df, mapping)` — rename data columns; `mapping` is `{old: new}`; 'time' cannot be remapped. Returns `(df, error)`.
- `save_csv(df, out_path)` — write DataFrame to CSV ready for `core/data_loader.load_csv`. Returns `error | None`.

`time_col`: column to rename to `'time'`. Auto-detected from common names (`time`, `Time`, `t`, etc.) if `None`.
`unit_scales`: `{column: scale_factor}` applied as multiplication before return.

### `tools/channel_math.py`
- `list_channels(df)` — return all column names except `'time'`.
- `add_channel(df, new_name, expression)` — evaluate *expression* using existing columns as variables; blocked tokens checked first, then `pd.eval` with numexpr engine (Python fallback). Append result as *new_name*. Returns copy `(df, error)`.
- `remove_channel(df, name)` — drop a column; `'time'` cannot be removed. Returns copy `(df, error)`.

### `tools/downsample.py`
- `downsample(df, target_fs, method='decimate')` — reduce sample rate to *target_fs* Hz. `method='decimate'` uses `scipy.signal.decimate` (integer factor, Chebyshev AA filter); `method='resample'` uses `scipy.signal.resample` (arbitrary ratio, FFT-based). Returns `(df, error)`.

### `tools/time_sync.py`
- `trim_to_overlap(dfs)` — trim a list of DataFrames to their shared time window. Returns `(trimmed_dfs, error)`.
- `sync_and_merge(dfs, tol_s=1e-4)` — trim to overlap then join all DataFrames on nearest timestamps (reference grid = first DataFrame). Duplicate column names from later DataFrames are suffixed `__N`. Returns `(merged_df, error)`.

---

## Reference datasets

Pre-built analytical datasets for workflow validation and CI regression.

| File | Description |
|------|-------------|
| `data/input/cantilever_beam/cantilever_response.csv` | 300 s time history at fs=200 Hz; columns: `time, force, acc_0m, acc_5m, acc_7m, acc_10m`; tip excitation + 4 accelerometers on a steel cantilever with 100 kg tip mass |
| `data/input/cantilever_beam/cantilever_wireframe.bdf` | NASTRAN free-field BDF; 11 GRID cards (GIDs 1–11 at x=0…10 m) + 10 PLOTEL cards |
| `data/input/cantilever_beam/cantilever_modes.f06` | NASTRAN SOL 103 F06; 4 modes at 0.55, 4.49, 13.67, 27.98 Hz; 11 GIDs per eigenvector (T3 only) |

Generated by `scripts/generate_cantilever_reference.py`. Tutorial: `docs/tutorial_cantilever.ipynb`.

---

## Smoke test coverage

`tests/test_page_smoke.py` contains one `AppTest` smoke test per page (9 total). Each test verifies:
1. The page renders without exception.
2. It accepts minimal input (pre-seeded session state or small file upload).
3. It writes the expected session-state keys.

| Test | Page | Pre-seeded state / input | Asserted keys |
|---|---|---|---|
| `test_page9_method_renders` | 9 — Method | — | `not at.exception` |
| `test_page1_time_history_writes_df` | 1 — Time History | `sample_3ch.csv` upload | `df`, `sample_rate` |
| `test_page2_fft_writes_fft_results` | 2 — FFT | Page 1 state via `_seed_page1_state` | `fft_results` |
| `test_page3_spectral_writes_results` | 3 — Spectral Analysis | Page 1 state; Welch path | `spectral_results` |
| `test_page4_simo_builds_stability_table` | 4 — SIMO | `simo_df`, `simo_sample_rate`; max order 8 | `si_stability_table`, `si_H_mat`, `si_freqs` |
| `test_page5_mimo_builds_stability_table` | 5 — MIMO | `mimo_run_a_df`, `mimo_run_b_df`, `mimo_sample_rate`; max order 8 | `mimo_stability_table`, `mimo_H_mat`, `mimo_freqs` |
| `test_page6_oma_builds_power_cmif` | 6 — OMA | `oma_df`, `oma_sample_rate` | `oma_sv`, `oma_freqs`, `oma_peak_estimates` |
| `test_page7_mac_renders_and_computes` | 7 — MAC | `modal_results`, `mac_f06_data`, `_mac_f06_name` | `mac_matrix` |
| `test_page8_wireframe_renders` | 8 — Wireframe | `modal_results`; `experimental_wireframe.bdf` upload | `not at.exception` |

Pages 4–6 bypass the file-upload UI by pre-seeding DataFrames directly into session state. The `synthetic_modal_results` fixture (in `tests/conftest.py`) provides a minimal valid `modal_results` dict for pages 7–8. Max order is set to 8 on stability-diagram pages to keep CI runtime bounded.
