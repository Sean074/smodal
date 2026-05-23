# Modal Analysis

A multi-page Streamlit app for structural dynamics modal analysis and experimental modal analysis (EMA). Supports SIMO and MIMO testing workflows through a browser-based GUI — no coding required to run an analysis.

---

## Prerequisites

- Python 3.10 or later
- Git

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/Sean074/modal_analysis.git
cd modal_analysis

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt
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
| 0 | Landing page | Entry point |
| 1 | Time History | Trim time window, apply Butterworth filter |
| 2 | FFT | Inspect spectra, save FFT for downstream use |
| 3 | Spectral Analysis | Auto-power, PSD, FRFs (H1/H2/Hv), coherence |
| 4 | SIMO EMA | Single-shaker system identification (pLSCF) |
| 5 | MIMO EMA | Dual-shaker system identification (multi-reference pLSCF) |
| 6 | MAC | Modal Assurance Criteria plot *(stub)* |
| 7 | Wireframe | 3-D mode shape visualisation |
| 8 | Methods | Explanation of the analytical methods used in MODAL_ANALYSIS |

Pages 1–3 feed into each other in sequence and can be used independently as QC tools. Page 4 (SIMO) and Page 5 (MIMO) reads CSV data directly and computes its own FRFs — Pages 1, 2 and 3 are not required for system identification.
---

## Documentation

| File | Audience | Contents |
|---|---|---|
| `modal_analysis.md` | Developers / analysts | Full page-by-page UI spec, controls, algorithms, and session state |
| `analysis_method.ipynb` | Analysts / students | Signal processing and system ID methods with worked Python examples |
