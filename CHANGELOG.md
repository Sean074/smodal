# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- (Work in progress for the next release goes here.)

### Changed

### Fixed

### Removed

---

## [1.0.0] — TBD

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

[Unreleased]: https://github.com/Sean074/smodal/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Sean074/smodal/releases/tag/v1.0.0
