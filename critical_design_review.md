# Critical Design Review — Modal Analysis Application
**Date:** 2026-05-24 (Pass 4 — re-review)
**Reviewer:** Claude Code (claude-sonnet-4-6)
**Branch:** `mac_dev`
**Test result:** `pytest tests/ -v` — **95 passed, 0 failed, 1 warning** (unrelated to code under review)
**Prior review:** 2026-05-24 (Pass 3, P3-M1/M2 blocked merge)
**Review standard:** `docs/code_review.md`

---

## Executive Summary — Pass 4

**All 6 Pass 3 issues resolved.** Test count grew from 93 to 95; two new tests cover the P3-N3 (`fdd_damping` sentinel) and P3-N4 (ill-conditioning `RuntimeWarning` propagation) fixes. Pass 4 finds **0 new CRITICAL/MAJOR** and **1 new MINOR** and **1 new NIT** — no blocking items. Branch is approved for merge.

---

## Executive Summary — Pass 3 (retained)

**Pass 2 approved the branch for beta; Pass 3 is a full re-review of all code on `mac_dev`.** All 19 issues from Passes 1–2 remain resolved. Pass 3 found **2 new MAJOR** and **4 new MINOR** issues. The 2 MAJOR items (P3-M1 and P3-M2) were fixed before Pass 4.

---

## Executive Summary — Pass 2 (retained)

**All 16 issues from Pass 1 are resolved.** The test suite grew from 82 to 93 tests and now passes clean under `-W error::RuntimeWarning`. No CRITICAL, MAJOR, or MINOR issues remained at the time of Pass 2 approval.

---

## Pre-Review Checklist

| Item | Status |
|---|---|
| Read relevant `docs/workflow_pages.md` sections | ✓ |
| Read `docs/data_model.md` | ✓ |
| Confirm docs updated with code changes | Pass 4: `mimo_frf_est_used` missing from `data_model.md` (NIT, see P4-N2) |
| Check `todo.md` — known bugs | USER items open (USER1-3); no code-review items in MAJOR/MINOR sections |
| Confirm tests exist for new/changed `core/` functions | ✓ — 95 tests, up from 93 |
| Identify high-blast-radius `core/` signature changes | None in this diff |

---

## Pass 1 Issues — Resolution Status

### CRITICAL Issues (all resolved)

| ID | Description | Status |
|---|---|---|
| C1 | `pd.eval(engine="python")` — code injection | **FIXED** — `_BLOCKED` regex + numexpr-first fallback in `tools/channel_math.py`; 8 security tests pass |
| C2 | Analysis log path traversal | **FIXED** — `re.sub(r'[^A-Za-z0-9_\-]', '_', ...)[:64]` at `pages/1_Time_History.py:134` |
| C3 | `np.real()` strips imaginary part of mode shapes before MAC | **FIXED** — complex shapes passed directly; `pages/7_MAC.py:164-166` |

### MAJOR Issues (all resolved)

| ID | Description | Status |
|---|---|---|
| M1 | One-sided FFT amplitude 3 dB error | **FIXED** — one-sided correction in `core/spectral.py:38-42`; `test_compute_fft_amplitude_correction` passes |
| M2 | Single-FFT PSD window power correction missing | **FIXED** — `W₂ = Σ w[n]²`, `norm = 2·fs·W₂` at `pages/3_Spectral_Analysis.py:285-286`; `test_single_fft_psd_hann_window_normalization` passes |
| M3 | MIMO sample-rate mismatch warned but not blocked | **FIXED** — `st.stop()` called after error at `pages/5_MIMO.py:68` |
| M4 | `oma_peak_estimates` session key undocumented | **FIXED** — key added to `docs/data_model.md` with correct owner/consumer description; `oma_peak_seed_ver` also documented |
| M5 | Residue extraction used full-span H not band-limited subset | **FIXED** — `extract_residues(H_mat_band, freqs_band, poles)` at `pages/4_SIMO.py:443`; NMSE also computed band-limited |

### MINOR Issues (all resolved)

