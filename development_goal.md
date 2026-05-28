# Development Roadmap — smodal

## Milestone v1.1.0 — Trustworthy results

**Goal:** The app stops lying to users. Every result the UI surfaces is either correct or accompanied by a visible warning.

| # | Item | Notes |
|---|---|---|
| 1 | Fix P6-C1: `except Exception` in `build_stability_table` silently substitutes unit-vector mode shapes | Blocker — see CDR Pass 6 |
| 2 | Coherence quality gate: overlay γ² < 0.7 bands on FRF/SIMO/MIMO/OMA pages | Biggest predictor of "did I get a real mode"; also the most instructive signal for students |
| 3 | Page-level smoke tests (Streamlit `AppTest`) for all 9 pages | Target: each page loads, accepts data, writes expected session-state keys — catches ~80% of page-layer regressions |
| 4 | Stability diagram: in-app legend / tooltip for `stable_all` / `stable_fd` / `stable_f` / `new` glyphs | Without this, students guess; combined with P6-C1, they guess wrong |

## Milestone v1.2.0 — Usable by engineers

**Goal:** Results leave the app. Users can validate their workflow against a known answer and hand results to other tools.

| # | Item | Notes |
|---|---|---|
| 5 | 2-DOF analytic reference dataset: known fn, ξ, mode shape documented; tutorial notebook runs end-to-end against it | Doubles as a numerical regression fixture in CI |
| 6 | Mode export: CSV + UFF/UNV writer | Right now results live only in `st.session_state`; export turns smodal into a step in a workflow |
| 7 | Reproducibility metadata in analysis log: input file hash, app version, library versions | Engineers using real data need this; students don't, so it's v1.2 not v1.1 |

## Backlog (no milestone)

| Item | Notes |
|---|---|
| Refactor shared SIMO/MIMO logic into `core/ema_pipeline.py` | Eliminates the recurring "fix landed in SIMO but not MIMO" failure mode (see P3-M1, P3-M2) |
| Sanity bounds: warn when model order > n_freq\_lines / 4 | A 60th-order pLSCF on 30 freq lines is nonsense; the app accepts it silently |
| Promote PyPI classifier to `5 - Production/Stable` | When v1.1.0 ships — see `pyproject.toml` note in CDR P6-T2 |
