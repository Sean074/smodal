# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run the app
streamlit run app.py

# Install dependencies
pip install -r requirements.txt
```

There is no linter or test suite configured.

## Architecture

This is a multi-page **Streamlit** app for structural dynamics modal analysis / system identification.

### Page flow

`app.py` is the landing page (Streamlit entry point). The numbered files in `pages/` are loaded automatically by Streamlit in sidebar order:

| File | Purpose | Status |
|---|---|---|
| `app.py` | Landing page — loads CSV data, assigns channels, saves analysis log | Implemented |
| `pages/1_Time_History.py` | Time history plots, trim range, Butterworth filtering | Implemented |
| `pages/2_FFT.py` | FFT with windowing options, Gain/Phase or Real/Imaginary display | Implemented |
| `pages/3_Spectral_Analysis.py` | Auto/cross power, PSD, coherence, FRF (H1, H2, Hv) — tabbed layout | Implemented |
| `pages/4_SIMO.py` | System Identification — SIMO EMA (stability diagram, mode extraction) | Implemented |
| `pages/5_MIMO.py` | MIMO EMA — multi-reference pLSCF (PolyMAX) | Implemented |
| `pages/6_MAC.py` | Modal Assurance Criteria plot | Stub |
| `pages/7_Wireframe.py` | 3-D wireframe mode shape visualisation | Stub |

`todo.md` tracks known bugs and development notes.

### Shared state

All pages communicate through `st.session_state`. Keys and their owners:

| Key | Set by | Consumed by |
|---|---|---|
| `df` | `app.py` | all pages |
| `input_channel` | `app.py` | all pages |
| `output_channels` | `app.py` | all pages |
| `sample_rate` | `app.py` | all pages |
| `analysis_name`, `analyst`, `description`, `comment` | `app.py` | log save |
| `processed_df` | `1_Time_History.py` | `2_FFT.py`, `3_Spectral_Analysis.py`, `4_SIMO.py` |
| `processing_info` | `1_Time_History.py` | `2_FFT.py` (display label) |
| `fft_results` | `2_FFT.py` | `3_Spectral_Analysis.py` |
| `spectral_results` | `3_Spectral_Analysis.py` | `3_Spectral_Analysis.py` (cached) |
| `si_freqs` | `4_SIMO.py` (Build) | `4_SIMO.py` (charts, Extract) |
| `si_stability_table` | `4_SIMO.py` (Build) | `4_SIMO.py` (Step 2, Stability tab) |
| `si_cmif` | `4_SIMO.py` (Build) | `4_SIMO.py` (Stability tab bg, CMIF tab) — shape `(n_freqs, 2)` |
| `si_H_mat` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_freqs_band` | `4_SIMO.py` (Build) | `4_SIMO.py` (Build) |
| `si_sel_outputs` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_frf_est_used` | `4_SIMO.py` (Build) | `4_SIMO.py` (reference) |
| `modal_results` | `4_SIMO.py` (Extract) | `6_MAC.py`, `7_Wireframe.py` |
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
| `mimo_modal_results` | `5_MIMO.py` (Extract) | `6_MAC.py`, `7_Wireframe.py` |

Every page guards against missing data with:
```python
if st.session_state.get("df") is None:
    st.warning(...)
    st.stop()