| ID | Description | Status |
|---|---|---|
| N1 | `Gyx`/`Gxy` variable naming reversed | **FIXED** — `Gxy = Sy * np.conj(Sx)` with explicit comment; `Gyx = np.conj(Gxy)` in `core/spectral.py:61-62, 156-157` |
| N2 | `RuntimeWarning` for zero-input (H2, Hv, gamma2) | **FIXED** — `np.errstate(divide='ignore', over='ignore', invalid='ignore')` + `np.where(np.isfinite(...))` clamps at `core/spectral.py:69-78`; confirmed clean under `-W error::RuntimeWarning` |
| N3 | Widget key pop as state reset in OMA page | **FIXED** — version-counter pattern: `key=f"oma_estimates_v{seed_ver}"` at `pages/6_OMA.py:297`; `oma_peak_seed_ver` incremented on Build |
| N4 | Channel-assignment widgets missing explicit `key=` | **FIXED** — `key="th_input_channel"` and `key="th_output_channels"` at `pages/1_Time_History.py:87, 95` |
| N5 | `mimo_file_a_name`, `mimo_file_b_name` undocumented | **FIXED** — both keys in `docs/data_model.md:40-41` |
| N6 | No `@st.cache_data` on expensive computations | **FIXED** — `@st.cache_data` added to both `compute_output_spectral_matrix` (`core/spectral.py:96`) and `compute_welch_quantities` (`core/spectral.py:133`) |

### NIT Issues (all resolved)

| ID | Description | Status |
|---|---|---|
| T1 | Bare `[]` session state access on `mac_fe_freqs` | **FIXED** — `.get("mac_fe_freqs", np.array([]))` at `pages/7_MAC.py:190` |
| T2 | `compute_cmif` docstring said "singular value" | **FIXED** — docstring now reads "L2 row norm of each frequency row (≡ σ₁ for SIMO use)" at `core/sysid.py:9` |
| T3 | MIMO MAC silently uses Run A shapes | **FIXED** — `st.caption("MAC uses Run A (reference) mode shape amplitudes only.")` at `pages/7_MAC.py:157` |

---

## Pass 2 New Findings

### MINOR Issues (new)

---

**[MINOR] `docs/data_model.md:137` — `add_channel` API description says "Python engine" but implementation prefers `numexpr`.**

WHY: The tools API table reads `"via pd.eval, Python engine"`. The implementation now tries `engine="numexpr"` first and falls back to Python only if numexpr cannot parse the expression. A developer reading the docs to understand security properties could incorrectly assume only Python engine is in use.

FIX: Update the description:

```
- `add_channel(df, new_name, expression)` — evaluate *expression* using existing columns as
  variables; blocked tokens checked first, then `pd.eval` with numexpr engine (Python fallback).
  Returns copy `(df, error)`.
```

---

**[MINOR] `docs/data_model.md` — seven page-7-internal session-state keys undocumented.**

WHY: `pages/7_MAC.py` writes the following keys that are absent from `docs/data_model.md`:
`mac_mapping`, `mac_matrix`, `mac_fe_freqs`, `mac_exp_freqs`, `mac_f06_data`, `_mac_f06_name`, `mac_exp_source`. While all are consumed only within page 7 (no cross-page contract), the project convention per `docs/code_review.md` Step 2 is that every key appears in the table.

FIX: Add a block to the session-state table:

| Key | Set by | Consumed by |
|---|---|---|
| `mac_exp_source` | `7_MAC.py` (radio) | `7_MAC.py` (mode shape selection) |
| `mac_mapping` | `7_MAC.py` (channel-DOF form) | `7_MAC.py` (Compute MAC) |
| `mac_matrix` | `7_MAC.py` (Compute MAC) | `7_MAC.py` (heatmap, frequency table) — shape `(n_fe_modes, n_exp_modes)` |
| `mac_fe_freqs` | `7_MAC.py` (Compute MAC) | `7_MAC.py` (heatmap labels, freq table) |
| `mac_exp_freqs` | `7_MAC.py` (Compute MAC) | `7_MAC.py` (heatmap labels, freq table) |
| `mac_f06_data` | `7_MAC.py` (F06 upload) | `7_MAC.py` (Compute MAC) |
| `_mac_f06_name` | `7_MAC.py` (F06 upload guard) | `7_MAC.py` (re-load guard) |

---

### NIT Issues (new)

---

**[NIT] `pages/7_MAC.py:79-81` — bare `[]` access on `mimo_modal_results` and `modal_results` in `exp_results` assignment.**

