# Code Review Process — Modal Analysis Application

Authoritative process guide for critical code review in this repository.  
All reviews **must** be critical: identify potential defects, non-conformance to documentation,
and deviations from engineering best practice — not just style.

---

## 1. Objectives

A code review in this project must verify:

| Objective | Why it matters |
|---|---|
| **Correctness** | Signal-processing errors produce silently wrong modal results |
| **Documentation conformance** | CLAUDE.md mandates docs stay in sync with every code change |
| **Session-state contract** | Pages communicate exclusively through `st.session_state`; broken contracts break the workflow silently |
| **Numerical validity** | Scientific computing bugs often surface only for edge-case data |
| **Security** | `pd.eval` with user input is an injection surface |
| **Maintainability** | Future analysts will modify this codebase; debt compounds |

---

## 2. Pre-Review Checklist

Complete before reading a single line of diff:

- [ ] Read the PR description / commit message — understand the *intent*, not just the change.
- [ ] Read the relevant section of `docs/workflow_pages.md` for any page touched.
- [ ] Read `docs/data_model.md` for any session-state key or core-module function touched.
- [ ] Confirm the diff includes documentation updates (`docs/`) if code changed. Flag immediately if absent.
- [ ] Check `todo.md` — does this PR close a known bug, or introduce a pattern already flagged there?
- [ ] Confirm tests exist for new or changed functions in `core/` or `tools/`.
- [ ] Identify any `core/` module functions whose signatures or return shapes changed — these are high-blast-radius changes.

---

## 3. Review Process (Ordered Steps)

### Step 1 — Documentation Compliance Audit

**Non-negotiable per CLAUDE.md**: every code change must update `docs/` in the same session.

Check:

- `docs/data_model.md` — any new or removed `st.session_state` key must appear in the session-state table with correct owner and consumer pages.
- `docs/data_model.md` — any changed function signature (name, args, return type/shape) in `core/` or `tools/` must be reflected.
- `docs/workflow_pages.md` — any UI control added, removed, or renamed must be reflected in the relevant page section.
- `docs/workflow_pages.md` — algorithm changes (windowing, FRF estimator, etc.) must update the documented algorithm description.

**Raise as CRITICAL** if documentation was not updated. Do not approve the PR until docs are in sync.

---

### Step 2 — Session-State Contract Verification

All inter-page state flows through `st.session_state`. Review every key touched:

- Is the key listed in `docs/data_model.md`? If a new key is introduced without a doc entry, reject.
- Does the *setting page* match the documented owner?
- Does the *consuming page* guard with `.get()` before access? Bare `st.session_state["key"]` without a guard raises `KeyError` when the user navigates out of order.
- Are numpy array shapes correct? Check documented shapes (e.g., `si_cmif` is `(n_freqs, 2)`, `oma_sv` is `(n_freqs, n_out)`) against what the code actually produces.
- Is any key deleted or renamed without updating all consuming pages?

---

### Step 3 — Correctness and Algorithm Review

For `core/` modules, verify implementation against the documented algorithms in `docs/methods.ipynb` and `docs/algorithms.md`.

**FFT / Spectral (`core/spectral.py`)**

- [ ] Window normalization: amplitude-correct vs. power-correct scaling must match the intended estimator.
- [ ] One-sided spectrum: verify factor-of-2 correction is applied to non-DC, non-Nyquist bins.
- [ ] Overlap averaging: confirm segment count, overlap fraction, and Welch normalization.
- [ ] FRF estimators: H1 = Gyx/Gxx, H2 = Gyy/Gxy, Hv (Geometric mean) — verify sign conventions and which is appropriate for noise assumptions.
- [ ] Coherence: must be bounded [0, 1]; check for divide-by-zero when Gxx or Gyy ≈ 0.

**System Identification (`core/sysid.py`, pages 4 & 5)**

- [ ] LSCF/PolyMAX companion matrix construction — verify dimension ordering (rows = outputs × model order).
- [ ] Pole stability criteria: frequency tolerance, damping tolerance, and mode shape (MAC) threshold must match documented criteria.
- [ ] Complex mode normalization: unit modal mass or unity magnitude — must be consistent with what `7_MAC.py` expects.
- [ ] Damping ratio sign: positive damping = stable system; negative damping flags a diverging solution.

**OMA (`core/` / `pages/6_OMA.py`)**

- [ ] FDD singular value decomposition: check that `np.linalg.svd` is called with `full_matrices=False` and the result shape matches `oma_sv` / `oma_svecs` documented shapes.
- [ ] NMSE interpolation: confirm peak-picking frequency resolution is not coarser than the FFT frequency step.

**MAC (`pages/7_MAC.py`)**

