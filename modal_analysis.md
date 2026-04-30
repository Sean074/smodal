# MODAL ANALYSIS PROGRAM — SYSTEM IDENTIFICATION

## Pages

| # | Page | Status |
|---|---|---|
| — | Landing Page | Implemented |
| 1 | Time History | Implemented |
| 2 | FFT | Implemented |
| 3 | Spectral Analysis | Implemented |
| 4 | Operational Modal Analysis (OMA) | Stub |
| 5 | Integration / Differentiation | Stub |
| 6 | Modal Assurance Criteria (MAC) | Stub |
| 7 | Wireframe Mode Shape | Stub |

---

## Landing Page — Data Load and Channel Assignment

User information inputs:
- Analysis Name
- Analyst Name
- Analysis Description

User selects data to load:
- One or more CSV files via file uploader.
- Multiple files are merged on the shared `time` column (inner join).

Channel assignment:
- Dropdown to select the **input channel** (force / excitation).
- Multiselect to choose **output channels** (accelerometers / responses).

Data summary table (shown after channels are assigned):
- Per channel: samples, sample rate (Hz), duration (s), min/max time, min/max value, RMS.

Analysis log:
- User can add a text comment.
- "Save Analysis Log" writes a JSON file to `data/output/<name>_log.json` containing date, analysis name, analyst, description, comment, and the data summary.

---

## Page 1 — Time History

Stacked strip charts (one subplot per channel, top to bottom) or overlaid on a single axes — toggled by "Stacked subplots" switch.

Controls:
- **Channels to plot** multiselect.
- **Time range** slider trims the window shown (and the data passed downstream).
- **Filter type**: None, Lowpass, Highpass, Bandpass, Bandstop (Butterworth via `scipy.signal.butter` / `sosfiltfilt`).
  - Filter order slider (1–8).
  - Single cutoff frequency input for lowpass/highpass.
  - Separate low and high cutoff inputs for bandpass/bandstop.

Plot:
- Raw signal plotted in colour per channel.
- Filtered signal overlaid in red dashed when a filter is active.

Channel statistics expander (visible time window):
- Min, Max, Mean, RMS, Std Dev, Samples — per selected channel.

Downstream handoff:
- `processed_df` — DataFrame of the trimmed (and optionally filtered) signals, stored in session state for use by FFT and Spectral Analysis pages.
- `processing_info` — dict with trim range, filter type, order, cutoff frequencies.

---

## Page 2 — FFT (Fast Fourier Transform)

Data source toggle (if Time History has been visited):
- Raw (full dataset) or Time History processed data (trim + filter already applied).

Controls:
- **Channels** multiselect (defaults to input + output channels).
- **Window**: Uniform (no window), Hanning, Flat Top, Force, Exponential.
- **Display mode**: Gain/Phase or Real/Imaginary.
- **Log Y** checkbox (applies to gain/real axis).
- **Frequency range** slider.
- **Compute & Save FFT** button — stores result in `fft_results` session state for the Spectral Analysis page.

Plot layout:
- Two rows per channel (top = gain or real, bottom = phase or imaginary), shared x-axis.

---

## Page 3 — Spectral Analysis

Two-column layout: narrow controls on the left, charts on the right.

Controls:
- **Method** radio: Single FFT or Welch.
  - *Single FFT*: requires `fft_results` from the FFT page (input + output channels must be included).
  - *Welch*: reads directly from processed (or raw) data; no FFT page visit required.
- **Output channels** multiselect.
- Welch-only controls:
  - **Segments** select-slider (4 / 8 / 16 / 32 / 64, default 8).
  - **Overlap (%)** select-slider (0 / 25 / 50 / 75, default 50).
  - **Window** selectbox: hann, flattop, boxcar.
  - Caption showing Δf and samples-per-segment.
- **Compute** button — runs spectral calculations and caches in `spectral_results`.
- **Frequency range** slider (inside chart column).

Four tabs:

### Auto-Power
- `Gxx` (input) and `Gyy` (each output) plotted in dB (10 log₁₀).
- Stacked subplots, shared x-axis.

### PSD
- One-sided Power Spectral Density for input (`Sxx`) and each output channel (`Syy`), stacked subplots with shared x-axis.
- PSD is normalised by frequency resolution so units are (measurement unit)²/Hz:  - *Welch*: `scipy.signal.welch` already returns a properly normalised one-sided PSD.
- *Single FFT*: `PSD = 2 · |FFT|² / (fs · N)` (factor of 2 for one-sided, divided by window energy `fs · N`).
- Y-axis display toggle: linear (unit)²/Hz or dB (10 log₁₀ of the PSD).- Δf annotation per subplot caption so the analyst can confirm frequency resolution.

### Cross-Power
- `|Gyx|` in dB and `∠Gyx` in degrees, two rows per output channel.

### FRF
- Estimator selector: H1, H2, Hv, All.
  - H1 = Gyx / Gxx (minimises output noise)
  - H2 = Gyy / Gxy (minimises input noise)
  - Hv = geometric mean of |H1|·|H2|, phase from H1
- Magnitude in dB (20 log₁₀) and phase in degrees; two rows per output channel.
- When "All" is selected, H1/H2/Hv are overlaid with solid/dash/dot line styles.

### Coherence
- Ordinary coherence γ² = |Gyx|² / (Gxx · Gyy), plotted 0–1.
- Reference line at γ² = 0.85.
- Single FFT note: γ² = 1 is always expected; multiple segments required for meaningful values.
- Welch note: values below 0.85 indicate noise or nonlinearity.

---

## Page 4 — Operational Modal Analysis (stub)

OMA / Stability Diagram — not yet implemented.

Planned: automated pole extraction, stability diagram, mode identification.

---

## Page 5 — Integration / Differentiation (stub)

Signal integration and differentiation — not yet implemented.

Planned: convert between acceleration, velocity, and displacement domains.

---

## Page 6 — Modal Assurance Criteria (stub)

MAC plot — not yet implemented.

Planned: compute and display MAC matrix between identified mode shapes.

---

## Page 7 — Wireframe Mode Shape (stub)

3-D mode shape visualisation — not yet implemented.

Planned implementation:
- User selects an ASCII text file in NASTRAN BDF format.
- Parser reads `GRID` cards (x, y, z geometry in global coordinate system CP 0) and `PLOTEL` cards (EID, G1, G2 connectivity).
- 3-D Plotly figure plots grid points and wireframe connections.
- Mode shape animation overlaid on the undeflected geometry.

---

## Spectral Analysis Formulas

System model: `x(t) → h(t) → y(t)`

| Quantity | Formula |
|---|---|
| Input auto-power | `Gxx = Sx · Sx*` |
| Output auto-power | `Gyy = Sy · Sy*` |
| Cross-power (output→input) | `Gyx = Sy · Sx*` |
| Cross-power (input→output) | `Gxy = Sx · Sy*` |
| H1 estimator | `H1 = Gyx / Gxx` |
| H2 estimator | `H2 = Gyy / Gxy` |
| Hv estimator | `|Hv| = √(|H1|·|H2|)`, phase = ∠H1 |
| Coherence | `γ² = \|Gyx\|² / (Gxx · Gyy)` |

---

## Input Data Format

CSV with one time column and one or more data channel columns.

Time column name detection order: `time`, `Time`, `TIME`, `t`, `T`, or a numeric monotonically increasing first column (renamed to `time`).

Multiple files may be uploaded and are merged on the `time` column (inner join).

Sample data: `data/input/sample_3ch.csv`
