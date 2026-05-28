# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [1.1.0] — 2026-05-28

### Added
- **Public Streamlit Community Cloud deployment** at <https://smodal-seanomeara.streamlit.app/> — README deploy badge included.
- **Landing-page caption** — one-sentence app description with a GitHub link for cold visitors.
- **Dev container** (`.devcontainer/`) for a one-click reproducible development environment.
- **Coherence quality gate** — γ² < 0.7 warning overlay on FRF / SIMO / MIMO / OMA pages so users know when input data quality is insufficient for reliable mode extraction.
- **Stability diagram guide** — expandable in-app table on SIMO and MIMO pages explaining glyph symbols: ★ fully stable, × frequency + damping stable, + frequency stable, ○ new/unclassified.
- **Model order sanity warning** — SIMO and MIMO pages alert when the selected max model order exceeds ¼ of the frequency lines in the analysis band, flagging overdetermined models that produce spurious computational poles.
- **Page-level smoke tests** — Streamlit `AppTest` suite covering all 9 pages; each test confirms the page loads, accepts sample data, and writes expected session-state keys.
- **UFF58 / UNV mode-shape export** — write measured mode shapes to Universal File Format for exchange with other structural dynamics tools.
- **Cantilever benchmark tutorial** — `docs/tutorial_cantilever.ipynb` provides an end-to-end worked example against a known analytic answer for workflow validation.
- **Reproducibility metadata in analysis log** — the saved JSON now records SHA-256 hashes of all input files and the versions of `smodal`, `numpy`, `scipy`, and `streamlit` used.
- **`.streamlit/config.toml`** settings tuned for the hosted deploy (`maxUploadSize`, telemetry disabled).

### Changed
- SIMO and MIMO EMA pages refactored to share a common chart module (`core/ema_charts.py`) and page-logic modules (`core/simo_page.py`, `core/mimo_page.py`). Eliminates the recurring failure mode where a fix landed in SIMO but was not propagated to MIMO.
- `pyproject.toml` development-status classifier updated from `3 - Alpha` to `4 - Beta`.
- README installation instructions corrected to the new repository name (`Sean074/smodal`).

### Fixed
- `core/sysid.py` — `except Exception` inside `build_stability_table` silently substituted unit-vector mode shapes when residue extraction failed, causing poles to be mis-classified as `stable_all` with no user warning. Now emits a `RuntimeWarning` and marks affected poles as unreliable. [P6-C1]
- `core/data_loader.py` — `compute_sample_rate` issued no warning when timestamp jitter exceeded 1%; now emits a `UserWarning` with the measured jitter percentage. [P6-M1]
- `core/geometry.py` — `_RE_FLOAT` regex rejected NASTRAN F06 floats with an unsigned exponent (e.g. `1.234E3`), silently resolving them to zero. Exponent sign is now optional. [P5-N1 / P6-M2]
- `pyproject.toml` — `E402` ruff ignore was applied project-wide; now scoped to `pages/*.py` and `app.py` where `st.set_page_config()` must precede other imports. [P5-N2 / P6-T1]
- Streamlit Community Cloud deploy failed when Poetry tried to install the project itself; added `[tool.poetry] package-mode = false` so Poetry resolves dependencies only.

---

## [1.0.0] — 2026-05-24

First public release.

### Added
- **Multi-page Streamlit GUI** — no scripting required to run an analysis.
- **Time history page** — CSV ingest, multi-file merge on the time column, channel assignment, time-window trim, Butterworth filtering, analysis log export (JSON).
- **FFT page** — windowed FFT with Gain/Phase or Real/Imaginary display.
- **Spectral analysis page** — auto/cross power, PSD, coherence, FRF estimators (H1, H2, Hv) in a tabbed layout.
- **SIMO EMA page** — single-reference pLSCF (PolyMAX) with stability diagram and pole extraction.
- **MIMO EMA page** — multi-reference pLSCF for symmetric/antisymmetric shaker runs.
- **OMA page** — output-only modal analysis via Frequency Domain Decomposition (FDD).
- **MAC page** — Modal Assurance Criteria matrix with optional FE F06 comparison.
- **Wireframe page** — 3-D Plotly visualisation of mode shapes driven by NASTRAN `GRID` / `PLOTEL` cards.
- **Method reference page** — in-app summary of the underlying analytical methods.
- **Sample dataset** — 3-channel CSV in `data/input/sample_3ch.csv`.
- **MIT licence** — see [LICENSE](LICENSE).
- **Package metadata** — `pyproject.toml` with name, version, author, dependencies.

### Known limitations
- No automated test coverage of `core/` modules. Planned for 1.1.0.
- Input-quality safeguards (FRF rank-deficiency warnings, spurious-pole flags) not yet implemented.

[Unreleased]: https://github.com/Sean074/smodal/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Sean074/smodal/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Sean074/smodal/releases/tag/v1.0.0
