# MIMO Swept Sine Testing

## Overview

MIMO (Multiple-Input Multiple-Output) swept sine testing uses two simultaneously operating shakers to excite a structure across a frequency band while measuring responses at multiple accelerometers. Compared to SIMO (single-shaker) testing, MIMO swept sine provides:

- Higher signal-to-noise ratio (SNR) than broadband random excitation.
- Leakage-free spectra when using sine tracking filters with a slow-enough sweep rate.
- Ability to excite and separate closely spaced or repeated modes that a single shaker may not reveal.
- Control over input force levels, keeping the structure in a linear regime (important for aircraft and lightly damped structures).
- Separation of symmetric and antisymmetric (asymmetric) mode families through deliberate phase conditions between shakers.

---

## 1. Test Setup

### 1.1 Shaker Placement

- Place shakers at locations with sufficient modal participation — avoid nodal points for the target modes.
- Shaker positions must be **linearly independent** with respect to the target mode shapes (i.e., the two input locations must not simultaneously be nodes of the same mode).
- Stinger rods (push rods) must be used between the shaker and the structure to isolate the shaker mass and ensure predominantly axial force transmission.
- Attach force transducers (load cells) directly at the structure–stinger interface. Impedance head sensors (combined force + acceleration) are preferred at each drive point.

### 1.2 Reference (Input) Channels

| Parameter | Recommendation |
|---|---|
| Number of inputs | Equal to number of shakers (2 for this test) |
| Force measurement | Load cell or impedance head at each shaker attachment |
| Drive point | At least one drive-point FRF per shaker (co-located force and response) |

Drive-point FRFs must exhibit a positive real part across the frequency band — this is a fundamental consistency check.

### 1.3 Response (Output) Channels

- Accelerometers placed to capture all relevant mode shapes.
- Sensor density: at least 2× the number of target modes to avoid spatial aliasing.
- Alignment: mount sensors along a single axis or in a tri-axial block; record mounting direction relative to the geometry model.

### 1.4 Data Acquisition

- Sampling rate: ≥ 10× the maximum frequency of interest.
- Anti-aliasing filters engaged on all channels.
- Dynamic range: ensure ADC is not clipping (target < −6 dBFS peak); adjust shaker drive levels accordingly.

---

## 2. Pre-Test Checks

| Check | Method | Pass Criterion |
|---|---|---|
| **Linearity** | Repeat measurement at 50% and 100% drive level; compare FRFs | FRF magnitude within ±1 dB |
| **Reciprocity** | Compare H(i→j) vs H(j→i) for cross FRFs | Magnitude within ±1 dB, phase within ±5° |
| **Drive-point positivity** | Real part of H at drive-point location | Must be positive (≥ 0) at all frequencies |
| **Coherence** | Ordinary or multiple coherence per output | γ² ≥ 0.9 in the analysis band |
| **Structural modification** | Inspect attachment points before/after | No visible stiffness change from shaker boundary conditions |

---

## 3. Swept Sine Procedure

### 3.1 Sweep Parameters

| Parameter | Typical Value | Notes |
|---|---|---|
| **Sweep type** | Linear or logarithmic | Log sweep preferred for lightly damped structures (uniform frequency resolution on log scale) |
| **Sweep rate** | ≤ ξωₙ² / 2π (Hz/s) per mode | Must be slow enough for each mode to reach steady state; reduce if coherence is poor |
| **Frequency range** | Cover all target modes + 10% margin | e.g., 1–200 Hz |
| **Force level** | Set per pre-test linearity check | Typically constant-force control preferred over constant-voltage |
| **Settling time** | ≥ 3 / (ξ·fₙ) cycles at each frequency | Ensures transient decay before recording |

A commonly quoted conservative sweep rate limit is:

```
sweep_rate ≤ (ξ · fₙ)² / 2  [Hz/s]
```

where ξ is the damping ratio and fₙ is the natural frequency in Hz. For 2% damping at 5 Hz this gives ≤ 0.005 Hz/s — very slow, so stepped-sine (dwell at discrete frequencies) is often used in practice.

### 3.2 Phase Conditions (Runs)

Two sweeps are performed with different phase relationships between the two shakers:

| Run | Shaker 1 Phase | Shaker 2 Phase | Excites |
|---|---|---|---|
| **Run A — Symmetric** | 0° | 0° | Symmetric (in-phase) mode families |
| **Run B — Asymmetric** | 0° | 180° | Antisymmetric (out-of-phase) mode families |

Using these two phase conditions with 2 shakers provides the minimum required number of independent excitation vectors to compute the full 2-column MIMO FRF matrix. Additional runs with alternative phase offsets (e.g., 0°/90°) can be used for overdetermination and averaging.

> **Industry note (Crystal Instruments):** The number of sweeps can equal the number of shakers. Both deterministic phase pairs (0°/0° and 0°/180°) and randomised phase pairs have been shown to yield identical FRFs, confirming that phase diversity rather than a specific angle is the key requirement.

---

## 4. MIMO FRF Computation

### 4.1 Matrix Formulation

For each frequency line ω, the MIMO FRF matrix **H**(ω) is of size (n_outputs × n_inputs):

```
H(ω) = Gyx(ω) · Gxx(ω)⁻¹          [H1 estimator]
H(ω) = Gyy(ω) · Gxy(ω)⁻¹          [H2 estimator]
```

where:

| Symbol | Size | Description |
|---|---|---|
| **Gxx** | 2 × 2 | Input cross-power spectral density matrix |
| **Gyx** | n_out × 2 | Output–input cross-power matrix |
| **Gyy** | n_out × n_out | Output auto/cross-power matrix |

