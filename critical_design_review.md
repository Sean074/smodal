# Critical Design Review — Modal Analysis Application

---

## v1.0.x History (Passes 1–5) — Condensed

All items below were identified across five review passes on branch `mac_dev` ending 2026-05-24.
Test suite at close of Pass 5: **103 passed, 0 failed**.

| ID | Severity | File | Short Description | Final Status |
|---|---|---|---|---|
| C1 | CRITICAL | `tools/channel_math.py` | `pd.eval(engine="python")` code injection via user expression | FIXED |
| C2 | CRITICAL | `pages/1_Time_History.py:134` | Analysis log path traversal — `analysis_name` not sanitized | FIXED |
| C3 | CRITICAL | `pages/7_MAC.py:164` | `np.real()` stripped imaginary part of mode shapes before MAC | FIXED |
| M1 | MAJOR | `core/spectral.py:38` | One-sided FFT amplitude 3 dB error | FIXED |
| M2 | MAJOR | `pages/3_Spectral_Analysis.py:285` | Single-FFT PSD window power correction missing | FIXED |
| M3 | MAJOR | `pages/5_MIMO.py:68` | MIMO sample-rate mismatch warned but not blocked | FIXED |
| M4 | MAJOR | `docs/data_model.md` | `oma_peak_estimates` session key undocumented | FIXED |
| M5 | MAJOR | `pages/4_SIMO.py:443` | Residue extraction used full-span H not band-limited subset | FIXED |
| P3-M1 | MAJOR | `pages/5_MIMO.py:536` | MIMO residue extraction used full-range arrays (M5 not propagated from SIMO) | FIXED |
| P3-M2 | MAJOR | `pages/5_MIMO.py:529` | Ill-conditioning check compared full-range freq count, always passed | FIXED |
| N1 | MINOR | `core/spectral.py:61` | `Gyx`/`Gxy` variable naming reversed | FIXED |
| N2 | MINOR | `core/spectral.py:69` | `RuntimeWarning` for zero-input (H2, Hv, gamma2) | FIXED |
| N3 | MINOR | `pages/6_OMA.py:297` | Widget key pop as state reset in OMA page | FIXED |
| N4 | MINOR | `pages/1_Time_History.py:87` | Channel-assignment widgets missing explicit `key=` | FIXED |
| N5 | MINOR | `docs/data_model.md` | `mimo_file_a_name`, `mimo_file_b_name` undocumented | FIXED |
| N6 | MINOR | `core/spectral.py:96` | No `@st.cache_data` on expensive spectral computations | FIXED |
| NW1 | MINOR | `docs/data_model.md:137` | `add_channel` description said "Python engine" only | FIXED |
| NW2 | MINOR | `docs/data_model.md` | 7 page-7 session-state keys (`mac_*`) undocumented | FIXED |
| P3-N1 | MINOR | `pages/3_Spectral_Analysis.py:352` | Cross-power phase sign-inverted after Gxy/Gyx rename | FIXED |
| P3-N2 | MINOR | `pages/3_Spectral_Analysis.py:268` | `N = 2*(len(freqs)−1)` gave wrong FFT length for odd-length signals | FIXED |
| P3-N3 | MINOR | `core/sysid.py:394` | `fdd_damping` overestimated damping when peak at last index | FIXED |
| P3-N4 | MINOR | `core/sysid.py:313` | `RuntimeWarning` from `extract_residues` not surfaced to UI | FIXED |
| T1 | NIT | `pages/7_MAC.py:190` | Bare `[]` session state access on `mac_fe_freqs` | FIXED |
| T2 | NIT | `core/sysid.py:8` | `compute_cmif` docstring said "singular value" | FIXED |
| T3 | NIT | `pages/7_MAC.py:157` | MIMO MAC silently used Run A shapes | FIXED |
| NW3 | NIT | `pages/7_MAC.py:79` | Bare `[]` access on `mimo_modal_results`/`modal_results` | FIXED |
| P4-N1 | MINOR | `core/mimo.py:43` | Latent `NameError` when `sel_outputs=[]` in Welch branch | CLOSED (pre-existing fix) |
| P4-N2 | NIT | `docs/data_model.md` | `mimo_frf_est_used` session key missing from table | FIXED |
| P5-N1 | MINOR | `core/geometry.py:276` | `_RE_FLOAT` regex drops F06 floats with unsigned exponent (e.g., `1.234E3`) | FIXED (Pass 6 as P6-M2) |
| P5-N2 | NIT | `pyproject.toml:56` | `E402` ruff ignore project-wide instead of scoped to `pages/` | FIXED (Pass 6 as P6-T1) |
| P6-C1 | CRITICAL | `core/sysid.py:246` | `except Exception` silently substitutes unit-vector mode shapes on residue-extraction failure | FIXED (`e408d01`) |
| P6-M1 | MINOR | `core/data_loader.py:54` | `compute_sample_rate` comment says "warn" on >1% jitter but body was `pass` | FIXED |
| P6-M2 | MINOR | `core/geometry.py:276` | `_RE_FLOAT` regex requires explicit exponent sign (carried from P5-N1) | FIXED |
| P6-T1 | NIT | `pyproject.toml:56` | `E402` ruff ignore project-wide (carried from P5-N2) | FIXED |
| P6-T2 | NIT | `pyproject.toml` | `Development Status :: 3 - Alpha` conflicts with v1.0.0 | FIXED (→ `4 - Beta`) |

