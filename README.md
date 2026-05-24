# smodal — Modal Analysis

A multi-page Streamlit app for structural dynamics modal analysis and experimental modal analysis (EMA). Supports SIMO and MIMO testing workflows through a browser-based GUI — no coding required to run an analysis.

**License:** MIT (see [LICENSE](LICENSE)) — free to use, modify, and redistribute, including commercially.

---

## Prerequisites

- Python 3.10 or later
- Git

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/Sean074/smodal.git
cd smodal

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -e ".[dev]"
```

---

## Running tests

```bash
source .venv/bin/activate        # if not already active
pytest tests/ -v
```

---

## Running the app

```bash
source .venv/bin/activate        # if not already active
streamlit run app.py
```

The app opens automatically in your default browser at `http://localhost:8501`.

---

## Sample data

A three-channel example dataset is included:

```
data/input/sample_3ch.csv
```

Upload it on the landing page to explore the full workflow without your own data.

---

## Workflow overview

| Step | Page | Purpose |
|---|---|---|
| 0 | Landing page | Analysis metadata |
| 1 | Time History | Trim time window, apply Butterworth filter |
| 2 | FFT | Inspect spectra |
| 3 | Spectral Analysis | Auto-power, PSD, FRFs (H1/H2/Hv), coherence |
| 4 | SIMO EMA | Single-shaker system identification (pLSCF) |
| 5 | MIMO EMA | Dual-shaker system identification (multi-reference pLSCF) |
| 6 | OMA | Output-only modal analysis (FDD) |
| 7 | MAC | Modal Assurance Criteria |
| 8 | Wireframe | 3-D mode shape visualisation |
| 9 | Methods | Analytical method reference |

Pages 1–3 feed into each other in sequence and can be used independently as QC tools. Pages 4 (SIMO), 5 (MIMO), and 6 (OMA) load CSV data directly and compute their own FRFs — Pages 1, 2, and 3 are not required for system identification.
---

## Documentation

| File | Contents |
|---|---|
| `docs/workflow_pages.md` | Page-by-page UI spec, controls, algorithms, session state |
| `docs/data_model.md` | Session state key table, core module API reference |
| `docs/algorithms.md` | Signal processing and system ID theory |
| `docs/methods.ipynb` | Worked Python examples |

---

## Author

Sean O'Meara — <sean.c.omeara74@gmail.com>

Bug reports and pull requests are welcome via the [GitHub issue tracker](https://github.com/Sean074/smodal/issues).

---

## Disclaimer

This application implements standard, well-published signal-processing and system-identification methods — FFT, H1/H2/Hv frequency-response estimators, polyreference Least-Squares Complex Frequency-domain (pLSCF / PolyMAX) pole extraction, Frequency Domain Decomposition (FDD), and the Modal Assurance Criterion (MAC) — using established numerical libraries (`numpy`, `scipy`).

It is intended as an educational and exploratory tool for structural dynamics work. Results are **not certified** for safety-critical analysis. Modal-identification quality depends heavily on input data quality (signal-to-noise ratio, excitation adequacy, sensor placement) and on user judgement when selecting stable poles. Always validate identified modes against engineering expectations and, where consequential, against an established commercial modal-analysis package.

The software is provided "as is", without warranty of any kind. See the [LICENSE](LICENSE) file for the full disclaimer of liability.

---

## License

Released under the [MIT License](LICENSE). Copyright (c) 2026 Sean O'Meara.

You are free to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software, subject to the conditions in the LICENSE file.
