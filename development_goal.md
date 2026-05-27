Is it a real v1.0 release?
Short answer: no — the tag is aspirational. The repo today sits between two states: v1.0.0 was tagged 2026-05-24, and [Unreleased] in the CHANGELOG already contains the makings of a small v1.0.1 (Streamlit Cloud deploy fixes, README rename, landing-page caption). So "current status" really means unreleased post-1.0.0 main. The work on [Unreleased] is real and small enough to justify cutting v1.0.1 — but cutting it now would re-ship the same three correctness bugs I flagged in the prior review, plus an Alpha PyPI classifier inside a 1.0.0 package. That isn't a v1.0.1; that's a packaging touch-up on top of an alpha.

Three concrete reasons it doesn't read as a real v1.0:

The author's own CHANGELOG admits the v1.0.0 tag was cut a commit early and ships with pre-rename strings. That is a v0.x problem, not a v1.x problem.
pyproject.toml still says Development Status :: 3 - Alpha while version = "1.0.0". Pick one. The classifier is what scrapers and pip users will read.
Three silent-failure bugs in core/ shipped in the tag (the except Exception → unit-vector mode shapes in sysid.py, the pass-instead-of-warn in data_loader.py, the F06 exponent-sign regex in geometry.py). A "1.0" promise — even loosely — is that the basic workflow doesn't lie to the user. These paths do.
Realistic re-versioning options: (a) re-tag the current main as v0.9.0 / Beta, fix the three CRITICALs, then earn a v1.0.0; (b) keep v1.0.0 as a marker and target v1.1.0 for trustworthy results plus page-level tests. I'd recommend (a) — the cost is a GitHub tag move, and the honesty is worth it.

What's missing for engineers and engineering students
The audience matters because engineers and students fail in different ways. Engineers will trust the numbers too readily; students won't trust them enough and will give up at the first confusing screen. The current app fails both:

Quality gates on input data. Coherence is plotted but not used as a gate. Low-coherence bands should be flagged in the UI (yellow/red overlay), and the FRF estimator should warn when γ² < 0.7 over the analysis band. Right now an engineer can extract "modes" from incoherent noise without a single alarm.
Stability-diagram literacy. stable_all, stable_fd, stable_f, new — these are the most important glyphs on the whole app, and there is no in-app legend, tooltip, or worked example explaining when to trust each. Students will guess. Combined with the C-1 fabrication bug, they'll guess wrong.
Sanity bounds on model order, band width, and damping. A 60th-order pLSCF on a 30-frequency-line band is mathematically nonsense. The app accepts it silently. A simple "rule-of-thumb" check (order ≤ n_freq_lines/4) with an inline warning would prevent half the support questions you'll eventually get.
An analytical-truth benchmark. The bundled sample_3ch.csv is opaque — neither engineer nor student can check "did I get the right answer?" because there is no right answer documented. A second sample (single-DOF or 2-DOF analytic system with known fn, ξ, mode shape) lets users validate their workflow against a target they understand.
Result export that connects to FE workflows. Right now 7_MAC.py imports F06; nothing exports identified modes in a format another tool can read. A simple CSV with mode_number, fn_hz, xi_pct, residues... plus a UFF/UNV writer would let users round-trip into LMS/ME'scope/Femtools.
Reproducibility metadata in the analysis log. The JSON log captures parameters; it doesn't capture input file hash, app version, or library versions. For students this is fine; for engineers using this on real data it's a gap.
Tutorial pedagogy. docs/methods.ipynb is a theory reference, not a tutorial. The first thing a student needs is a guided run-through with annotations: "click here, observe this, this is why."
A roadmap document. todo.md is essentially empty (one "nice to have" item). For an open-source project asking for issues and PRs, the absence of "here is where this is going" discourages contribution.
The biggest value improvements (ranked by leverage)
If you can only do five things in the next month:

Fix the three CRITICAL silent-failure paths. Cost: ~2 days. Value: the app stops lying. Nothing else matters until this is done.
Add a coherence-driven quality gate that shows up in the SIMO/MIMO/OMA UIs. Cost: ~3 days. Value: the single largest predictor of "did I get a real mode" is "was my input coherent in this band" — surfacing that turns the app from a calculator into a guide. This is also the feature most likely to teach students why their results are wrong, which is the whole point of a teaching tool.
Ship a Streamlit AppTest-based smoke test for every page. Cost: ~3-4 days. Value: the difference between "we hope it works" and "we know each page loads, accepts data, and writes the expected session-state keys." Today the page layer is uncovered; nine smoke tests would catch ~80% of the regressions users will report.
Add an analytical 2-DOF reference dataset + a tutorial notebook that runs end-to-end against it. Cost: ~2 days. Value: students get a calibration point they can trust; you get a smoke-test fixture you can run in CI to catch numerical regressions in sysid.py. Two birds.
Export identified modes as CSV + UFF/UNV. Cost: ~2 days. Value: the app stops being a dead end. Right now results live only in st.session_state; once the browser tab closes, they're gone. Export turns smodal from a viewer into a step in a workflow, which is what engineers actually need.
Two honourable mentions worth doing soon but not in the first five: (a) refactor SIMO/MIMO shared logic into core/ema_pipeline.py (eliminates the recurring "fix landed in SIMO but not MIMO" failure mode); (b) add tooltips/legend to the stability diagram glyphs (cheap, high pedagogical value).

The honest summary
Today's main is a competent, well-documented alpha with a misleading version number, a public deploy, and three correctness bugs that an engineering user — and especially an engineering student — has no way to detect on their own. Fix the correctness bugs, add coherence-driven quality gates, write one tutorial against a known-truth dataset, and you have a genuine v1.0 worth promoting. Don't ship v1.0.1 until at least the correctness bugs are out.