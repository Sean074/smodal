# Development Roadmap — smodal

## Milestone v1.1.0 — Trustworthy results ✓ SHIPPED 2026-05-28

**Goal:** The app stops lying to users. Every result the UI surfaces is either correct or accompanied by a visible warning.

| # | Item | Status |
|---|---|---|
| 1 | Fix P6-C1: `except Exception` in `build_stability_table` silently substitutes unit-vector mode shapes | ✓ DONE (`e408d01`) |
| 2 | Coherence quality gate: overlay γ² < 0.7 bands on FRF/SIMO/MIMO/OMA pages | ✓ DONE |
| 3 | Page-level smoke tests (Streamlit `AppTest`) for all 9 pages | ✓ DONE — 146 tests pass |
| 4 | Stability diagram: in-app legend / tooltip for glyph symbols | ✓ DONE |

Also completed in this cycle (pulled forward from v1.2.0 and backlog):

| Item | Status |
|---|---|
| 2-DOF cantilever tutorial notebook (`docs/tutorial_cantilever.ipynb`) | ✓ DONE |
| UFF58 / UNV mode-shape export writer | ✓ DONE |
| Reproducibility metadata in analysis log (file hashes, library versions) | ✓ DONE |
| Refactor shared SIMO/MIMO logic into `core/ema_charts.py` / `core/simo_page.py` / `core/mimo_page.py` | ✓ DONE |
| Model order sanity warning (max order > n\_freq\_lines / 4) | ✓ DONE |
| `pyproject.toml` classifier → `4 - Beta` | ✓ DONE |

---

## Milestone v1.2.0 — Production quality

**Goal:** Harden the app for real engineering workflows: CI regression suite, stricter input validation, and a path toward `5 - Production/Stable`.

| # | Item | Notes |
|---|---|---|
| 1 | CI numerical regression against cantilever benchmark | Run the tutorial notebook headlessly in CI; assert fn/ξ within tolerance — catches `core/` regressions that smoke tests miss |
| 2 | FRF rank-deficiency warning on MIMO page | Warn when the FRF matrix is nearly singular before running pLSCF |
| 3 | Spurious-pole flag heuristic | Flag poles with damping > 10% or < 0% as likely computational |
| 4 | Promote PyPI classifier to `5 - Production/Stable` | After CI regression suite is in place |

## Backlog (no milestone)

| Item | Notes |
|---|---|
| Multi-run averaging for OMA | Ensemble-average CPSD across repeated ambient runs |
| Mode shape animation on wireframe page | Animate deformed shape at each extracted frequency |