---

## Pass 6 — `development_v1.1.0`

**Date:** TBD
**Branch:** `development_v1.1.0`
**Base test result:** 103 passed, 0 failed (inherited from Pass 5 on `main`)
**Review standard:** `docs/code_review.md`

### Pre-Review Checklist

| Item | Status |
|---|---|
| Read relevant `docs/workflow_pages.md` sections | ✓ |
| Read `docs/data_model.md` | ✓ |
| Confirm docs updated with code changes | ✓ (pending P6-C1 fix) |
| Check `todo.md` — known bugs | ✓ |
| Confirm tests exist for new/changed `core/` functions | ✓ — 146 tests pass |
| Identify high-blast-radius `core/` signature changes | ✓ — none |

---

### CRITICAL Issues

---

~~**[P6-C1] `core/sysid.py:246` — `except Exception` silently substitutes unit-vector mode shapes on residue-extraction failure**~~

FIXED (`e408d01`): inner `except Exception` now emits a `RuntimeWarning` and sets `mshapes = None`; the
stability classifier treats `None` shapes as `"new"` for all poles at that order. Outer catch also
emits a `RuntimeWarning` and appends an empty-poles entry rather than swallowing the failure silently.

---

### MINOR Issues

---

~~**[P6-M1] `core/data_loader.py:54` — `compute_sample_rate` comment says "warn" on >1% jitter but body is `pass`**~~

FIXED: replaced `pass` with `warnings.warn(...)` emitting `UserWarning` with jitter percentage. `warnings` import added.

---

~~**[P6-M2] `core/geometry.py:276` — `_RE_FLOAT` regex requires explicit exponent sign (carried from P5-N1)**~~

FIXED: added `?` to `[+-]` before the exponent digits → `[Ee][+-]?\d+`. NASTRAN floats with
unsigned exponents (e.g. `1.234E3`) now parse correctly instead of silently resolving to zero.

---

### NIT Issues

---

~~**[P6-T1] `pyproject.toml:56` — `E402` ruff ignore project-wide (carried from P5-N2)**~~

FIXED: removed `E402` from global `ignore`; added `[tool.ruff.lint.per-file-ignores]` scoping it to
`pages/*.py` and `app.py`. Seven pre-existing F401/I001 violations auto-fixed by `ruff --fix`.
146 tests pass.

---

~~**[P6-T2] `pyproject.toml` — `Development Status :: 3 - Alpha` conflicts with `version = "1.0.0"`**~~

FIXED: updated classifier to `Development Status :: 4 - Beta` on `development_v1.1.0`.
Update to `5 - Production/Stable` when v1.1.0 ships.

---

### Final Approval Gate — Pass 6

| Gate | Status |
|---|---|
| All [CRITICAL] resolved | ✓ — P6-C1 fixed (`e408d01`) |
| All [MAJOR] resolved | ✓ |
| `pytest tests/ -v` passes | ✓ — 146 passed |
| `docs/data_model.md` up to date | ✓ |
| No new [CRITICAL] introduced since last review pass | ✓ |

**Pass 6 verdict: APPROVED — all issues resolved. Ready for merge to `main` as v1.1.0.**
