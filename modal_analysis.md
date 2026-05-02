# MODAL ANALYSIS PROGRAM — SYSTEM IDENTIFICATION

## Pages

| # | Page | Status |
|---|---|---|
| — | Landing Page | Implemented |
| 1 | Time History | Implemented |
| 2 | FFT | Implemented |
| 3 | Spectral Analysis | Implemented |
| 4 | System Identification (SIMO EMA) | Implemented |
| 5 | MIMO EMA (Multi-Reference System Identification) | Implemented |
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

Two-column layout (1:3 ratio): narrow controls left, charts right.

### Data requirements
- `spectral_results` from Page 3 (must contain H1/H2/Hv for all output channels).

### Controls

**Step 1 — Stability Diagram**
- **Curve fitting method** radio: pLSCF / ERA.
- **FRF estimator** radio: H1 / H2 / Hv (default H1).
- **Output channels** multiselect (defaults to all available from `spectral_results`).
- **Frequency range** slider (analysis band, 0 Hz to Nyquist).
- **Max model order** slider (4–100, step 2, default 40).
- **Stability thresholds** expander: Δf (%), Δξ (%), MAC threshold.
- **Build Stability Diagram** button — sweeps orders 2..N_max and stores results in session state.

**Step 2 — Mode Specification**
- **Number of modes** integer input (1–20; auto-populated from count of deduplicated green stable poles).
- **Mode initial estimates** editable data_editor table — one row per mode: fn (Hz), ξ (%), source (read-only).
  - Pre-populated from green stable poles (deduplicated at 1 % frequency tolerance), sorted by fn.
  - Falls back to top-N CMIF peaks (`scipy.signal.find_peaks` by prominence) if poles are insufficient.
  - Falls back to manual zero-rows if no CMIF is available.
  - User can override fn and ξ values.
- **Extract Mode Shapes** button — converts table estimates to complex poles and runs residue extraction.

### Four tabs

#### CMIF
- Complex Mode Indicator Function computed live from the selected channels and FRF estimator.
- Plotted on a log y-axis vs frequency (Hz).
- Peaks indicate candidate mode locations.
- Implementation: `np.linalg.norm(H, axis=1)` (Euclidean norm per frequency line, equivalent to first singular value of a row vector).

#### Stability Diagram
- Model order swept from 2 to N_max (step 2); each order compared to the previous.
- Pole stability classification:
  - **open circle / grey** = new (no match in previous order)
  - **cross / blue** = frequency stable: `|Δfn/fn| < ε_f`
  - **x / orange** = freq + damping stable: above + `|Δξ/ξ| < ε_ξ`
  - **star / green** = fully stable: above + MAC ≥ ε_MAC
- Normalised CMIF curve shown in background for reference (scaled to fit model-order axis).

#### Mode Shapes
- Summary table: Mode #, fn (Hz), ξ (%), |φ| and ∠φ (°) per output channel.
- Stacked FRF subplots per output channel — 2 rows each (magnitude dB, phase °), shared x-axis:
  - Measured — solid colour line.
  - Synthesised — dashed red line.
  - Optional individual modal contributions — thin dotted lines (toggled by checkbox).
- NMSE (dB) per channel appended to the subplot title annotation.

