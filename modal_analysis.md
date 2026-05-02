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

## Page 4 — System Identification (SIMO EMA)

Single-Input Multiple-Output Experimental Modal Analysis using FRFs from Page 3.

Two-column layout: narrow controls left, charts right.

### Data requirements
- `spectral_results` from Page 3 (must contain H1/H2/Hv for all output channels).

### Controls

**Step 1 — Stability Diagram**
- **Curve fitting method** radio: pLSCF / ERA.
- **FRF estimator** radio: H1 / H2 / Hv (default H1).
- **Output channels** multiselect.
- **Frequency range** slider (analysis band).
- **Max model order** slider (4–100, step 2, default 40).
- **Stability thresholds** expander: Δf (%), Δξ (%), MAC threshold.
- **Build Stability Diagram** button.

**Step 2 — Mode Specification**
- **Number of modes** integer input (auto-populated from green stable pole count).
- **Mode initial estimates** editable table — one row per mode: fn (Hz), ξ (%).
  Pre-populated from selected green poles; falls back to top-N CMIF peaks
  (`scipy.signal.find_peaks`) if no poles selected. User can override any value.
- **Extract Mode Shapes** button.

### Four tabs

#### CMIF
- Complex Mode Indicator Function: first singular value of the FRF matrix vs frequency.
- Peaks indicate candidate mode locations.
- Computed via `numpy.linalg.svd`.

#### Stability Diagram
- Model order swept from 2 to N_max (step 2).
- Each pole classified per order relative to previous order:
  - **o** (grey) = new
  - **f** (blue) = frequency stable: |Δfn/fn| < ε_f
  - **d** (orange) = freq + damping stable: above + |Δξ/ξ| < ε_ξ
  - **s** (green) = fully stable: above + MAC > ε_MAC
- CMIF curve shown in background for reference.

#### Mode Shapes
- Summary table: Mode #, fn (Hz), ξ (%) — fitted values from residue extraction.
- Stacked FRF subplots per output channel (magnitude dB + phase °):
  - Measured H1 — solid colour line.
  - Synthesised (predicted) model — dashed red line.
  - Optional: individual modal contributions as thin dotted lines.
- Modal fit quality (NMSE dB) per channel shown as subplot caption.

#### Export
- Identified mode table as downloadable CSV.
- Results stored in `modal_results` session state for Page 6 (MAC) and Page 7 (Wireframe).

### Algorithms

#### Method 1 — pLSCF (default)
- Operates directly on H1 FRFs from Page 3 (no IFFT required).
- z-domain Right Matrix Fraction Description: `H(z) = B(z) · A(z)⁻¹`.
- Denominator polynomial A solved via real-valued normal equations across all output
  channels simultaneously (`numpy.linalg.lstsq`).
- Poles from companion matrix eigenvalues (`numpy.roots`).
- Best choice for EMA with a measured input signal.

#### Method 2 — ERA
- Computes Impulse Response Function via `numpy.fft.irfft(H1)`.
- Builds block Hankel matrix from IRF samples.
- SVD-based state-space realization (`scipy.linalg.svd`, `scipy.linalg.eig`).
- Model order controlled by SVD rank truncation.
- Well suited for extension to OMA (ambient excitation, no measured input).

#### Shared (both methods)
- Residue extraction: partial-fraction model + `numpy.linalg.lstsq`.
- FRF synthesis: vectorised partial-fraction sum (numpy).
- CMIF: `numpy.linalg.svd` of H matrix at each frequency line.
- Physical pole filter: 0 < ξ < 30 %, fn within analysis range.

---

### Known Issues in `core/sysid.py` and `core/spectral.py`

The following bugs were identified by numerical testing against a synthetic 2-DOF system
(modes at 30 Hz / ζ = 3 % and 80 Hz / ζ = 5 %).  All three are interdependent and must be
addressed together.

---

#### Issue 1 — `spectral.py`: Welch FRF has conjugate phase (`compute_welch_quantities`)

**Location:** `core/spectral.py`, line 96.