WHY: The accesses at lines 80-81 are logically safe because `source_options` is constructed from `has_simo`/`has_mimo` which themselves come from `.get()` checks. However, the pattern is inconsistent with the project convention of always guarding session-state reads with `.get()`.

FIX:
```python
exp_results = (
    st.session_state.get("mimo_modal_results", {}) if "MIMO" in exp_source
    else st.session_state.get("modal_results", {})
)
```

---

## Test Suite Status

**`pytest tests/ -v` — 93 passed, 0 failed, 1 warning**

The 1 warning is from `tests/test_tools.py::TestTimeSync::test_sync_preserves_monotonic_time` (a `UserWarning` from the merge function — expected and benign).

New tests added since Pass 1 (11 new):
- `test_compute_fft_amplitude_correction` — verifies one-sided correction (covers M1)
- `test_single_fft_psd_hann_window_normalization` — verifies W₂ norm (covers M2)
- `TestChannelMathSecurity` (8 tests) — injection blocking (covers C1)

Zero RuntimeWarnings under `-W error::RuntimeWarning` — N2 fully resolved.

Remaining coverage gaps:
- No test for MAC page complex-mode-shape handling (C3 fix) — hard to test without Streamlit runtime; acceptable
- No test for path sanitization in `1_Time_History.py` (C2 fix) — the logic is in page render code, not a pure function; acceptable

---

## Security Checklist

| Check | Status |
|---|---|
| `pd.eval` expression injection | **PASS** — `_BLOCKED` regex + numexpr-first; 8 tests pass |
| Analysis log path traversal | **PASS** — safe character allowlist + 64-char truncation |
| `pd.eval` local_dict scope | **PASS** — only DataFrame column names exposed |
| BDF file parser robustness | **PASS** — malformed cards handled gracefully |

---

## Documentation Compliance Audit

| Document | Status |
|---|---|
| `docs/data_model.md` session-state table | PASS — all keys documented; `add_channel` description updated |
| `docs/workflow_pages.md` algorithm descriptions | PASS — matches code |
| `docs/data_model.md` core API signatures | PASS — all `core/` signatures present and accurate |

---

## Final Approval Gate — Pass 4

| Gate | Status |
|---|---|
| All [CRITICAL] resolved | ✓ — 0 open |
| All [MAJOR] resolved | ✓ — 0 open (P3-M1/M2 fixed) |
| `pytest tests/ -v` passes | ✓ 95/95 |
| `docs/data_model.md` up to date | ✓ (P4-N2 is NIT, non-blocking) |
| No new [CRITICAL] introduced since last review pass | ✓ |

**Pass 4 verdict: APPROVED — no blocking issues. 1 MINOR (P4-N1) and 1 NIT (P4-N2) open; fix in follow-up PR.**

---

## Final Approval Gate — Pass 3 (retained)

| Gate | Status |
|---|---|
| All [CRITICAL] resolved | ✓ — 0 open |
| All [MAJOR] resolved | **✗ — P3-M1 and P3-M2 open** (fixed before Pass 4) |
| `pytest tests/ -v` passes | ✓ 93/93 |
| `docs/data_model.md` up to date | ✓ |
| No new [CRITICAL] introduced since last review pass | ✓ |

**Pass 3 verdict: BLOCKED — 2 MAJOR issues must be fixed before merge.**

## Final Approval Gate — Pass 2 (retained for reference)

| Gate | Status |
|---|---|
| All [CRITICAL] resolved | ✓ — 0 open |
| All [MAJOR] resolved | ✓ — 0 open |
| `pytest tests/ -v` passes | ✓ 93/93 |
| `docs/data_model.md` up to date | ✓ — NW1, NW2 resolved |
| No new [CRITICAL] introduced since last review pass | ✓ |

**Pass 2 verdict: APPROVED for beta — no blocking issues. All MINOR items resolved.**

---

## Pass 3 New Findings

### MAJOR Issues (new — block merge)

---

**[MAJOR] P3-M1 — `pages/5_MIMO.py:536` — MIMO residue extraction uses full-range H_mat/freqs instead of band-limited arrays (M5 fix not propagated from SIMO)**