- [ ] MAC formula: `|phi_r^H phi_s|^2 / (phi_r^H phi_r)(phi_s^H phi_s)` — verify conjugate-transpose vs. transpose usage (complex mode shapes require `H`, not `T`).
- [ ] Cross-method MAC: confirm mode-shape vectors from SIMO, MIMO, OMA are length-compatible before comparison.

---

### Step 4 — Security Review

**High priority — `tools/channel_math.py`**

`pd.eval(expression, engine="python")` with user-supplied `expression` executes arbitrary Python.

Check:

- [ ] Is the expression sanitized before `pd.eval`? Current code has no allowlist or syntax check — this is a known risk.
- [ ] Is the `engine="python"` argument necessary? The `numexpr` engine is safer and faster for arithmetic.
- [ ] Are only DataFrame column names exposed in `local_dict`? No builtins, `os`, `subprocess`, or `__import__` should be reachable.
- [ ] Is the result type checked? A user could return a non-numeric Series, breaking downstream operations.

**File I/O**

- [ ] Analysis log paths: `data/output/<analysis_name>_log.json` — is `analysis_name` sanitized against path traversal (`../`, absolute paths)?
- [ ] BDF file parsing (`core/geometry.py`): does the parser reject or skip malformed GRID/PLOTEL cards without crashing?

---

### Step 5 — Error Handling and Robustness

- [ ] Every function that can fail on bad input must return an error signal — not raise an unhandled exception to the Streamlit UI. The `(result, error)` tuple pattern in `tools/channel_math.py` is the project convention; verify new functions follow it.
- [ ] Divide-by-zero: check all spectral divisions (H1, H2, coherence, FDD normalization) for `np.errstate` guards or small-epsilon denominators.
- [ ] Empty data: what happens when a user uploads a single-column CSV (no response channels)? Trace through `core/data_loader.py` and page 1.
- [ ] NaN/Inf propagation: numpy operations on NaN-containing arrays silently produce NaN results. Verify upstream data validation catches bad sensor channels before they enter spectral computation.
- [ ] Type coercion: `pd.DataFrame` columns may be `object` dtype if the CSV parser fails to infer floats. Confirm numeric dtype is enforced after load.

---

### Step 6 — Streamlit-Specific Review

- [ ] `st.cache_data` / `st.cache_resource` — are expensive computations (FFT, spectral averaging, LSCF build) cached? Repeated reruns on large datasets without caching is a UX failure.
- [ ] Widget keys — every interactive widget (`st.slider`, `st.selectbox`, etc.) that persists state must have a unique, stable `key=` argument. Missing or duplicate keys cause Streamlit to silently reset or collide widget state.
- [ ] Re-load guards — the pattern `if st.session_state.get("th_file_names") != uploaded_names` prevents re-processing on every rerun. Verify new file-upload blocks use the same guard.
- [ ] Page navigation side-effects — pages must not mutate session-state keys owned by *other* pages. A page 3 function writing to `si_stability_table` is a contract violation.
- [ ] `st.stop()` / early returns — pages that depend on upstream state (e.g., page 2 needs `df`) must call `st.stop()` after displaying the warning, not fall through to broken computation.

---

### Step 7 — Numerical and Scientific Code Standards

These are engineering-code-specific checks beyond standard software review:

- [ ] **Units are explicit**: variable names or docstrings must state the unit (`fs_hz`, `freq_rad_s`, `damping_ratio`, not bare `w` or `d`).
- [ ] **Array axis conventions are documented**: when a function returns a multi-dimensional array, the docstring must state what each axis represents (e.g., `shape (n_freqs, n_outputs, n_inputs)`).
- [ ] **No silent broadcasting errors**: numpy broadcasting between `(n,)` and `(n,1)` arrays can produce unexpected `(n,n)` results. Verify shapes are explicit where ambiguity exists.
- [ ] **Numerical conditioning**: matrix inversions in FRF computation should use `np.linalg.lstsq` or `np.linalg.solve` — never `np.linalg.inv(A) @ b`, which is numerically unstable and slower.
- [ ] **Physical reasonableness**: modal frequencies must be positive real; damping ratios should be in (0, 1) for typical structures. Hard-coded bounds or assertions are acceptable guards.
- [ ] **Windowing amplitude correction**: assert the window sum (for power) or peak (for amplitude) is applied consistently across FFT and averaging functions.

---

### Step 8 — Code Quality and Maintainability

