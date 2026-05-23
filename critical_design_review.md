# Critical Design Review — Modal Analysis Application
**Date:** 2026-05-23  
**Reviewer:** Claude Code (claude-sonnet-4-6)  
**Branch:** `mac_dev`  
**Test result:** `pytest tests/ -v` — **82 passed, 0 failed, 4 warnings**  
**Review standard:** `docs/code_review.md`

---

## Executive Summary

The codebase is structurally sound and well-tested for its signal-processing core. The test suite covers happy-path and invalid-input scenarios for all `core/` and `tools/` modules. Three **CRITICAL** defects must be resolved before a beta release: two security vulnerabilities (path traversal, code injection) and one numerical correctness defect (MAC computed on real-cast complex mode shapes). Five **MAJOR** issues cover a 3 dB FFT amplitude error, incorrect single-FFT PSD normalization, missing session-state documentation, a sample-rate mismatch that is warned but not blocked, and residue extraction operating on the wrong frequency span. Several **MINOR** and **NIT** items are noted for cleanup.

---

## Pre-Review Checklist

| Item | Status |
|---|---|
| Read relevant `docs/workflow_pages.md` sections | ✓ |
| Read `docs/data_model.md` | ✓ |
| Confirm docs updated with code changes | See M4 — one key missing |
| Check `todo.md` — known bugs | todo.md is clean |
| Confirm tests exist for new/changed `core/` functions | ✓ — 82 tests |
| Identify high-blast-radius `core/` signature changes | None in this diff |

---

## 3. Review Findings

### CRITICAL Issues

---

**[CRITICAL] `tools/channel_math.py:54` — `pd.eval` with Python engine executes arbitrary user code.**

WHY: `engine="python"` in `pd.eval` exposes full Python builtins via the expression string. A user can run `__import__('os').system('...')` or `__import__('subprocess').run(...)` through the channel math UI. The `local_dict` restriction does not prevent access to builtins under the Python engine.

FIX: Switch to `engine="numexpr"` (restricts evaluation to arithmetic/comparison operators). If Python engine is required for pandas Series methods, add an allowlist regex check that rejects any expression containing `__`, `import`, `open`, `exec`, `eval`, `os`, or `subprocess` before passing to `pd.eval`. Also validate that the result is a numeric `pd.Series`.

```python
import re
_BLOCKED = re.compile(r'__|import|open|exec\b|eval\b|\bos\b|subprocess')

def add_channel(df, new_name, expression):
    if new_name == "time":
        return df, "Cannot overwrite the 'time' column."
    if _BLOCKED.search(expression):
        return df, "Expression contains disallowed tokens."
    local_vars = {col: df[col] for col in df.columns}
    try:
        result = pd.eval(expression, local_dict=local_vars, engine="numexpr")
    except Exception as e:
        try:
            result = pd.eval(expression, local_dict=local_vars, engine="python")
        except Exception as e2:
            return df, f"Expression error: {e2}"
    if not isinstance(result, (pd.Series, np.ndarray)):
        return df, "Expression must evaluate to a numeric series."
    ...
```

---

**[CRITICAL] `pages/1_Time_History.py:131` — Analysis log path is not sanitized against directory traversal.**

WHY: `analysis_name` is taken from `st.session_state` (populated from a free-text input in `app.py`). Only spaces are replaced with underscores. A name of `../../.bashrc` or `../etc/cron.d/backdoor` writes outside `data/output/`. `Path("data/output") / "../../.bashrc_log.json"` resolves to `data/.bashrc_log.json` at minimum; with an absolute path it goes anywhere writable.

FIX: Strip all directory components and limit to safe characters before constructing the path.

```python
import re
safe_name = re.sub(r'[^A-Za-z0-9_\-]', '_',
    (st.session_state.get("analysis_name") or "analysis"))[:64]
log_path = Path("data/output") / f"{safe_name}_log.json"
```

---

**[CRITICAL] `pages/7_MAC.py:162-164` — Complex mode shapes are real-cast before MAC computation, producing wrong MAC values for EMA results.**

WHY: `compute_mac` in `core/sysid.py` correctly uses `phi_ref.conj().T @ phi_comp` for complex mode shapes. However page 7 applies `np.real()` before passing shapes to `compute_mac`:

```python
# SIMO path (line 164):
phi_exp = np.real(exp_results["mode_shapes"])
```