WHY: The M5 fix applied to SIMO (`si_H_mat_band`, `si_freqs_band`) was never replicated in MIMO. `build_stability_table` is called with `H_band`/`freqs_band`, so poles are identified within `[f_min, f_max]`. But `extract_residues` at line 536 receives `mimo_H_mat` (full range) and `mimo_freqs` (full range), so the partial-fraction least-squares system includes all frequencies 0 Hz to Nyquist. Out-of-band response (noise floor, other modes, filter roll-off) biases the residue estimates.

FIX: Store `mimo_H_mat_band` and use it (alongside `mimo_freqs_band`) in the extract step, matching what SIMO does at lines 405–406 and 443:

```python
# In build step (after line 497):
st.session_state["mimo_H_mat_band"] = H_band

# In extract step (replace lines 508–509):
H_mat = st.session_state.get("mimo_H_mat_band")
freqs_ext = st.session_state.get("mimo_freqs_band")
if H_mat is None or freqs_ext is None:
    st.error("Build the stability diagram first.")
    st.stop()

# And NMSE should be computed band-limited too:
H_syn_band = synthesize_frf(freqs_ext, poles, residues)
nmse = modal_fit_nmse(H_mat, H_syn_band)
# Keep full-range synthesis for plotting only:
H_syn = synthesize_frf(st.session_state["mimo_freqs"], poles, residues)
```

---

**[MAJOR] P3-M2 — `pages/5_MIMO.py:529` — Ill-conditioning warning compares full-range freq count vs 2×poles; always passes, masking underdetermined band-limited system**

WHY: `len(freqs_ext)` is the full-spectrum freq count (e.g., 1000 lines for a 1000-sample signal). The check `len(freqs_ext) < 2 * len(poles)` will never fire for any realistic configuration. If the analysis band contains only 50 freq lines and 25 poles are requested, the residue fit is underdetermined within the band — but the 1000-point full-range count masks this. The companion fix in SIMO at lines 436–440 correctly checks `len(freqs_band)`.

FIX: After P3-M1 is applied, `freqs_ext` will be the band-limited array. The check at line 529 then naturally uses `len(freqs_band)` and is correct. No additional change needed beyond P3-M1.

---

### MINOR Issues (new)

---

**[MINOR] P3-N1 — `pages/3_Spectral_Analysis.py:352` — Cross-power tab phase display is sign-inverted after Gxy/Gyx naming swap**

WHY: The N1 fix renamed the Gxy/Gyx variables in `core/spectral.py`. Old `Gyx = Sy * conj(Sx)` had phase = ∠Y − ∠X = ∠H. The new `Gyx = conj(Gxy) = conj(Sy * conj(Sx))` has phase = ∠X − ∠Y = −∠H. Page 3 still reads `ch_data[ch]["Gyx"]` and plots its angle (line 352): the Cross-Power phase subplot now shows the negative of the FRF phase. Magnitude is unchanged.

FIX: Either (a) plot `Gxy` instead (which has the physically expected phase ∠H), or (b) update the tab label to `"∠Gyx — {ch} (°)"` clearly indicating the conjugate direction, and add a caption. Option (a) is the cleaner fix:

```python
# Replace line 346:
Gyx = ch_data[ch]["Gxy"][mask]   # Gxy = Sy*conj(Sx); phase = ∠H
# Update titles at line 336:
titles += [f"|Gxy| — {ch} (dB)", f"∠Gxy — {ch} (°)"]
```

---

**[MINOR] P3-N2 — `pages/3_Spectral_Analysis.py:268` — `N = 2*(len(freqs)−1)` gives wrong FFT length for odd-length signals in Single FFT PSD**

WHY: `np.fft.rfftfreq(n)` returns `n//2 + 1` bins. For even `n`, `2*(n//2+1-1) = n` (correct). For odd `n`, `2*((n-1)//2+1-1) = n-1` (off by one). The window array constructed at line 282 (`get_window(..., N)`) has length `n-1` instead of `n`, giving a slightly wrong W2 and therefore a systematic Single FFT PSD normalization error.

FIX:
```python
# Replace line 268:
N = 2 * len(freqs) - (1 if freqs[-1] == sample_rate / 2 else 0)
# Or more robustly, infer from the saved fft_results:
N = len(fft_res["ffts"][plot_chs[0]]) * 2 - (1 if ...)
```
Simplest correct fix: store `N` in `fft_results` when computing in `2_FFT.py` and read it here.

---

**[MINOR] P3-N3 — `core/sysid.py:394` — `fdd_damping` gives overestimated damping when peak is at the last frequency index**

