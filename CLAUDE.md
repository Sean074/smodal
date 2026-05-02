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
| `pages/5_MIMO.py` | MIMO EMA — multi-reference pLSCF (PolyMAX), inline pre-processing | Implemented |
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
| `processed_df` | `1_Time_History.py` | `2_FFT.py`, `3_Spectral_Analysis.py` |
| `processing_info` | `1_Time_History.py` | `2_FFT.py` (display label) |
| `fft_results` | `2_FFT.py` | `3_Spectral_Analysis.py` |
| `spectral_results` | `3_Spectral_Analysis.py` | `3_Spectral_Analysis.py` (cached), `4_SIMO.py` |
| `si_stability_table` | `4_SIMO.py` (Build) | `4_SIMO.py` (Step 2, Stability tab) |
| `si_cmif` | `4_SIMO.py` (Build) | `4_SIMO.py` (Stability tab bg, CMIF tab) |
| `si_H_mat` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_freqs_band` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
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

#### `core/sysid.py`
- `compute_cmif(H)` — `np.linalg.norm(H, axis=1)`; Euclidean norm per frequency line (equivalent to first singular value of a row vector).
- `compute_mimo_cmif(H, n_out)` — SVD per frequency line of the (n_out × 2) MIMO FRF slice; returns `(n_freqs, 2)` singular values σ₁, σ₂.
- `cmif_peak_estimates(cmif, freqs, n_modes)` — top-N peaks by `scipy.signal.find_peaks` prominence; falls back to evenly spaced frequencies.
- `poles_from_estimates(fn_hz, xi)` — converts fn (Hz) and ξ arrays to continuous-time complex poles `s = −ξωₙ + jωd`.
- `plscf_poles(H, freqs, n_order)` — pLSCF for one model order; real-valued normal equations, monic denominator, `numpy.roots`, `s = log(z)/Δt`; returns physical poles only.
- `era_poles(H, freqs, n_order, fs)` — ERA for one model order; IRF via `irfft`, block Hankel, SVD, state-space eigendecomposition; returns `(poles, mode_shapes)`.
- `build_stability_table(H, freqs, fs, max_order, method, df_thr, dd_thr, mac_thr)` — sweeps orders 2..max_order step 2; classifies each pole as `new` / `stable_f` / `stable_fd` / `stable_all`; returns list of dicts.
- `extract_residues(H, freqs, poles)` — complex LS fit of partial-fraction basis to H; returns `(n_outputs, n_modes)` complex residues.
- `synthesize_frf(freqs, poles, residues)` — partial-fraction sum; returns `(n_freqs, n_outputs)` complex.
- `modal_fit_nmse(H_measured, H_syn)` — NMSE per output channel in dB (lower = better).

#### `core/spectral.py`
- `compute_fft(signal, sample_rate, window)` — applies a scipy window and returns `(freqs_hz, fft_complex)` via `np.fft.rfft`.
- `compute_spectral_quantities(Sx, Sy)` — computes single-realisation spectral quantities from complex FFT arrays; returns dict with `Gxx`, `Gyy`, `Gyx`, `Gxy`, `H1`, `H2`, `Hv`, `gamma2`.
- `compute_welch_quantities(x, y, sample_rate, nperseg, noverlap, window)` — Welch-averaged spectral quantities using `scipy.signal.welch` and `csd`; returns the same keys as above plus `freqs`.

Windows supported by `compute_fft`: `uniform` (boxcar), `hanning`, `flattop`, `force` (hann), `exponential`.
Windows supported by `compute_welch_quantities`: any scipy window name (typically `hann`, `flattop`, `boxcar`).

### Input data format

CSV files must have one time column (`time`, `Time`, `TIME`, `t`, or `T` — or a numeric monotonically increasing first column) plus one or more channel columns. Multiple CSVs can be uploaded simultaneously and are merged on the `time` column (inner join). Sample data: `data/input/sample_3ch.csv`.

Analysis logs are written as JSON to `data/output/<analysis_name>_log.json`.

### Page details

#### Page 1 — Time History
- Butterworth filter (lowpass, highpass, bandpass, bandstop) via `scipy.signal.butter` / `sosfiltfilt`.
- Time range slider trims the display window.
- Stacked subplots (one per channel) or overlaid single plot.
- Raw and filtered traces plotted together (filtered in red dashed).
- Persists trimmed + filtered data as `processed_df` and filter metadata as `processing_info` for downstream pages.
- Channel stats table (min, max, mean, RMS, std dev) in an expander.

#### Page 2 — FFT
- Data source toggle: raw full dataset or processed data from Time History page.
- Window selection: uniform, Hanning, Flat Top, Force, Exponential.
- Display mode: Gain/Phase or Real/Imaginary.
- Log Y toggle for gain axis.
- "Compute & Save FFT" button stores results in `fft_results` for use by Spectral Analysis.
- Auto-plots using cached FFT if settings match; recomputes on-the-fly otherwise.

#### Page 3 — Spectral Analysis
- **Method** radio: Single FFT (requires `fft_results`) or Welch (reads directly from `processed_df` / `df`).
- Two-column layout: controls (left narrow) + charts (right wide).
- Welch controls: Segments (4/8/16/32/64), Overlap % (0/25/50/75), Window (hann/flattop/boxcar), plus Δf caption.
- **Five tabs:** Auto-Power (dB), PSD (unit²/Hz or dB, linear/log toggle), Cross-Power (magnitude + phase), FRF (H1/H2/Hv/All selector), Coherence.
- Frequency range slider scoped to chart area.
- Results cached in `spectral_results`; only recomputes when params change.
- PSD tab: normalised one-sided PSD — Welch uses `scipy.signal.welch` directly; Single FFT uses `PSD = 2·|FFT|²/(fs·N)`.
- Coherence tab: γ²=0.85 reference line; caption adapts to method (Welch gives meaningful coherence, Single FFT always yields γ²=1).

#### Page 4 — System Identification (SIMO EMA)
- Requires `spectral_results` from Page 3; guards against missing data.
- Two-column layout (1:3): controls left, charts right.
- **Step 1** — select method (pLSCF/ERA), FRF estimator, output channels, frequency range, max model order, stability thresholds; click **Build Stability Diagram**.
- **Step 2** — n_modes (auto from green pole count), editable estimates table (fn Hz, ξ %, source); click **Extract Mode Shapes**.
- Build stores `si_stability_table`, `si_cmif`, `si_H_mat`, `si_freqs_band`, `si_sel_outputs`, `si_frf_est_used` in session state and clears any previous `modal_results`.
- Extract stores `modal_results` (fn, xi, poles, mode_shapes, output_channels, freqs, H_measured, H_synthesis, nmse).
- Four tabs: **CMIF** (log-scale, live from selected channels), **Stability Diagram** (scatter per class + CMIF background), **Mode Shapes** (summary table + stacked FRF overlays with optional modal contributions, NMSE per subplot), **Export** (downloadable CSV).

#### Page 5 — MIMO EMA
- Loads Run A (in-phase) and Run B (out-of-phase) CSVs independently via file uploaders on the page — does not use landing-page session data.
- Sample rate derived from Run A time column.
- Channel assignment: separate input-channel selectboxes for Run A and Run B; shared output multiselect.
- Three optional pre-processing expanders (all use the same trim + filter settings):
  1. **Time history / filter** — time range slider, Butterworth filter controls, optional time history preview (Run A blue, Run B orange; filtered as dashed overlays).
  2. **FFT preview** — two-column layout (Run A | Run B); input + each output channel FFT (dB, uniform window) stacked vertically; max-frequency slider.
  3. **FRF preview** — two-column layout (Run A | Run B); magnitude (dB) + phase (°) per input/output pair stacked vertically; H1, single FFT; max-frequency slider.
- **Step 1**: FRF method (Welch/Single FFT), FRF estimator (H1/H2/Hv), Welch controls, frequency range, max model order, stability thresholds → **Build Stability Diagram**.
  - FRFs computed independently per run using the chosen SIMO estimator, then column-stacked: `H_stacked = [H_A | H_B]` shape `(n_freqs, n_out × 2)`.
  - pLSCF sweep over stacked matrix; CMIF via SVD of per-frequency `(n_out × 2)` slice.
- **Step 2**: n_modes (auto from green pole count), editable estimates table → **Extract Mode Shapes**.
  - Residues reshaped to `(n_out, 2, n_modes)`; per mode, ‖Run A‖ vs ‖Run B‖ norm determines S/A type label.
  - FRF synthesis and NMSE over full `(n_freqs, n_out × 2)` matrix.
- Four tabs: **CMIF** (σ₁/σ₂ log-scale), **Stability Diagram** (same four-class scatter + σ₁ background), **Mode Shapes** (summary table + 4-row subplots per channel: Run A mag/phase, Run B mag/phase, with optional modal contributions and NMSE annotation), **Export** (downloadable CSV, stores `mimo_modal_results`).

### Spectral analysis formulas (page 3)

System model: `x(t) → h(t) → y(t)`

- Input auto-power: `Gxx = Sx · Sx*`
- Output auto-power: `Gyy = Sy · Sy*`
- Cross-power: `Gyx = Sy · Sx*`, `Gxy = Sx · Sy*`
- FRF estimators: `H1 = Gyx / Gxx`, `H2 = Gyy / Gxy`, `Hv` = geometric mean magnitude with H1 phase
- Coherence: `γ² = |Gyx|² / (Gxx · Gyy)`

### Wireframe geometry (page 7 — stub)

The planned wireframe page will parse NASTRAN BDF-format ASCII files containing `GRID` (point geometry in global coordinate system CP 0) and `PLOTEL` (two-point connectivity) cards to drive a 3-D Plotly visualisation of mode shapes.
