# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run the app
streamlit run app.py

# Install dependencies
pip install -r requirements.txt
```

Run tests with `pytest tests/ -v` (requires `source .venv/bin/activate`).

## Documentation requirement

When ANY code changes are made, update the relevant file(s) in `docs/` in the same session.
Never defer documentation. `docs/workflow_pages.md` is the authoritative page-level UI spec;
`docs/data_model.md` is the authoritative session state and core module API reference.

## Architecture

This is a multi-page **Streamlit** app for structural dynamics modal analysis / system identification.

### Page flow

`app.py` is the landing page (Streamlit entry point). The numbered files in `pages/` are loaded automatically by Streamlit in sidebar order:

| File | Purpose | Status |
|---|---|---|
| `app.py` | Landing page — analysis metadata (name, analyst, description) and workflow overview | Implemented |
| `pages/1_Time_History.py` | Load CSV data, assign channels, time history plots, trim range, Butterworth filtering, save analysis log | Implemented |
| `pages/2_FFT.py` | FFT with windowing options, Gain/Phase or Real/Imaginary display | Implemented |
| `pages/3_Spectral_Analysis.py` | Auto/cross power, PSD, coherence, FRF (H1, H2, Hv) — tabbed layout | Implemented |
| `pages/4_SIMO.py` | System Identification — SIMO EMA (stability diagram, mode extraction) | Implemented |
| `pages/5_MIMO.py` | MIMO EMA — multi-reference pLSCF (PolyMAX) | Implemented |
| `pages/6_OMA.py` | Operational Modal Analysis — FDD (output-only, no force) | Implemented |
| `pages/7_MAC.py` | Modal Assurance Criteria plot | Implemented |
| `pages/8_Wireframe.py` | 3-D wireframe mode shape visualisation | Implemented |
| `pages/9_Method.py` | Analysis method reference | Implemented |

`todo.md` tracks known bugs and development notes.

### Shared state

See `docs/data_model.md` for the full session-state key table and core module API reference.

### Input data format

CSV files must have one time column (`time`, `Time`, `TIME`, `t`, or `T` — or a numeric monotonically increasing first column) plus one or more channel columns. Multiple CSVs can be uploaded simultaneously and are merged on the `time` column (inner join). Sample data: `data/input/sample_3ch.csv`.

Analysis logs are written as JSON to `data/output/<analysis_name>_log.json`.

### Page details

Full UI spec, controls, algorithms, and session state per page are in `docs/workflow_pages.md`. Worked signal-processing examples with runnable code are in `docs/methods.ipynb`.

### Wireframe geometry (page 8)

Page 8 parses NASTRAN BDF-format ASCII files containing `GRID` (point geometry in global coordinate system CP 0) and `PLOTEL` (two-point connectivity) cards to drive a 3-D Plotly visualisation of mode shapes.
