# Known bugs



---

# Planned features / enhancements

0. Data input format. current default is csv.  Possible that data from test equipment will be in universal files *.unv. Need to decide if the data is converted to a csv or read directly as a panda.
1. Allow users to pick mode frequencies directly on the CMIF plot and have those added to the stability diagram estimates table.
2. Add Operational Modal Analysis (OMA) support — ambient excitation with no measured input force. ERA (`era_poles` in `core/sysid.py`) is already implemented and is the natural starting point as it does not require a measured input; it just needs to be re-exposed in the Page 4 UI.
3. Extend to MIMO Random — two independent broadband random inputs; FRF via H1 estimator with Welch averaging; requires good coherence to overcome leakage.
4. MIMO Burst Random — removes leakage without a window; better for lightly damped structures.
5. Force control / COLA — constant-overlap-and-add stepped sine with force-controlled amplitude for nonlinear structure characterisation.
6. OMA overlay — compare EMA mode shapes against OMA results for in-service validation.
7. Implement page 6 (Modal Assurance Criteria) — MAC matrix between identified mode shapes.

