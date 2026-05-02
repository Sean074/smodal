# Bugs
1) If on page 2 FFT the user saves a Welch anlysis and then on Page 3 Spectral Analysis tries to execute a single FFT an error occurs.  This is correct the Welch FFT from PAge 2 can NOT be used as the input into the Page 3 Single FFT analysis.

2) The New page 4 needs to be renamed to Modal Parameter Estimation - SIMO
3) Feels like the user should be able to identify mode freqs in the CMIF plot and these added to the stability diagram table fitting process.
4) The mode specification table has a damping estimate. Seems defaults to the 2%. How is this calculated?
5) With defined peaks in the CMIF the stability diagram does not indicate mode identification.  The CMIF identifies a peak at low modal order however there is no indication on the stability diagram.
5) what curve fit is been used? Multi Degree of Freedom Polynominal, MDOF Poly?
    - IS this a two part process?  PArt one pole identification, part 2 residual calculation.
6) the FRF is generally not a good match. Residuals, there estimate seems important to match the FRF. Should the residuals be calculated?
7) is the fitting limited the selected freq range?
8) the plots should scale to the selected freq range
9) should the user be able to modify the freq, damping, amplitude and phase in the mode shapes tab and have the FRFs update?

10) Allow OMA (operational modal analysis) what needs to be added or changed?
11) How to extend this to Multi input multi output MIMO.


# Development

