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
| P5-N2 | NIT | `pyproject.toml:56` | `E402` ruff ignore project-wide instead of scoped to `pages/` | **OPEN → carried to Pass 6** |

---

## Pass 6 — `development_v1.1.0`

**Date:** TBD
**Branch:** `development_v1.1.0`
**Base test result:** 103 passed, 0 failed (inherited from Pass 5 on `main`)
**Review standard:** `docs/code_review.md`

### Pre-Review Checklist

| Item | Status |
|---|---|
| Read relevant `docs/workflow_pages.md` sections | Pending |
| Read `docs/data_model.md` | Pending |
| Confirm docs updated with code changes | Pending |
| Check `todo.md` — known bugs | C1, P5-N1, M1 open (see below) |
| Confirm tests exist for new/changed `core/` functions | Pending |
| Identify high-blast-radius `core/` signature changes | Pending |

---

### CRITICAL Issues

---

**[P6-C1] `core/sysid.py:246` — `except Exception` silently substitutes unit-vector mode shapes on residue-extraction failure**

WHY: When `extract_residues` raises inside `build_stability_table`, the `except Exception` at line 246
returns `np.ones((len(poles), H.shape[1]), dtype=complex)` — unit vectors — as mode shapes. The outer
`except Exception` at line 250 additionally swallows whole-order pole-finding failures with no warning.
Both are broad catches; neither logs, warns, or marks affected poles as unreliable.

Consequence: MAC-based stability classification (`stable_all` vs `stable_fd`) runs against fabricated
unit shapes. Poles that should be classified `new` or `stable_fd` may be promoted to `stable_all`
silently. The user sees a stability diagram they cannot trust, with no indication anything went wrong.

FIX (line 246 inner catch):
```python
except Exception as exc:
    warnings.warn(
        f"Residue extraction failed for order {n}: {exc} — poles marked unreliable",
        RuntimeWarning,
        stacklevel=2,
    )
    mshapes = None  # Signal downstream classifier to mark these poles as 'new'
```
Then update the stability classifier to treat `mshapes is None` as `stability = "new"` for all poles
at that order.

FIX (line 250 outer catch):
```python
except Exception as exc:
    warnings.warn(
        f"Pole-finding failed for order {n}: {exc} — order skipped",
        RuntimeWarning,
        stacklevel=2,
    )
    results.append({"order": n, "poles": np.array([]), ...})
```

---

### MINOR Issues

---

**[P6-M1] `core/data_loader.py:54` — `compute_sample_rate` comment says "warn" on >1% jitter but body is `pass`**

WHY: Comment at line 52 reads "More than 1% jitter — warn but still return estimate". The body is
`pass`. Engineers with non-uniform or resampled data get no indication their sample rate estimate
may be degraded. Downstream spectral analysis (FFT bin spacing, Welch window length) uses this
estimate without qualification.

FIX:
```python
if dt_std / dt_mean > 0.01:
    warnings.warn(
        f"Sample rate jitter {dt_std / dt_mean:.1%} exceeds 1% — "
        "sample rate estimate may be inaccurate",
        UserWarning,
        stacklevel=2,
    )
```

---

~~**[P6-M2] `core/geometry.py:276` — `_RE_FLOAT` regex requires explicit exponent sign (carried from P5-N1)**~~

FIXED: added `?` to `[+-]` before the exponent digits → `[Ee][+-]?\d+`. NASTRAN floats with
unsigned exponents (e.g. `1.234E3`) now parse correctly instead of silently resolving to zero.

---

### NIT Issues

---

**[P6-T1] `pyproject.toml:56` — `E402` ruff ignore project-wide (carried from P5-N2)**

FIX:
```toml
[tool.ruff.lint.per-file-ignores]
"pages/*.py" = ["E402"]
"app.py" = ["E402"]
```
Remove `E402` from the global `ignore` list.

---

**[P6-T2] `pyproject.toml` — `Development Status :: 3 - Alpha` conflicts with `version = "1.0.0"`**

FIX: Update to `Development Status :: 4 - Beta` on current branch;
update to `5 - Production/Stable` when v1.1.0 ships.

---

### Final Approval Gate — Pass 6

| Gate | Status |
|---|---|
| All [CRITICAL] resolved | Pending |
| All [MAJOR] resolved | Pending |
| `pytest tests/ -v` passes | Pending |
| `docs/data_model.md` up to date | Pending |
| No new [CRITICAL] introduced since last review pass | Pending |

| P6-C1 | ~~CRITICAL~~ FIXED | `core/sysid.py:246,250` | `except Exception` silently substituted unit-vector mode shapes; outer except swallowed order failures silently | FIXED — zeros substituted; both sites emit `RuntimeWarning`; `_residue_warn_count` incremented |

**Pass 6 verdict: IN PROGRESS**