- [ ] **Type hints**: all `core/` and `tools/` functions must have complete type annotations. `Any` is acceptable only for numpy arrays (`np.ndarray`); bare `list` or `dict` should be parameterized.
- [ ] **Docstrings**: public functions must have a one-line summary, args/returns description, and shape annotations for array parameters. Minimal inline comments only where the *why* is non-obvious.
- [ ] **Function length**: functions longer than ~60 lines should be decomposed. A single function doing data load + validation + computation + plotting is a design defect.
- [ ] **No magic numbers**: frequency bands, model order limits, stability thresholds must be named constants or parameters — not bare literals embedded in expressions.
- [ ] **No mutable default arguments**: `def f(x, results=[])` is a Python antipattern; flag any occurrence.
- [ ] **Import hygiene**: `core/` modules must not import from `pages/`; `tools/` must not import from `core/`. The dependency graph is: `pages → core`, `pages → tools`, `core ↔ core` (minimal), `tools` standalone.

---

### Step 9 — Test Coverage

- [ ] New `core/` functions must have a corresponding test in `tests/`.
- [ ] Tests must cover the happy path **and** at least one invalid-input case (wrong shape, empty array, bad dtype).
- [ ] Spectral/modal tests should compare against analytically known results (e.g., single-tone FFT, two-DOF system with known poles) — not just "no exception raised".
- [ ] `core/spectral.py` changes must not break `tests/test_spectral.py`; run `pytest tests/ -v` and include pass/fail status in the review.
- [ ] `tools/` changes must have corresponding tests in `tests/test_tools.py`.

---

## 4. Issue Severity Classification

| Severity | Label | Criteria | Required action |
|---|---|---|---|
| **Critical** | `[CRITICAL]` | Produces wrong results, data loss, security vulnerability, documentation not updated | Block merge — must fix |
| **Major** | `[MAJOR]` | Unhandled exception path, broken session-state contract, missing test for new logic | Block merge — must fix or explicitly justify |
| **Minor** | `[MINOR]` | Type hint missing, magic number, suboptimal but correct algorithm | Non-blocking — fix in this PR or open follow-up |
| **Nit** | `[NIT]` | Style, naming, comment wording | Optional |

---

## 5. Common Defect Patterns in This Codebase

Based on the architecture, watch specifically for:

| Pattern | Where to look | Risk |
|---|---|---|
| `st.session_state["key"]` without `.get()` | All pages | `KeyError` on out-of-order navigation |
| `np.fft.rfft` result used without one-sided correction | `spectral.py`, page 2 | 3 dB amplitude error |
| `pd.eval(..., engine="python")` with unsanitized input | `tools/channel_math.py`, page 1 | Code injection |
| `np.linalg.inv(A)` used for linear solve | `sysid.py`, `mimo.py` | Numerical instability for ill-conditioned FRF matrices |
| Missing `st.stop()` after guard warning | Pages 2–8 | Silent crash on missing upstream data |
| Session-state shape mismatch vs. documented shape | Pages 4–6 | Wrong modal extraction silently |
| Analysis log path not sanitized | Page 1 | Path traversal write |
| New key written to `st.session_state` without `docs/data_model.md` update | Any page | Documentation drift |

---

## 6. Review Output Format

Every review finding must be written as:

```
[SEVERITY] file.py:line_number — Short description of the issue.
WHY: Explain the defect or risk in one sentence.
FIX: Concrete suggestion (code snippet if helpful).
```

Example:

```
[CRITICAL] pages/2_FFT.py:87 — One-sided FFT amplitude is not corrected by factor 2.
WHY: np.fft.rfft returns half-spectrum bins that are half-amplitude relative to the full signal power.
FIX: Multiply fft_complex[1:-1] by 2 before computing magnitude, or use the amplitude_correction helper in core/spectral.py.
```

---

## 7. Final Approval Gate

A PR may be approved **only** when:

- [ ] All `[CRITICAL]` and `[MAJOR]` items are resolved or explicitly accepted with documented justification.
- [ ] `pytest tests/ -v` passes with no failures.
- [ ] `docs/data_model.md` and `docs/workflow_pages.md` are up to date.
- [ ] No new `[CRITICAL]` items introduced since last review pass.

---

## 8. References

| Resource | Purpose |
|---|---|
| `docs/data_model.md` | Session-state key ownership and core module API |
| `docs/workflow_pages.md` | Page-level UI spec and algorithm descriptions |
| `docs/algorithms.md` | Signal processing algorithm derivations |
| `docs/methods.ipynb` | Worked numerical examples (ground truth for algorithm review) |
| `CLAUDE.md` | Project conventions, commands, and documentation requirement |
| `todo.md` | Known bugs and deferred work |
| IEEE 1012-2016 | Software verification and validation standard |
| NASEM "Assessing the Reliability of Complex Models" | Numerical model V&V for scientific computing |