WHY: The upper half-power loop `for k in range(peak_idx + 1, len(sv1))` is empty when `peak_idx = len(sv1) - 1`. `f_b` defaults to `freqs[-1]`, so `xi_pct = (freqs[-1] - f_a) / (2 * fn) * 100` may overestimate damping. The 50% clamp at the call site only catches severe cases; moderate overestimates slip through.

FIX: Add an explicit guard:
```python
f_b = float(freqs[-1])
found_upper = False
for k in range(peak_idx + 1, len(sv1)):
    if sv1[k] <= half_power:
        ...
        found_upper = True
        break
if not found_upper:
    return 0.0, float(freqs[0]), float(freqs[-1])  # signal failure; caller clamps to 2%
```

---

**[MINOR] P3-N4 — `core/sysid.py:313` / `core/sysid.py:239` — `RuntimeWarning` from `extract_residues` inside `build_stability_table` is not surfaced to the Streamlit UI**

WHY: When the analysis band is narrow and model order is high, `extract_residues` issues `warnings.warn(..., RuntimeWarning)` at line 313. Inside `build_stability_table`, the call is wrapped in `try/except Exception` (line 239), which does not suppress warnings. The warning goes to stderr only; the user sees no indication in the app. Subsequent MAC-based pole classification uses ill-conditioned residues, potentially misclassifying `stable_all` poles as `stable_fd` without any visible error.

FIX: Catch the RuntimeWarning inside `build_stability_table` using `warnings.catch_warnings` and either re-raise as a return-value flag or propagate to the calling page. Alternatively, the page-level underdetermined check (P3-M2) would catch the case before it reaches the stability-diagram level.

---

---

## Pass 4 New Findings

### MINOR Issues (new — non-blocking)

---

**[MINOR] P4-N1 — `core/mimo.py:61` — `compute_mimo_frfs` latent `NameError` when `sel_outputs=[]` in Welch branch**

WHY: The Welch branch assigns `freqs_full = res_a["freqs"]` after the `for ch in sel_outputs` loop. If `sel_outputs` is empty the loop body never executes, `res_a` is undefined, and the subsequent reference raises `NameError`. The page-level guard (`if not sel_outputs: st.stop()`) prevents this in normal use, but the core function has no internal protection and could fail if called directly.

FIX: Assign `freqs_full` before the loop and update inside it, or validate at function entry:
```python
if not sel_outputs:
    raise ValueError("sel_outputs must not be empty")
```

---

### NIT Issues (new)

---

**[NIT] P4-N2 — `docs/data_model.md` — `mimo_frf_est_used` session-state key missing from `data_model.md` table**

WHY: `pages/5_MIMO.py:512` writes `st.session_state["mimo_frf_est_used"] = frf_est`. The key appears in `docs/workflow_pages.md:420` but is absent from the authoritative `docs/data_model.md` session-state table, inconsistent with the analogous `si_frf_est_used` which is documented.

FIX: Add to the `data_model.md` session-state table after the `mimo_n_out` row:
```
| `mimo_frf_est_used` | `5_MIMO.py` (Build) | `5_MIMO.py` (reference) |
```

---

---

## Full Issue Summary Table