The (i,j) element of **Gxx** is `Gxx[i,j] = X_i · conj(X_j)` averaged across sweeps.

### 4.2 Averaging Across Runs

With Run A and Run B providing two independent force vectors:

```python
# Stack runs column-wise: X shape = (2, n_runs), Y shape = (n_out, n_runs)
Gxx = X @ X.conj().T           # 2×2 input power matrix
Gyx = Y @ X.conj().T           # n_out×2 cross-power matrix
H   = Gyx @ np.linalg.inv(Gxx) # n_out×2 FRF matrix
```

### 4.3 Condition Number Check

Before inverting **Gxx**, compute its condition number:

```python
cond = np.linalg.cond(Gxx)
```

| Condition Number | Interpretation |
|---|---|
| < 10 | Well conditioned — reliable inversion |
| 10–100 | Moderate conditioning — acceptable |
| > 100 | Ill conditioned — runs are insufficiently independent; adjust shaker phases |

A high condition number indicates the two excitation vectors are nearly collinear (e.g., both shakers at the same phase), which inflates noise in the computed FRFs.

### 4.4 Multiple Coherence

The multiple coherence for output channel _k_ quantifies how much of the response is explained by the two inputs:

```
γ²_multiple[k] = (H[k,:] · Gxx · H[k,:].conj().T) / Gyy[k,k]
```

Values < 0.9 at frequencies of interest indicate: extraneous noise, nonlinearity, unmeasured inputs, or too-fast a sweep rate.

---

## 5. Quality Checks on the FRF Matrix

| Check | Method | Target |
|---|---|---|
| **Multiple coherence** | Per output channel | ≥ 0.9 in analysis band |
| **Reciprocity** | Compare H[i,j] vs H[j,i] | Magnitude ±1 dB, phase ±5° |
| **Drive-point FRF sign** | Real(H_drive) | Positive at all frequencies |
| **Gxx condition number** | Per frequency line | < 100 |
| **CMIF rank** | SVD σ₁/σ₂ ratio at resonance | Both singular values should peak at distinct modal frequencies |

---

## 6. Complex Mode Indicator Function (CMIF)

The MIMO CMIF is computed from the SVD of **H**(ω) at each frequency line:

```
H(ω) ≈ U(ω) · Σ(ω) · V(ω)ᴴ
```

- **σ₁(ω):** first singular value — peaks indicate natural frequencies of all modes.
- **σ₂(ω):** second singular value — additional peak at a frequency where σ₁ also peaks indicates a repeated or closely spaced mode.
- **Left singular vectors U:** approximate mode shape at that frequency.
- **Right singular vectors V:** approximate modal participation factors (force distribution).

The CMIF plot (log scale, σ₁ and σ₂ vs frequency) is the primary tool for initial mode count estimation and frequency range selection.

---

## 7. System Identification — pLSCF (PolyMAX)

### 7.1 Stability Diagram

Using the full MIMO FRF matrix as input to pLSCF:

1. Fit polynomial fraction models at increasing model orders (2, 4, 6, … up to max order).
2. At each order, extract poles (frequency + damping) and classify stability:
   - **New:** pole appeared at this order.
   - **Stable f:** frequency stable within tolerance (e.g., Δf < 1%).
   - **Stable f+d:** frequency and damping stable.
   - **Stable all:** frequency, damping, and mode shape (MAC) all stable — physical pole.
3. Read off stable columns (vertical alignment across orders) to identify physical modes.

### 7.2 Mode Shape Extraction

After selecting poles from the stability diagram:

1. Compute residues via complex least-squares fit across the full **H** matrix.
2. Modal scale factor (modal mass) obtainable from drive-point residues.
3. Synthesise **H_syn** and compare against measured **H** (NMSE or Modal Fit Quality indicator).

### 7.3 Mode Complexity

| Metric | Formula | Good Mode |
|---|---|---|
| **MPC** (Modal Phase Collinearity) | Eigenvalue ratio of [Re φ, Im φ] scatter | ≥ 0.9 |
| **MPD** (Mean Phase Deviation) | Mean angular deviation from best-fit line | ≤ 10° |
| **Modal Fit NMSE** | 10·log₁₀(||H-H_syn||²/||H||²) | < −20 dB |

---

## 8. Workflow Summary

```
Load Run A + Run B CSVs
        │
        ▼
Time domain review (trim, filter, check levels)
        │
        ▼
Compute MIMO FRF matrix H(ω)  [n_out × 2 × n_freq]
   ├─ Check Gxx condition number
   ├─ Check multiple coherence per output
   └─ Check reciprocity and drive-point positivity
        │
        ▼
Plot CMIF (σ₁, σ₂) → initial mode count & freq range
        │
        ▼
Build Stability Diagram (pLSCF, orders 2..N)
        │
        ▼
Select stable poles → extract mode shapes & residues
        │
        ▼
Synthesise H_syn → check NMSE, MPC, MPD
        │
        ▼
Export modal parameters (fn, ξ, φ)
```

---

## 9. Future Developments

1. **MIMO Random** — two independent broadband random inputs; FRF via H1 estimator with Welch averaging; requires good coherence to overcome leakage.
2. **MIMO Burst Random** — burst random removes leakage without a window; better for lightly damped structures.
3. **Force control / COLA** — constant-overlap-and-add stepped sine with force-controlled amplitude for nonlinear structure characterisation.
4. **Operational Modal Analysis (OMA) overlay** — compare EMA mode shapes against OMA results for in-service validation.
