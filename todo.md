# Known bugs

1. If on page 2 (FFT) the user saves a Welch analysis and then on page 3 (Spectral Analysis) tries to execute a Single FFT, an error occurs. This is by design — a Welch FFT from page 2 cannot be used as the input into the page 3 Single FFT analysis. The error message should be made clearer to the user.

---

# Planned features / enhancements

1. Allow users to pick mode frequencies directly on the CMIF plot and have those added to the stability diagram estimates table.
2. Add Operational Modal Analysis (OMA) support — ambient excitation with no measured input force. ERA is the natural starting point as it does not require a measured input.
3. Extend to MIMO Random — two independent broadband random inputs; FRF via H1 estimator with Welch averaging; requires good coherence to overcome leakage.
4. MIMO Burst Random — removes leakage without a window; better for lightly damped structures.
5. Force control / COLA — constant-overlap-and-add stepped sine with force-controlled amplitude for nonlinear structure characterisation.
6. OMA overlay — compare EMA mode shapes against OMA results for in-service validation.
7. Implement page 6 (Modal Assurance Criteria) — MAC matrix between identified mode shapes.
8. Implement page 7 (Wireframe) — 3-D mode shape animation on a NASTRAN BDF geometry model.