#### Export
- Table of identified modes (mode #, fn Hz, ξ %, amplitude and phase per channel) shown and available as downloadable CSV named `<analysis_name>_modal_results.csv`.
- Results stored in `modal_results` session state for Page 6 (MAC) and Page 7 (Wireframe).

### Algorithms

#### Method 1 — pLSCF (default)
- Operates directly on FRFs from Page 3 (no IFFT required).
- z-domain Right Matrix Fraction Description: `H(z) = B(z) · A(z)⁻¹`.
- Basis variable: `z_i = exp(+j 2π f_i Δt)` where `Δt = 1 / (2 · f_max)`.
- Real-valued normal equations across all output channels simultaneously (`numpy.linalg.lstsq`).
- Monic denominator: α₀ = 1; solves for α₁…αₙ.
- Poles from `numpy.roots` applied to denominator polynomial in descending order.
- z → s mapping: `s = log(z) / Δt`.
- Best choice for EMA with a measured input signal.

#### Method 2 — ERA
- Computes Impulse Response Function via `numpy.fft.irfft(H)` for each output channel.
- Builds block Hankel matrices H₀ (offset 0) and H₁ (offset 1), size `(n_out·r) × s`.
- SVD of H₀ (`scipy.linalg.svd`), rank-truncated to `n_order`.
- State-space realisation: `A_sys = S⁻½ Uᵣᵀ H₁ Vᵣ S⁻½`.
- Eigendecomposition of A_sys (`scipy.linalg.eig`); z → s via `log(λ)/Δt`.
- Mode shapes extracted directly from observability matrix: `C_obs @ evecs`.
- Well suited for extension to OMA (ambient excitation, no measured input).

#### Shared (both methods)
- **Physical pole filter:** `Im(s) > 0`, `0 < ξ < 30 %`, `fn` within analysis frequency range.
- **MAC for stability:** computed on mode-shape vectors from consecutive orders; pLSCF uses a quick residue extraction per order, ERA uses observability-matrix mode shapes.
- **Residue extraction:** complex least-squares `np.linalg.lstsq(Φ, H)` where `Φ[i,k] = 1/(jωᵢ − sₖ) + 1/(jωᵢ − sₖ*)` — returns complex residues encoding amplitude and phase.
- **FRF synthesis:** vectorised partial-fraction sum: `H_syn = Φ @ residues.T`.
- **NMSE:** `10 log₁₀(‖H_meas − H_syn‖² / ‖H_meas‖²)` per output channel (dB); lower = better fit.

### Session state
| Key | Set by | Consumed by |
|-----|--------|-------------|
| `si_stability_table` | `4_SIMO.py` (Build) | `4_SIMO.py` (Step 2, Stability tab) |
| `si_cmif` | `4_SIMO.py` (Build) | `4_SIMO.py` (Stability tab background, CMIF tab) |
| `si_H_mat` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_freqs_band` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_sel_outputs` | `4_SIMO.py` (Build) | `4_SIMO.py` (Extract) |
| `si_frf_est_used` | `4_SIMO.py` (Build) | `4_SIMO.py` (reference) |
| `modal_results` | `4_SIMO.py` (Extract) | `6_MAC.py`, `7_Wireframe.py` |

---

## Page 5 — MIMO EMA (Multi-Reference System Identification)

Multiple-Input Multiple-Output Experimental Modal Analysis using two simultaneous-shaker sine excitation patterns (in-phase and 180° out-of-phase). Assumes symmetric input placement and a near-symmetric structure.

Two-column layout (1:3 ratio): narrow controls left, charts right.

---

### Test background

#### Shaker placement

- Place shakers at locations with sufficient modal participation — avoid nodal points for the target modes.
- Shaker positions must be **linearly independent** with respect to the target mode shapes (i.e., the two input locations must not simultaneously be nodes of the same mode).
- Stinger rods must be used between the shaker and the structure to isolate the shaker mass and ensure predominantly axial force transmission.
- Attach force transducers (load cells) directly at the structure–stinger interface. Impedance head sensors (combined force + acceleration) are preferred at each drive point.

#### Phase conditions — the two runs

| Run | Shaker 1 phase | Shaker 2 phase | Excites |
|---|---|---|---|
| **Run A — Symmetric** | 0° | 0° | Symmetric (in-phase) mode families |
| **Run B — Asymmetric** | 0° | 180° | Antisymmetric (out-of-phase) mode families |

Two sweeps with different phase relationships between the shakers provide the minimum required number of independent excitation vectors to compute the full 2-column MIMO FRF matrix.

#### Swept sine parameters

| Parameter | Typical value | Notes |
|---|---|---|
| Sweep type | Linear or logarithmic | Log sweep preferred for lightly damped structures |
| Sweep rate | ≤ (ξ·fₙ)² / 2 Hz/s per mode | Must be slow enough for each mode to reach steady state |
| Frequency range | Cover all target modes + 10% margin | e.g. 1–200 Hz |
| Force level | Set per pre-test linearity check | Constant-force control preferred over constant-voltage |

#### Pre-test quality checks

| Check | Method | Pass criterion |
|---|---|---|
| **Linearity** | Repeat at 50% and 100% drive level; compare FRFs | Magnitude within ±1 dB |
| **Reciprocity** | Compare H(i→j) vs H(j→i) | Magnitude ±1 dB, phase ±5° |
| **Drive-point positivity** | Real part of H at drive-point location | Must be ≥ 0 at all frequencies |
| **Coherence** | Multiple coherence per output | γ² ≥ 0.9 in the analysis band |

#### FRF matrix quality checks

| Check | Target |
|---|---|
| Multiple coherence per output channel | ≥ 0.9 in analysis band |
| Gxx condition number (per frequency line) | < 100 (> 100 = runs are insufficiently independent) |
| Drive-point FRF real part | Positive at all frequencies |
| CMIF rank — σ₁/σ₂ ratio at resonance | Both singular values should peak at distinct modal frequencies |

Multiple coherence for output channel _k_:

```
γ²_multiple[k] = (H[k,:] · Gxx · H[k,:].conj().T) / Gyy[k,k]
```

---

### Data requirements
- Two CSV files loaded directly on this page (independent of the landing page):
  - **Run A** — in-phase excitation: all shakers driven at 0° relative phase.
  - **Run B** — out-of-phase excitation: shakers driven at 0° and 180° relative phase.
- Each CSV must contain at least one force (input) channel and one or more acceleration (output) channels.
- Both runs must share the same output channel names and sample rate.

### Channel assignment
- **Run A input channel** — force reference for the in-phase run.
- **Run B input channel** — force reference for the out-of-phase run.
- **Output channels** multiselect — channels present in both runs.

### Pre-processing expanders (optional, applied identically to both runs)

#### Time history / filter expander
- **Time range** slider — trims both runs to the same window.
- **Filter type** radio: None / Lowpass / Highpass / Bandpass / Bandstop (Butterworth).
  - Filter order slider (1–8).
  - Single cutoff for Lowpass/Highpass; separate low/high cutoffs for Bandpass/Bandstop.
- Caption shows time window, approximate sample count, and active filter.
- **Show time history preview** checkbox (default on) — stacked subplots of the trimmed time window:
  - **Channels to preview** multiselect (defaults to first 4 common channels).
  - Run A plotted in blue (solid); Run B in orange (solid).
  - When a filter is active, filtered traces overlaid as dashed lines (Run A dashed blue, Run B dashed orange).
  - Shared x-axis; 200 px height per subplot row.

#### FFT preview expander
- **Max frequency** slider for display range.
- Two-column layout: **Run A** (left) | **Run B** (right).
- Each column: input channel FFT followed by each output channel FFT stacked vertically (shared x-axis).
- Magnitude plotted in dB (20 log₁₀|FFT|); uniform (rectangular) window, single FFT of the trimmed/filtered signal.

#### FRF preview expander
- **Max frequency** slider for display range.
- Two-column layout: **Run A** (left) | **Run B** (right).
- Each column: for each input/output pair, magnitude (dB) and phase (°) stacked vertically (shared x-axis).
- Uses H1 estimator from single FFT of the trimmed/filtered signals.

### Controls

**Step 1 — Stability Diagram**
- **FRF method** radio: Welch / Single FFT (consistent with Page 3 options).
- **Welch controls** (if selected): Segments (4/8/16/32/64), Overlap % (0/25/50/75), Window (hann/flattop/boxcar).
- **FRF estimator** radio: H1 / H2 / Hv (applied independently to each run before stacking).
- **Frequency range** slider.
- **Max model order** slider (4–100, step 2, default 40).
- **Stability thresholds** expander: Δf (%), Δξ (%), MAC threshold.
- **Build Stability Diagram** button.

**Step 2 — Mode Specification**
- **Number of modes** integer input (auto-populated from count of deduplicated green stable poles).
- **Mode initial estimates** editable table — fn (Hz), ξ (%), source (read-only).
  - Pre-populated from green stable poles (1 % frequency tolerance), sorted by fn.
  - Falls back to SVD-CMIF σ₁ peaks if poles are insufficient.
- **Extract Mode Shapes** button.

### Four tabs

#### CMIF
- SVD-based Complex Mode Indicator Function computed from the stacked MIMO FRF matrix.
- Both singular value curves (σ₁ ≥ σ₂) plotted on log y-axis vs frequency.
  - σ₁: all modes visible; σ₂: resolves repeated / closely-spaced modes.
- Peaks from σ₁ used for initial mode frequency estimates.

#### Stability Diagram
- Same four-class pole classification as Page 4 (new / freq-stable / freq+damp-stable / fully-stable).
- MIMO FRF matrix reshaped to (n_freqs, n_out × 2) before sweep; reuses `build_stability_table`.
- SVD-CMIF σ₁ curve shown in background for reference.

#### Mode Shapes
- Summary table: Mode #, fn (Hz), ξ (%), type (S/A), |φ| and ∠φ (°) per output per reference (columns labelled `A·<ch>` and `B·<ch>`).
- Mode type: if ‖Run A residues‖ ≥ ‖Run B residues‖ → Symmetric (S); otherwise Antisymmetric (A).
- Per-channel plot selector multiselect (defaults to first 4 channels).
- 4 subplot rows per selected channel (Run A magnitude dB, Run A phase °, Run B magnitude dB, Run B phase °), shared x-axis:
  - Measured — solid colour line.
  - Synthesised — dashed red line.
  - Optional individual modal contributions — thin dotted lines (toggled by checkbox).
- NMSE (dB) annotated on each magnitude subplot title.

#### Export
- Table of identified modes (fn, ξ, type, amplitude and phase per output per reference) downloadable as `<analysis_name>_mimo_results.csv`.
- Results stored in `mimo_modal_results` session state for Page 6 (MAC) and Page 7 (Wireframe).

### Algorithm — Multi-reference pLSCF (PolyMAX)

#### FRF matrix construction
- Run A FRFs: H_A(ω) shape (n_freqs, n_out) — computed per-output using the selected estimator (H1/H2/Hv) with the Run A input channel as reference.
- Run B FRFs: H_B(ω) shape (n_freqs, n_out) — same approach using the Run B input channel.
- Stacked MIMO matrix: H(ω) = [H_A | H_B] shape (n_freqs, n_out × 2).
- Note: FRFs are estimated independently per run (SIMO approach stacked), not via full MIMO matrix inversion `H = Gyx · Gxx⁻¹`. This is valid when the two input forces are recorded as separate time-series runs rather than simultaneous acquisitions.

#### SVD-CMIF
- At each frequency line: SVD of the (n_out × 2) H slice → singular values σ₁, σ₂.
- Implemented in new function `compute_mimo_cmif(H_3d)` in `core/sysid.py`.

#### Pole identification
- z-domain right matrix fraction: `H(z) = B(z) · A(z)⁻¹`.
- Normal equations assembled across all (n_out × 2) output-reference pairs simultaneously.
- Reuses `plscf_poles(H_reshaped, freqs, n_order)` from `core/sysid.py` without modification.
- Physical filter: Im(s) > 0, 0 < ξ < 30 %, fn within analysis band.

#### Residue extraction and mode classification
- `extract_residues(H_reshaped, freqs, poles)` returns (n_out × 2, n_modes) complex residues.
- Reshaped to (n_out, 2, n_modes); per mode, ‖Run A column‖ vs ‖Run B column‖ determines S / A label.
- FRF synthesis and NMSE computed per output per reference.

#### Best-practice rationale
- PolyMAX (multi-reference pLSCF) is the current industry standard for MIMO EMA (aircraft GVT, automotive NVH).
- Symmetric / antisymmetric excitation exploits structural near-symmetry to pre-separate mode families, reducing coupling between closely-spaced symmetric and antisymmetric modes in the stability diagram.
- Common denominator polynomial enforces global consistency of natural frequencies across all reference-output FRF pairs.

### Session state
| Key | Set by | Consumed by |
|-----|--------|-------------|
| `mimo_run_a_df` | `5_MIMO.py` (load) | `5_MIMO.py` (Build) |
| `mimo_run_b_df` | `5_MIMO.py` (load) | `5_MIMO.py` (Build) |
| `mimo_sample_rate` | `5_MIMO.py` (load) | `5_MIMO.py` (Build, Export) |
| `mimo_H_mat` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_freqs_band` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_cmif` | `5_MIMO.py` (Build) | `5_MIMO.py` (CMIF tab, Stability bg) |
| `mimo_stability_table` | `5_MIMO.py` (Build) | `5_MIMO.py` (Stability tab, Step 2) |
| `mimo_sel_outputs` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_n_out` | `5_MIMO.py` (Build) | `5_MIMO.py` (Extract) |
| `mimo_frf_est_used` | `5_MIMO.py` (Build) | `5_MIMO.py` (reference) |
| `mimo_modal_results` | `5_MIMO.py` (Extract) | `6_MAC.py`, `7_Wireframe.py` |

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