pLSCF residues are complex (encode both amplitude and phase per DOF). Discarding imaginary parts is only correct when the mode is perfectly real-normal. For typical damped structures the phase scatter is the signal — stripping it falsely maximises or suppresses MAC values and makes the heatmap meaningless.

FIX: Remove `np.real()`. Pass the complex mode shape matrix directly. `compute_mac` already handles complex inputs correctly.

```python
# SIMO
phi_exp = exp_results["mode_shapes"]          # (n_dof, n_modes) complex
# MIMO — use Run A shapes (this choice should also be documented in the UI)
phi_exp = exp_results["mode_shapes"][:, 0, :] # (n_dof, n_modes) complex
```

---

### MAJOR Issues

---

**[MAJOR] `core/spectral.py:35-37` / `pages/2_FFT.py:247` — `rfft` output used without one-sided amplitude correction (3 dB error in FFT magnitude display).**

WHY: `np.fft.rfft` returns a one-sided spectrum where interior bins (0 < k < N/2) have half the amplitude of a two-sided spectrum. The correct amplitude spectrum requires multiplying those bins by 2. This is explicitly called out as a common defect pattern in `docs/code_review.md`. In `compute_fft`, no correction is applied:

```python
fft_complex = np.fft.rfft(windowed)   # raw — interior bins at half amplitude
```

H1/H2/Hv/coherence are unaffected (error cancels in numerator and denominator). But page 2 plots `np.abs(F)` directly, showing all AC peaks 6 dB too low in power and 3 dB too low in amplitude. The single-FFT Gxx/Gyy fed to page 3 PSD are 4× too small in power.

FIX: Apply the one-sided correction inside `compute_fft`:

```python
fft_complex = np.fft.rfft(windowed)
# One-sided amplitude correction (exclude DC at [0] and Nyquist at [-1] for even N)
n = len(signal)
fft_complex = fft_complex.copy()
if n % 2 == 0:
    fft_complex[1:-1] *= 2
else:
    fft_complex[1:] *= 2
```

Alternatively, document that `compute_fft` returns raw rfft output and apply the correction at all call sites consistently. The Welch path (`scipy.signal.welch`) already handles this internally — the mismatch between paths is the root of the confusion.

---

**[MAJOR] `pages/3_Spectral_Analysis.py:263-273` — Single-FFT PSD normalization omits window power correction factor.**

WHY: For the single-FFT path, the PSD tab normalizes as:

```python
norm = sample_rate * N
Sxx = 2.0 * ch_data[plot_chs[0]]["Gxx"] / norm
```

The correct one-sided PSD from a windowed FFT is `2 |X_win|² / (fs · W₂)` where `W₂ = Σ w[n]²` is the window power sum. The code uses `fs · N` instead of `fs · W₂`. For the uniform/boxcar window `W₂ = N` so there is no error. For the Hann window `W₂ ≈ 0.375 N`, causing a **+4.3 dB systematic error** in absolute PSD level. For Flat Top, the error is different again.

Note: the Welch path is correct because `scipy.signal.welch` applies the window correction internally.

FIX: Compute `W₂` from the actual window applied, and include it in the normalization. Since `compute_fft` returns the windowed FFT without exposing the window array, the simplest fix is to expose the window sum from `compute_fft` or recompute it in the PSD tab using `scipy.signal.get_window`.

---

**[MAJOR] `pages/5_MIMO.py:63-67` — Sample-rate mismatch between Run A and Run B issues a warning but does not block computation.**

WHY: When Run B has a sample rate more than 1% different from Run A, the page warns but allows the user to continue. FRF estimates from mismatched sample rates produce incorrect results with no further indication to the user. For a beta release this is a known-bad-data path that should be blocked, not just warned.

FIX: Call `st.stop()` after the mismatch warning, or add an explicit override checkbox that requires the user to acknowledge the risk.

```python
if fs_a is not None and abs(fs_b - fs_a) / (fs_a + 1e-9) > 0.01:
    st.error(
        f"Run B sample rate ({fs_b:.1f} Hz) differs from Run A ({fs_a:.1f} Hz) by more than 1 %. "
        "FRF estimates will be unreliable. Re-upload files with matching sample rates."
    )
    st.stop()
```

---

**[MAJOR] `docs/data_model.md` — Session-state key `oma_peak_estimates` is not documented.**