**Root cause:** `scipy.signal.csd(a, b)` computes `E[a*(f) · b(f)]` (conjugate of the first
argument times the second). The code calls `csd(y, x)`, which therefore returns
`E[Y*(f) · X(f)] = conj(H) · Gxx`, not the intended `E[Y(f) · X*(f)] = H · Gxx`.

**Effect:** The H1 estimator from Welch averaging has the correct magnitude but conjugate
phase (e.g., +90° at resonance instead of the physically correct −90° for a receptance FRF).
This propagates through Pages 1–3 (wrong phase display) and causes complete failure of
residue extraction on Page 4 (NMSE ≈ 0 dB).

**Fix:** Swap arguments: replace `csd(y, x)` with `csd(x, y)`.

---

#### Issue 2 — `sysid.py`: pLSCF z → s mapping has wrong sign (`plscf_poles`)

**Location:** `core/sysid.py`, function `plscf_poles`, line ~112.

**Root cause:** The polynomial basis uses the forward-shift variable
`z_i = exp(+j 2π f_i Δt)`.  The LS fit finds the denominator roots in this basis.  For a
stable (damped) physical pole, the correct z-domain location is *inside* the unit circle
(`|z_k| < 1`).  Applying `s = log(z_k) / Δt` then gives `Re(s_k) < 0` → positive damping
(`ξ_k > 0`) → passes the physical mask correctly.

**What went wrong:** During initial development the FRF passed to pLSCF was `conj(H)` (due
to Issue 1).  The conjugate FRF shifts the polynomial roots to the *reciprocal* locations
(outside the unit circle, `|z_k| > 1`), making `Re(log(z)/Δt) > 0` → `ξ < 0` → filtered
out.  A sign negation `s = −log(z_k) / Δt` was applied as a workaround that happened to
recover the correct poles from `conj(H)`.

**Current state (after both Issue 1 fix and sign negation):** The FRF is now correct (`H`,
not `conj(H)`), so the sign negation is no longer appropriate.  The combined effect is that
pLSCF again finds no physical poles — this time because the minus sign pushes the correctly
located roots to the wrong half-plane.

**Fix (pending):** Revert `plscf_poles` to `s = +log(z_k) / Δt` now that Issue 1 is
corrected.  The physical mask (`Im(s) > 0`, `ξ > 0`, `fn` in band) should then pass the
correct poles without modification.

---

#### Issue 3 — `sysid.py`: `extract_residues` forces real residues

**Location:** `core/sysid.py`, function `extract_residues`, lines ~289–295.

**Root cause:** The code stacks the real and imaginary parts of the basis matrix Φ into a
real-valued system `[Re(Φ); Im(Φ)] · r = [Re(H); Im(H)]` and solves for a *real* vector
`r`.  This implicitly constrains all residues to be real scalars, i.e., it forces all mode
shapes to be in-phase (purely real).

**Effect:** Complex mode-shape residues (which encode both amplitude and relative phase at
each sensor) cannot be represented.  The synthesised FRF magnitude is typically 10–100×
smaller than measured, and NMSE ≈ 0 dB (effectively no fit).  This applies even when the
exact pole locations are known.

**Fix:** Replace the stacked real LS with a complex LS solve directly:
`np.linalg.lstsq(Phi, H)` where `Phi` and `H` are complex-valued.  This returns complex
residues that correctly encode amplitude and phase.

---

#### Summary of recommended corrections (in order)

| Step | File | Change | Depends on |
|------|------|---------|------------|
| 1 | `core/spectral.py` | `csd(y, x)` → `csd(x, y)` | — |
| 2 | `core/sysid.py` | Revert `plscf_poles` to `+log(z)/Δt` | Step 1 |
| 3 | `core/sysid.py` | Replace real LS in `extract_residues` with complex LS | Step 1 |

All three steps have been applied.

### Session state
| Key | Set by | Consumed by |
|-----|--------|-------------|
| `modal_results` | `4_OMA.py` | `6_MAC.py`, `7_Wireframe.py` |

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
