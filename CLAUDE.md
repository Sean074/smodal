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
| `pages/3_Spectral_Analysis.py` | Auto/cross power, coherence, FRF (H1, H2, Hv) — tabbed layout | Implemented |
| `pages/4_OMA.py` | Operational Modal Analysis / Stability Diagram | Stub |
| `pages/5_Integration.py` | Signal integration / differentiation | Stub |
| `pages/6_MAC.py` | Modal Assurance Criteria plot | Stub |
| `pages/7_Wireframe.py` | 3-D wireframe mode shape visualisation | Stub |

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
| `spectral_results` | `3_Spectral_Analysis.py` | `3_Spectral_Analysis.py` (cached) |
| `modal_results` | `4_OMA.py` | `6_MAC.py`, `7_Wireframe.py` |

Every page (except `7_Wireframe.py`) guards against missing data with:
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
- Four tabs: Auto-Power (dB), Cross-Power (magnitude + phase), FRF (H1/H2/Hv/All selector), Coherence.
- Frequency range slider scoped to chart area.
- Results cached in `spectral_results`; only recomputes when params change.
- Coherence tab: γ²=0.85 reference line; caption adapts to method (Welch gives meaningful coherence, Single FFT always yields γ²=1).

### Spectral analysis formulas (page 3)

System model: `x(t) → h(t) → y(t)`

- Input auto-power: `Gxx = Sx · Sx*`
- Output auto-power: `Gyy = Sy · Sy*`
- Cross-power: `Gyx = Sy · Sx*`, `Gxy = Sx · Sy*`
- FRF estimators: `H1 = Gyx / Gxx`, `H2 = Gyy / Gxy`, `Hv` = geometric mean magnitude with H1 phase
- Coherence: `γ² = |Gyx|² / (Gxx · Gyy)`

### Wireframe geometry (page 7 — stub)

The planned wireframe page will parse NASTRAN BDF-format ASCII files containing `GRID` (point geometry in global coordinate system CP 0) and `PLOTEL` (two-point connectivity) cards to drive a 3-D Plotly visualisation of mode shapes.