WHY: Per `docs/code_review.md` Step 1 and `CLAUDE.md`: every new session-state key must appear in `docs/data_model.md`. `oma_peak_estimates` is set in `pages/6_OMA.py:349`, read at lines 254-265, and cleared at line 350, but is absent from the session-state table in `docs/data_model.md`. This violates the documentation contract.

FIX: Add the following entry to the session-state table in `docs/data_model.md`:

| Key | Set by | Consumed by |
|---|---|---|
| `oma_peak_estimates` | `6_OMA.py` (Build) | `6_OMA.py` (Step 2 init) — list of dicts with `fn_hz`, `xi_pct`, `source` from FDD auto-peak detection |

---

**[MAJOR] `pages/4_SIMO.py:440` — Residue extraction uses the full-bandwidth H matrix, not the band-limited subset used to build the stability diagram.**

WHY: The stability diagram is built from `H_band` (frequency-band-limited) and poles are identified within `[f_min, f_max]`. But at Extract time:

```python
H_mat = st.session_state.get("si_H_mat")   # full frequency range
freqs  = st.session_state.get("si_freqs")  # full frequency range
residues = extract_residues(H_mat, freqs, poles)
```

The residue fit includes frequency content outside the analysis band, which adds noise and can attract residue energy to out-of-band features. NMSE is then computed over the full spectrum, which dilutes the quality metric with unmodelled regions.