| ID | Severity | File | Line | Short Description | Status |
|---|---|---|---|---|---|
| C1 | ~~CRITICAL~~ FIXED | `tools/channel_math.py` | 54 | `pd.eval(engine="python")` — code injection via user expression | FIXED |
| C2 | ~~CRITICAL~~ FIXED | `pages/1_Time_History.py` | 131 | Analysis log path traversal — `analysis_name` not sanitized | FIXED |
| C3 | ~~CRITICAL~~ FIXED | `pages/7_MAC.py` | 162–164 | `np.real()` removed; complex mode shapes passed directly | FIXED |
| M1 | ~~MAJOR~~ FIXED | `core/spectral.py` | 35–37 | One-sided correction applied in `compute_fft`; amplitude test added | FIXED |
| M2 | ~~MAJOR~~ FIXED | `pages/3_Spectral_Analysis.py` | 263–273 | Window power W₂ correction applied; PSD integration test added | FIXED |
| M3 | ~~MAJOR~~ FIXED | `pages/5_MIMO.py` | 63–67 | Sample-rate mismatch now blocks with `st.stop()` | FIXED |
| M4 | ~~MAJOR~~ FIXED | `docs/data_model.md` | — | `oma_peak_estimates` + `oma_peak_seed_ver` documented | FIXED |
| M5 | ~~MAJOR~~ FIXED | `pages/4_SIMO.py` | 440 | Residue extraction uses `H_mat_band` / `freqs_band` | FIXED |
| N1 | ~~MINOR~~ FIXED | `core/spectral.py` | 143 | `Gxy`/`Gyx` naming corrected; convention comment added | FIXED |
| N2 | ~~MINOR~~ FIXED | `core/spectral.py` | 58–66 | `np.errstate` + `np.where` guards; zero RuntimeWarnings | FIXED |
| N3 | ~~MINOR~~ FIXED | `pages/6_OMA.py` | 350 | Version-counter key (`oma_estimates_v{n}`) replaces key-pop pattern | FIXED |
| N4 | ~~MINOR~~ FIXED | `pages/1_Time_History.py` | 81–97 | Stable `key=` args on channel-assignment widgets | FIXED |
| N5 | ~~MINOR~~ FIXED | `docs/data_model.md` | — | `mimo_file_a_name`, `mimo_file_b_name` documented | FIXED |
| N6 | ~~MINOR~~ FIXED | `core/spectral.py` | 96, 133 | `@st.cache_data` on `compute_output_spectral_matrix` and `compute_welch_quantities` | FIXED |
| T1 | ~~NIT~~ FIXED | `pages/7_MAC.py` | 188 | `.get()` used for `mac_fe_freqs`, `mac_exp_freqs` | FIXED |
| T2 | ~~NIT~~ FIXED | `core/sysid.py` | 8–12 | `compute_cmif` docstring corrected to "L2 row norm" | FIXED |
| T3 | ~~NIT~~ FIXED | `pages/7_MAC.py` | 162 | MIMO Run A caption added to UI | FIXED |
| NW1 | ~~MINOR~~ FIXED | `docs/data_model.md` | 137 | `add_channel` description updated to "numexpr engine (Python fallback)" | FIXED |
| NW2 | ~~MINOR~~ FIXED | `docs/data_model.md` | — | 7 page-7 session-state keys (`mac_*`, `_mac_f06_name`) added to table | FIXED |
| NW3 | ~~NIT~~ FIXED | `pages/7_MAC.py` | 79–81 | `.get()` used for `mimo_modal_results`/`modal_results` — consistent with project convention | FIXED |
| P3-M1 | ~~MAJOR~~ FIXED | `pages/5_MIMO.py` | 518–548 | `extract_residues(H_mat_band, freqs_ext, poles)` + `mimo_H_mat_band`/`mimo_freqs_band` stored and used | FIXED |
| P3-M2 | ~~MAJOR~~ FIXED | `pages/5_MIMO.py` | 541 | `len(freqs_ext)` now checks band-limited count; naturally correct after P3-M1 | FIXED |
| P3-N1 | ~~MINOR~~ FIXED | `pages/3_Spectral_Analysis.py` | 336, 346 | Cross-power tab plots `Gxy` (`∠Gxy` title); phase = ∠H correct | FIXED |
| P3-N2 | ~~MINOR~~ FIXED | `pages/3_Spectral_Analysis.py` | 268 | `N = fft_res.get("n_samples", ...)` reads stored sample count; `n_samples` stored by page 2 | FIXED |
| P3-N3 | ~~MINOR~~ FIXED | `core/sysid.py` | 415–416 | `found_upper` guard; returns `(0.0, freqs[0], freqs[-1])` sentinel; test added | FIXED |
| P3-N4 | ~~MINOR~~ FIXED | `core/sysid.py` | 302–308; `pages/5_MIMO.py` | `build_stability_table` propagates `RuntimeWarning`; MIMO page catches with `warnings.catch_warnings`; test added | FIXED |
| P4-N1 | MINOR | `core/mimo.py` | 61 | Latent `NameError` in `compute_mimo_frfs` Welch branch when `sel_outputs=[]` — `res_a` referenced before assignment | OPEN |
| P4-N2 | NIT | `docs/data_model.md` | — | `mimo_frf_est_used` session-state key in `workflow_pages.md:420` but missing from `data_model.md` table | OPEN |
