# Algorithms

One-paragraph reference per analysis method used in the app. Implementation lives in
`core/spectral.py` and `core/sysid.py`; worked Python examples are in `docs/methods.ipynb`.
Page-by-page UI context is in `docs/workflow_pages.md`.

---

## FFT & Windowing

The Discrete Fourier Transform converts a time-domain signal into the frequency domain by
decomposing it into a sum of sinusoids. A window function (Hanning, Flat-top, Exponential, or
uniform boxcar) is applied before the FFT to reduce spectral leakage from signal truncation; the
Flat-top window minimises amplitude error while the Hanning window is a good general-purpose
choice. Implementation: `core/spectral.py` → `compute_fft`; see `docs/methods.ipynb` §FFT.

## Welch PSD

The Welch method estimates the Power Spectral Density by averaging periodograms computed over
overlapping, windowed segments of the signal. Averaging reduces variance at the cost of frequency
resolution; typical settings are 50–75% overlap with a Hanning window. Implementation:
`core/spectral.py` → `compute_welch_quantities`, `compute_output_spectral_matrix`; see
`docs/methods.ipynb` §Welch.

## FRF Estimators (H1 / H2 / Hv)

A Frequency Response Function (FRF) relates the output spectrum to the input spectrum. Three
estimators are supported: **H1** (`Gyx / Gxx`) minimises output noise and is preferred for
impact testing; **H2** (`Gyy / Gxy`) minimises input noise; **Hv** is the geometric mean and
is robust when noise is present on both signals. Implementation: `core/spectral.py` →
`compute_spectral_quantities`, `compute_welch_quantities`; see `docs/methods.ipynb` §FRF.

## Coherence

Coherence γ² = |Gxy|² / (Gxx × Gyy) measures the linear causality between input and output at
each frequency, ranging from 0 (no linear relationship) to 1 (perfectly linear). Values below
~0.8 indicate noise, nonlinearity, or signal leakage and should be investigated before
interpreting FRFs. Implementation: `core/spectral.py` → `compute_welch_quantities`; see
`docs/methods.ipynb` §Coherence.

## pLSCF (PolyMAX)

The Polyreference Least-Squares Complex Frequency (pLSCF) method fits a polynomial fraction model
to the measured FRF matrix to estimate poles (natural frequencies and damping ratios) and mode
shapes. It builds a stability diagram by sweeping model orders and flagging poles that stabilise
in frequency, damping, and mode shape (MAC) across orders. Implementation: `core/sysid.py` →
`plscf_poles`, `build_stability_table`; see `docs/methods.ipynb` §pLSCF.

## ERA (Eigensystem Realization Algorithm)

ERA reconstructs a minimal state-space model from the free-decay Impulse Response Function (IRF),
obtained by inverse FFT of the measured FRF. A block Hankel matrix is formed from the IRF,
decomposed by SVD to determine system order, and the state-space eigenvalues yield the poles.
ERA is an alternative to pLSCF and can be more robust for lightly damped structures.
Implementation: `core/sysid.py` → `era_poles`; see `docs/methods.ipynb` §ERA.

## FDD (Frequency Domain Decomposition)

FDD is an output-only (OMA) method that decomposes the output Power Spectral Density matrix by
SVD at each frequency line. Peaks in the first singular value curve identify natural frequencies;
damping is estimated via the half-power bandwidth of the corresponding singular value bell curve.
FDD assumes broadband, white-noise excitation and works without measuring the input force.
Implementation: `core/sysid.py` → `fdd_svd`, `fdd_damping`; see `docs/methods.ipynb` §FDD.

## MAC (Modal Assurance Criterion)

The Modal Assurance Criterion quantifies the degree of correlation between two mode shape vectors
as a scalar from 0 (orthogonal — unrelated modes) to 1 (perfectly correlated). A MAC matrix
between reference and computed mode sets is plotted as a colour map; diagonal values close to 1
and off-diagonal values close to 0 indicate a well-separated, correctly identified modal set.
Implementation: `core/sysid.py` → `compute_mac`; see `docs/workflow_pages.md` §Page 7.