FIX: Store `si_H_mat_band` and `si_freqs_band` separately (they're already stored at line 405 for reference) and use them in the Extract step. Add `si_H_mat_band` to `docs/data_model.md`.

---

### MINOR Issues

---

**[MINOR] `core/spectral.py:143` — Variable `Gyx` in `compute_welch_quantities` is named opposite to standard convention.**

WHY: `scipy.signal.csd(x, y)` returns `E[X* Y]`, which in standard modal-analysis notation is `G_xy` (input-conjugate × output). The code assigns this to `Gyx`. The math is correct (`H1 = Gyx/Gxx = E[X* Y]/Gxx` gives the right FRF), but a future maintainer reading `H1 = Gyx/Gxx` and knowing the formula `H1 = G_yx/G_xx = E[Y* X]/G_xx` will be confused. The same naming inconsistency exists in `compute_spectral_quantities`.

FIX: Rename the variable or add a clarifying comment that makes the convention explicit:

```python
# scipy csd(x,y) = E[X* Y] — labelled Gxy here; standard H1 = Gxy/Gxx
_, Gxy = csd(x, y, **kw)
Gyx = np.conj(Gxy)
H1 = Gxy / Gxx_safe    # H1 = Gxy/Gxx — minimises input noise
H2 = Gyy / np.where(np.abs(Gyx) > eps, Gyx, eps + 0j)
```

---

**[MINOR] `core/spectral.py:58-66` — `compute_spectral_quantities` produces `RuntimeWarning: overflow` and `invalid value` for zero-input signals (visible in test run).**

WHY: The test `test_compute_spectral_quantities_zero_input` passes but the test output shows:
- `RuntimeWarning: overflow encountered in divide` at line 61 (H2)
- `RuntimeWarning: invalid value encountered in multiply` at line 63 (Hv_mag)
- `RuntimeWarning: invalid value encountered in divide` at line 66 (gamma2)

When `Sx = 0`, `Gxy_safe = eps + 0j`, `H2 = Gyy / eps → inf`. Then `Hv_mag = sqrt(0 * inf) = NaN`. These propagate to the Streamlit display, potentially showing `inf` or `NaN` in plots.

FIX: Wrap the computation in `np.errstate(divide='ignore', invalid='ignore')` and explicitly clamp or fill NaN/inf outputs:

```python
with np.errstate(divide='ignore', invalid='ignore'):
    H2 = Gyy / Gxy_safe
    Hv_mag = np.sqrt(np.abs(H1) * np.abs(H2))
    ...
H2 = np.where(np.isfinite(H2), H2, 0.0)
Hv_mag = np.where(np.isfinite(Hv_mag), Hv_mag, 0.0)
```

---

**[MINOR] `pages/6_OMA.py:350` — Widget state is reset by popping a `data_editor` key from session state.**

WHY: `st.session_state.pop("oma_estimates", None)` clears the `st.data_editor(key="oma_estimates")` widget state to force re-initialisation. This is an undocumented Streamlit internal behaviour that may break across Streamlit versions, and can cause confusing rerun loops.

FIX: Use a separate explicit seed variable rather than clearing the widget key. For example, store `oma_peak_seed` and use it as `data_editor`'s `data` argument, regenerating the frame from the seed on each rerun.

---

**[MINOR] `pages/1_Time_History.py:81-97` — Channel-assignment widgets (`selectbox`, `multiselect`) lack explicit `key=` arguments.**

WHY: Without stable widget keys, Streamlit assigns keys by type + render index. If the page layout changes (e.g., new expander above the selectors), Streamlit can silently reset widget state or swap values between widgets.

FIX:
```python
input_ch = st.selectbox("Input channel", channels,
    index=..., key="th_input_channel")
output_chs = st.multiselect("Output channels", available_outputs,
    default=..., key="th_output_channels")
```

---

**[MINOR] `docs/data_model.md` — `mimo_file_a_name` and `mimo_file_b_name` reload-guard keys are not listed in the session-state table.**

WHY: Analogous keys `th_file_names`, `simo_file_name`, and `oma_file_name` are documented. The MIMO equivalents are absent, creating inconsistency in the reference.

FIX: Add entries to `docs/data_model.md`:

| Key | Set by | Consumed by |
|---|---|---|
| `mimo_file_a_name` | `5_MIMO.py` (load) | `5_MIMO.py` (re-load guard) |
| `mimo_file_b_name` | `5_MIMO.py` (load) | `5_MIMO.py` (re-load guard) |

---

**[MINOR] No `@st.cache_data` on expensive computations (Welch, stability table sweep).**

WHY: `build_stability_table` (sweeps up to 50 model orders with pLSCF solves) and `compute_output_spectral_matrix` (OMA CPSD) recompute on every Streamlit rerun unless the user presses a button. The pages guard against this by requiring explicit button presses, but a rerun triggered by any widget interaction (e.g., the frequency slider) clears the spinner and pauses the UI. For large datasets this is a UX issue.

FIX: For beta, the button-based manual caching is acceptable. Consider `@st.cache_data` on `compute_output_spectral_matrix` as a quick win for OMA with large files.

---

### NIT Items

---

**[NIT] `pages/7_MAC.py:188` — Bare `[]` access on `mac_fe_freqs` and `mac_exp_freqs`.**

WHY: `st.session_state["mac_fe_freqs"]` at line 188 uses direct access rather than `.get()`. Although guarded by the `if mac_matrix is None: st.stop()` at line 186, the pattern is inconsistent with project convention and fragile if the guard is ever removed.

FIX: `mac_fe_freqs = st.session_state.get("mac_fe_freqs", np.array([]))`

---

**[NIT] `core/sysid.py:8-12` — `compute_cmif` docstring says "first singular value" but computes Euclidean row norm.**

WHY: For a row vector, the Euclidean norm equals the singular value, so the result is correct for SIMO use. But the docstring is technically inaccurate and could mislead a developer extending the function to multi-reference inputs (MIMO uses `compute_mimo_cmif` which does the correct per-frequency SVD).

FIX: Update docstring: `"""H: (n_freqs, n_outputs) complex → (n_freqs,) L2 norm of each frequency row (≡ σ₁ for SIMO use)."""`

---

**[NIT] `pages/7_MAC.py:162` — MIMO MAC uses only Run A mode shapes with no UI indication.**

WHY: For MIMO results, the MAC page silently uses Run A shapes (`[:, 0, :]`) and discards Run B. This is not communicated to the user in the UI or in `docs/workflow_pages.md`.

FIX: Add a `st.caption("MAC uses Run A (symmetric/antisymmetric) mode shape amplitudes.")` after the MIMO source selector.

---

## 4. Test Suite Status

**`pytest tests/ -v` — 82 passed, 0 failed**

Warnings observed (non-fatal, but indicate defensive-coding gaps):
```
tests/test_spectral.py::test_compute_spectral_quantities_zero_input
  spectral.py:61: RuntimeWarning: overflow encountered in divide   (H2)
  spectral.py:63: RuntimeWarning: invalid value encountered in multiply  (Hv)
  spectral.py:66: RuntimeWarning: invalid value encountered in divide   (gamma2)
```
These are addressed under [MINOR] item above.

Notable coverage gaps:
- No test for FFT one-sided amplitude amplitude correctness (would catch [MAJOR] M1)
- No test for single-FFT PSD window normalization (would catch [MAJOR] M2)
- No security test for `add_channel` expression injection ([CRITICAL] C1)
- No test for MAC page complex-mode-shape handling ([CRITICAL] C3)

---

## 5. Security Checklist

| Check | Status |
|---|---|
| `pd.eval` engine="python" with user input | **FAIL** — no sanitization; see [CRITICAL] C1 |
| Analysis log path sanitization | **FAIL** — path traversal possible; see [CRITICAL] C2 |
| `pd.eval` local_dict exposes only DataFrame columns | PASS — no builtins explicitly added, but Python engine bypasses this |
| BDF file parser rejects malformed cards | PASS — `parse_wireframe_bdf` and `parse_f06` are tested in test_geometry.py and handle malformed lines gracefully |

---

## 6. Documentation Compliance Audit

| Document | Status |
|---|---|
| `docs/data_model.md` session-state table | **FAIL** — `oma_peak_estimates`, `mimo_file_a_name`, `mimo_file_b_name` missing |
| `docs/workflow_pages.md` algorithm descriptions | PASS — matches code |
| `docs/data_model.md` core API signatures | PASS — all `core/` signatures present and accurate |

---

## 7. Final Approval Gate

| Gate | Status |
|---|---|
| All [CRITICAL] resolved | **BLOCKED** — 2 critical items open (C1, C2) |
| All [MAJOR] resolved | **BLOCKED** — 5 major items open |
| `pytest tests/ -v` passes | ✓ 82/82 |
| `docs/data_model.md` up to date | **BLOCKED** — see M4, and MINOR items |
| No new [CRITICAL] introduced since last pass | N/A (first pass) |

**Merge verdict: BLOCKED — resolve all [CRITICAL] and [MAJOR] items before beta release.**

---

## 8. Issue Summary Table

| ID | Severity | File | Line | Short Description |
|---|---|---|---|---|
| C1 | CRITICAL | `tools/channel_math.py` | 54 | `pd.eval(engine="python")` — code injection via user expression |
| C2 | CRITICAL | `pages/1_Time_History.py` | 131 | Analysis log path traversal — `analysis_name` not sanitized |
| C3 | ~~CRITICAL~~ FIXED | `pages/7_MAC.py` | 162–164 | `np.real()` removed; complex mode shapes passed directly; regression test added |
| M1 | MAJOR | `core/spectral.py` | 35–37 | FFT one-sided amplitude not corrected (3 dB error in display) |
| M2 | MAJOR | `pages/3_Spectral_Analysis.py` | 263–273 | Single-FFT PSD missing window power correction (up to 4.3 dB error) |
| M3 | MAJOR | `pages/5_MIMO.py` | 63–67 | Sample-rate mismatch warned but not blocked |
| M4 | MAJOR | `docs/data_model.md` | — | `oma_peak_estimates` session key undocumented |
| M5 | MAJOR | `pages/4_SIMO.py` | 440 | Residue extraction uses full-span H not band-limited subset |
| N1 | MINOR | `core/spectral.py` | 143 | `Gyx`/`Gxy` variable naming reversed vs standard convention |
| N2 | MINOR | `core/spectral.py` | 58–66 | `RuntimeWarning` for zero-input (H2, Hv, gamma2) not suppressed |
| N3 | MINOR | `pages/6_OMA.py` | 350 | Widget key pop as state reset — fragile Streamlit internal |
| N4 | MINOR | `pages/1_Time_History.py` | 81–97 | Channel-assignment widgets missing explicit `key=` |
| N5 | MINOR | `docs/data_model.md` | — | `mimo_file_a_name`, `mimo_file_b_name` reload guards undocumented |
| N6 | MINOR | All pages | — | No `@st.cache_data` on expensive computations |
| T1 | NIT | `pages/7_MAC.py` | 188 | Bare `[]` session state access (guarded but pattern is inconsistent) |
| T2 | NIT | `core/sysid.py` | 8–12 | `compute_cmif` docstring says "singular value" — should say "row norm" |
| T3 | NIT | `pages/7_MAC.py` | 162 | MIMO MAC silently uses Run A shapes — not communicated in UI |