```

### Core modules

#### `core/data_loader.py`
- `load_csv(file)` — accepts a file-like object, normalises the time column name, returns `(df, error_string)`.
- `compute_sample_rate(time)` — estimates Hz from mean `diff` of the time array.
- `compute_summary(df, input_ch, output_chs)` — returns a list of dicts (one per channel) with samples, sample rate, duration, min/max time, min/max value, RMS.

#### `core/preprocess.py`
- `build_butter_sos(ftype, order, cutoffs, fs)` — constructs a Butterworth SOS filter; `cutoffs` is a float (Hz) for LP/HP or `[low, high]` for BP/BS.
- `trim_and_filter(df, t_min, t_max, ftype, order, cutoffs, fs)` — trims a DataFrame to the time window then applies the filter in-place; `ftype='None'` or `cutoffs=None` skips filtering.

#### `core/spectral.py`
- `compute_fft(signal, sample_rate, window)` — applies a scipy window and returns `(freqs_hz, fft_complex)` via `np.fft.rfft`.
- `compute_psd(signal, sample_rate, nperseg, noverlap, window)` — single-channel auto-PSD via Welch; returns `(freqs_hz, Pxx)`.
- `compute_spectral_quantities(Sx, Sy)` — computes single-realisation spectral quantities from complex FFT arrays; returns dict with `Gxx`, `Gyy`, `Gyx`, `Gxy`, `H1`, `H2`, `Hv`, `gamma2`.
- `compute_welch_quantities(x, y, sample_rate, nperseg, noverlap, window)` — Welch-averaged spectral quantities using `scipy.signal.welch` and `csd`; returns the same keys as above plus `freqs`.

Windows supported by `compute_fft`: `uniform` (boxcar), `hanning`, `flattop`, `force` (hann), `exponential`.
Windows supported by `compute_welch_quantities`: any scipy window name (typically `hann`, `flattop`, `boxcar`).

#### `core/sysid.py`
- `compute_cmif(H)` — `np.linalg.norm(H, axis=1)`; Euclidean norm per frequency line (equivalent to first singular value of a row vector).
- `deduplicate_stable_poles(stab_results, tol)` — extracts and deduplicates fully-stable (`stable_all`) poles from a stability table; returns list of dicts with `fn_hz`, `xi_pct`, `source`.
- `cmif_peak_estimates(cmif, freqs, n_modes)` — top-N peaks by `scipy.signal.find_peaks` prominence; falls back to evenly spaced frequencies.
- `poles_from_estimates(fn_hz, xi)` — converts fn (Hz) and ξ arrays to continuous-time complex poles `s = −ξωₙ + jωd`.
- `plscf_poles(H, freqs, n_order)` — pLSCF for one model order; real-valued normal equations, monic denominator, `numpy.roots`, `s = log(z)/Δt`; returns physical poles only.
- `era_poles(H, freqs, n_order, fs)` — ERA for one model order; IRF via `irfft`, block Hankel, SVD, state-space eigendecomposition; returns `(poles, mode_shapes)`.
- `build_stability_table(H, freqs, fs, max_order, method, df_thr, dd_thr, mac_thr)` — sweeps orders 2..max_order step 2; classifies each pole as `new` / `stable_f` / `stable_fd` / `stable_all`; returns list of dicts.
- `extract_residues(H, freqs, poles)` — complex LS fit of partial-fraction basis to H; returns `(n_outputs, n_modes)` complex residues.
- `synthesize_frf(freqs, poles, residues)` — partial-fraction sum; returns `(n_freqs, n_outputs)` complex.
- `modal_fit_nmse(H_measured, H_syn)` — NMSE per output channel in dB (lower = better).

#### `core/mimo.py`
- `compute_mimo_cmif(H, n_out)` — SVD per frequency line of the (n_out × 2) MIMO FRF slice; returns `(n_freqs, 2)` singular values σ₁, σ₂.
- `compute_mimo_frfs(run_a_proc, run_b_proc, input_a, input_b, sel_outputs, fs, frf_method, frf_est, n_seg, ovlp_pct, welch_win)` — assembles the stacked MIMO FRF matrix from two processed runs; returns `(H_stacked, freqs_full)` where `H_stacked` is `(n_freqs, n_out * 2)`.

#### `core/plots.py`
- `fft_subplot(df_proc, channels, fs, fmax)` — returns a stacked Plotly figure of magnitude FFT (dB) for each channel.
- `frf_subplot(df_proc, input_ch, output_chs, fs, fmax)` — returns a stacked magnitude + phase FRF figure (H1 estimator, single FFT) for each output channel.

### Input data format

CSV files must have one time column (`time`, `Time`, `TIME`, `t`, or `T` — or a numeric monotonically increasing first column) plus one or more channel columns. Multiple CSVs can be uploaded simultaneously and are merged on the `time` column (inner join). Sample data: `data/input/sample_3ch.csv`.

Analysis logs are written as JSON to `data/output/<analysis_name>_log.json`.

### Page details

Full UI spec, controls, algorithms, and session state per page are in `modal_analysis.md`. Worked signal-processing examples with runnable code are in `analysis_method.ipynb`.

### Wireframe geometry (page 7 — stub)

The planned wireframe page will parse NASTRAN BDF-format ASCII files containing `GRID` (point geometry in global coordinate system CP 0) and `PLOTEL` (two-point connectivity) cards to drive a 3-D Plotly visualisation of mode shapes.
