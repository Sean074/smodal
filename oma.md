# OMA — Operational Modal Analysis Implementation Plan

## Objective

Create page `6_OMA.py` for Operational Modal Analysis (OMA) using only output
response data (accelerations). The force column in the CSV is ignored.
Renumber the existing downstream pages: 7_MAC, 8_Wireframe, 9_Method.
Update `analysis_method.ipynb` with the OMA method.

---

## Analytical Method

### What is OMA?

OMA (Operational Modal Analysis) identifies modal parameters — natural frequency,
damping ratio, and mode shape — from ambient or in-service vibration data.
Unlike EMA (Experimental Modal Analysis), the excitation force is **not measured**.
The key assumption is that the unmeasured input is broadband stationary random
(spectrally flat), so the output power spectral density matrix encodes the system's
poles directly.

### Core mathematical objects

| EMA (SIMO / MIMO) | OMA |
|---|---|
| FRF matrix **H**(ω) — output/input ratio | Spectral matrix **S**_yy(ω) — output/output PSD |
| Excitation G_xx measured explicitly | Excitation assumed white: G_xx ≈ const |
| H1 / H2 / Hv estimators | Welch CPSD matrix |
| Poles from curve-fitting H | Poles from SVD of S_yy |
| Mode shapes from residues | Mode shapes from left singular vectors |
| Mass-normalised shapes possible | Un-normalised shapes only |

### Frequency Domain Decomposition (FDD)

The method used here is **FDD** (Brincker et al. 2000), the frequency-domain
standard for OMA:

1. **Output spectral matrix** — for `n_out` response channels compute the
   (n_out × n_out) power / cross-power matrix at each frequency line using
   Welch averaging:

   ```
   S_yy[i, j](ω) = CPSD(y_i, y_j, ω)
   ```

   The diagonal entries are auto-PSDs; off-diagonal are cross-PSDs.

2. **Singular Value Decomposition per frequency line**:

   ```
   S_yy(ω_k) = U_k Σ_k U_k^H
   ```

   The first singular value σ₁(ω) is the **Power CMIF** (Complex Mode Indicator
   Function). Its peaks identify the natural frequencies.
   The corresponding left singular vector **u₁**(ω_k) is an estimate of the mode
   shape at that frequency.

3. **Peak picking** — local maxima in σ₁ are candidate modes.

4. **Damping via half-power bandwidth** — around each peak ω_r, the half-power
   frequencies (where σ₁ = σ₁_max / √2) give damping ratio:

   ```
   ξ = (ω_b − ω_a) / (2 ω_r)
   ```

5. **Optional EFDD** (Enhanced FDD) — IDFT of the singular value function around
   each peak back to the correlation domain; fit an exponential decay to extract
   a more accurate damping estimate. This is a stretch goal for v1.

### Key differences from the existing EMA pages

| Topic | SIMO (page 4) / MIMO (page 5) | OMA (page 6) |
|---|---|---|
| Input channels | One (SIMO) or two (MIMO) force channels selected | None — force column ignored |
| Frequency function built | FRF **H**(ω) via H1/H2/Hv estimators | Spectral matrix **S**_yy(ω) via CPSD |
| Matrix size | (n_freqs, n_out) | (n_freqs, n_out, n_out) |
| Indicator function | CMIF = ‖H‖ per row | σ₁ of S_yy per frequency |
| Pole estimation | pLSCF or ERA on H — stability diagram | Peak-picking on σ₁ (FDD), no stability diagram in v1 |
| Mode shape extraction | Residue extraction (least squares fit to H) | Left singular vector **u₁** at peak |
| Damping | From complex pole σ + jω_d | Half-power bandwidth of σ₁ curve |
| Mass normalisation | Available (FRF-based) | Not available (no input measured) |
| Synthesis / validation | Synthesised H vs measured H | Synthesised S_yy vs measured S_yy (stretch goal) |

---

## Test Data

`data/input/sample_3ch.csv` — columns: `time`, `force`, `acc_1`, `acc_2`

For OMA: load file, select `acc_1` and `acc_2` as output channels; the `force`
column is ignored (not assigned as an input).

`data/input/val_cantilever_impulse.csv` — columns: `time`, `force_N`,
`Node11_accel_g`, `Node8_accel_g`, `Node6_accel_g`

For OMA: select three node accelerations as outputs; ignore `force_N`.

---

## Implementation Plan

### Phase 0 — Page renumbering (file renames only, no code changes)

| Current file | Renamed to |
|---|---|
| `pages/6_MAC.py` | `pages/7_MAC.py` |
| `pages/7_Wireframe.py` | `pages/8_Wireframe.py` |
| `pages/8_Method.py` | `pages/9_Method.py` |

Update `CLAUDE.md` page table to reflect new numbering.

### Phase 1 — Core: output spectral matrix (`core/spectral.py`)

Add one new function alongside the existing `compute_welch_quantities`:

```python
def compute_output_spectral_matrix(signals, fs, nperseg, noverlap, window):
    """
    signals : (n_samples, n_out) array
    Returns : freqs (n_freqs,), Syy (n_freqs, n_out, n_out) complex
    """
```

Implementation: call `scipy.signal.csd` for every (i, j) pair; enforce
conjugate symmetry (`Syy[k, i, j] = conj(Syy[k, j, i])`).

### Phase 2 — Core: FDD (`core/sysid.py`)

Add two new functions:

```python
def fdd_svd(Syy):
    """
    SVD of S_yy at each frequency line.
    Syy : (n_freqs, n_out, n_out) complex
    Returns : singular_values (n_freqs, n_out), singular_vectors (n_freqs, n_out, n_out)
    """

def fdd_damping(sv1, freqs, peak_idx):
    """
    Half-power bandwidth damping estimate for one peak.
    sv1   : (n_freqs,) first singular values
    peak_idx : index of the peak in freqs / sv1
    Returns : xi_pct (float), f_a (float), f_b (float)
    """
```

Reuse existing `cmif_peak_estimates` by passing `sv1` as the CMIF array.

### Phase 3 — Page `pages/6_OMA.py`

#### Section A — File upload and channel selection

- File uploader (same pattern as 4_SIMO.py).
- Channel selector: multi-select **output channels only**; no input channel widget.
- Optionally show a note: "Force / input columns will be ignored."

#### Section B — Pre-processing expander

Identical to the SIMO pre-processing expander (trim, Butterworth filter) — reuse
`trim_and_filter` from `core/preprocess.py`.

#### Section C — Spectral parameters and CPSD build

Controls (sidebar or expander):
- Frequency band (f_min, f_max sliders)
- Welch segment length (number of segments or nperseg)
- Overlap percentage
- Window type (hann / flattop / boxcar)

On "Build" button:
1. Call `compute_output_spectral_matrix` → S_yy.
2. Call `fdd_svd` → singular values and vectors.
3. Store in session state: `oma_freqs`, `oma_sv`, `oma_svecs`, `oma_Syy`.

#### Section D — FDD plot (CMIF / σ₁)

Plot σ₁(ω) (and optionally σ₂) in dB vs frequency using Plotly.
Style consistent with the CMIF plots on pages 4 and 5.

#### Section E — Peak identification and mode extraction

- Auto-detect peaks from σ₁ using `cmif_peak_estimates` (already in `sysid.py`).
- Allow user to manually add / remove peaks via a data editor table (frequency,
  initial damping guess).
- On "Extract" button for each selected peak:
  - Natural frequency: frequency of the σ₁ peak.
  - Mode shape: singular vector **u₁** at peak frequency (stored as complex array).
  - Damping: call `fdd_damping` for half-power bandwidth estimate.
- Store results as `oma_modal_results` (same schema as `modal_results` from SIMO
  so MAC page can consume it).

`oma_modal_results` schema (list of dicts):
```python
{
    "fn_hz": float,
    "xi_pct": float,
    "mode_shape": np.ndarray,  # complex (n_out,)
    "channel_names": list[str],
}
```

#### Section F — Results table

Display identified modes: frequency (Hz), damping (%), mode shape magnitude,
mode shape phase. Match display style of the SIMO results table.

#### Section G — Synthesis (validation, optional v1)

Reconstruct S_yy from identified poles and singular vectors; overlay on measured
σ₁. Provides a visual goodness-of-fit check. Can be deferred if time-limited.

### Phase 4 — Session state additions

| Key | Set by | Consumed by |
|---|---|---|
| `oma_df` | `6_OMA.py` (load) | `6_OMA.py` |
| `oma_sample_rate` | `6_OMA.py` (load) | `6_OMA.py` |
| `oma_file_name` | `6_OMA.py` (load) | re-load guard |
| `oma_freqs` | `6_OMA.py` (Build) | `6_OMA.py` (plot, Extract) |
| `oma_sv` | `6_OMA.py` (Build) | `6_OMA.py` (plot, Extract) |
| `oma_svecs` | `6_OMA.py` (Build) | `6_OMA.py` (Extract) |
| `oma_Syy` | `6_OMA.py` (Build) | `6_OMA.py` (synthesis) |
| `oma_modal_results` | `6_OMA.py` (Extract) | `7_MAC.py`, `8_Wireframe.py` |

### Phase 5 — `analysis_method.ipynb` update

Add a new section "OMA — Frequency Domain Decomposition" covering:
- Derivation: why S_yy peaks at natural frequencies under white-noise assumption
- Step-by-step worked example with `sample_3ch.csv` (acc_1, acc_2 only)
- Code cells calling `compute_output_spectral_matrix` and `fdd_svd`
- Plot of σ₁, annotated peak picks, half-power damping calculation
- Comparison table: EMA result (from existing cells) vs OMA result

### Phase 6 — `CLAUDE.md` updates

- Update page table (new numbering 6_OMA … 9_Method).
- Add `oma_modal_results` to the session state table.
- Document `compute_output_spectral_matrix`, `fdd_svd`, `fdd_damping` in the
  core modules section.

---

## Existing functions reused without modification

| Function | Module | Used for |
|---|---|---|
| `load_csv` | `core/data_loader.py` | CSV load |
| `compute_sample_rate` | `core/data_loader.py` | fs from time column |
| `trim_and_filter` | `core/preprocess.py` | Pre-processing |
| `cmif_peak_estimates` | `core/sysid.py` | Auto peak detection on σ₁ |
| `deduplicate_stable_poles` | `core/sysid.py` | (optional) dedup if stability used later |
| `compute_mac` | `core/sysid.py` | MAC page consumes oma_modal_results |

---

## References

- Brincker R, Zhang L, Andersen P. *Modal identification of output-only systems
  using frequency domain decomposition.* Smart Materials and Structures, 2001.
- https://community.sw.siemens.com/s/article/OMG-What-is-OMA-Operating-Modal-Analysis
- https://en.wikipedia.org/wiki/Operational_modal_analysis
