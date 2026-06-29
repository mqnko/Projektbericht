# MONITORING_BRIEF.md

Implementation brief for the drift-monitoring component of the PixelWise
Projektbericht. This file is the single source of truth for the feature. Read it
first, then read the actual database and prediction code in this repo before
writing anything.

---

## 0. Context

PixelWise is a handwritten-digit classifier deployed on a VM: a **FastAPI** model
service behind **Nginx**, supervised by **systemd**, persisting predictions to a
**PostgreSQL** database via **SQLAlchemy**. The connection string (`DATABASE_URL`)
is built in code from a `DB_PASSWORD` environment variable provided through a
systemd EnvironmentFile. The base app (classifier + API + predictions table)
already works. This task adds **one new, decoupled component**: an automated
monitor that detects distribution drift in the model's confidence scores over
time.

This is coursework with an academic report attached. The code must be clean,
readable, and reproducible, because it is graded alongside the report and must
live in a working GitHub repository.

## 1. Goal

Detect when the distribution of model **confidence scores** on live traffic has
drifted away from a historical **reference** distribution, and raise an alert
when it has. The statistical instrument is the **two-sample
Kolmogorov–Smirnov (KS) test**.

Rationale (already argued in the report, do not re-derive): monitoring the
one-dimensional confidence score is a cheap, valid proxy for drift, avoiding the
curse of dimensionality that makes testing the raw 28x28 image inputs
impractical.

## 2. Hard constraints

These come from the report's architecture chapter. Do not violate them.

- **Read-only and decoupled.** The monitor only *reads* from the predictions
  table (`SELECT` only). It must not modify the classifier, the API, the request
  path, or existing rows. No change to API latency.
- **Reuse the app's data layer.** Talk to the database through the project's
  existing SQLAlchemy engine / `SessionLocal` and predictions model. Do not open
  a second raw connection and do not introduce another database engine.
- **Run-once-and-exit.** The monitor is a single-shot script: start, evaluate,
  emit a result, exit. Scheduling is external via **cron** (see §7). Do not
  write a long-running loop or background thread.
- **Minimal dependencies.** Standard library + the existing SQLAlchemy stack +
  SciPy for the KS test.

## 3. Things to confirm from the repo BEFORE coding

Verify these against the actual files (the DB/models module, the API wiring,
`requirements.txt`):

- **Predictions table / model**: the SQLAlchemy model class and underlying table
  name for stored predictions.
- **Confidence column**: name, and whether it stores the scalar max-softmax
  probability in [0, 1] or the full 10-class vector. The monitor needs a scalar;
  if only the full vector is stored, reduce with `max()` at read time.
- **Timestamp column**: name and type (e.g. `DateTime`). Needed to order rows
  and to split reference vs live.
- **Engine / session**: where the app defines its engine and `SessionLocal` —
  import and reuse them rather than constructing your own.
- **Connection config**: how `DATABASE_URL` is assembled from `DB_PASSWORD`.
  Reuse that mechanism; never hardcode credentials or print secrets.

## 4. What to build

A module, suggested `monitoring/drift_monitor.py`, exposing a `main()` that runs
the full check once. Break it into small, testable functions:

1. **Load reference sample.** Query the confidence scores of the historical
   baseline window (see §5 for the split) through the existing session.
2. **Load live sample.** Query the confidence scores of the most recent window.
3. **Cold-start guard.** If either sample has fewer than `MIN_SAMPLES` rows,
   skip the test and exit cleanly with a clear "insufficient data" status. Do
   **not** run the KS test on tiny samples. (This directly backs report §4.3.)
4. **Run the test.** `scipy.stats.ks_2samp(reference, live)` -> statistic `D` and
   `p`-value.
5. **Decide.** If `p < ALPHA`, flag drift; else report no drift.
6. **Emit result.** Print a structured, log-friendly line (timestamp, n_ref,
   n_live, D, p, alpha, verdict). Alerting = stdout/log for now; keep the emit
   step in its own function so it can later be swapped for Prometheus/email
   without touching the statistics.

## 5. Reference-vs-live split

Make this a single configurable strategy, not scattered logic. Default:

- **Reference** = the earliest `REF_SIZE` predictions (the baseline captured when
  the model was known-good), **or** all rows older than a cutoff.
- **Live** = the most recent `LIVE_SIZE` predictions (sliding window).

Expose `REF_SIZE`, `LIVE_SIZE`, `MIN_SAMPLES`, and `ALPHA` as constants/config
at the top of the file. Sensible starting values: `ALPHA = 0.05`,
`MIN_SAMPLES = 30`, window sizes a few hundred — but make them trivially
editable, because the report's §4.2 experiment sweeps `ALPHA` and the §4.3
discussion depends on `MIN_SAMPLES`.

## 6. Experiment harness (second, after the monitor works)

Not part of the production monitor, but needed to generate the report's
Chapter 4 results. Keep it in a separate script, e.g.
`experiments/inject_drift.py`:

- Take a known-good baseline run as the reference.
- Induce controlled drift by feeding out-of-distribution / noisy / rotated
  inputs so the confidence distribution shifts downward, and record those
  predictions as the live window.
- Run the monitor against (a) a no-drift live window and (b) drifted windows of
  increasing severity.
- Capture, for the report: the `p`-value trajectory under no-drift vs drift, the
  false-positive count under the null, and the detection outcome per severity.
  Save these as CSV + a plot so they can go straight into Chapter 4.

Keep all randomness seeded so the results are reproducible.

## 7. Scheduling & reproducibility (report §3.3)

- Provide the exact **cron** line to run the monitor periodically (e.g. every 15
  min): invoke the project's Python interpreter on `drift_monitor.py`, with the
  working directory and environment set so `DATABASE_URL` / `DB_PASSWORD`
  resolve the same way the systemd service resolves them.
- Add a short section to the repo README: how to run the monitor once by hand,
  how to run the experiment, and how to reproduce the Chapter 4 figures.
- Ensure a fresh clone can run it: pin new deps (SciPy) in `requirements.txt`.

## 8. Out of scope (state as limitations, do not implement)

These are deliberately excluded and are written up in the report's conclusion as
simplifications — do not build them:

- No automated retraining / CI-CD trigger. The monitor only **alerts**; it is
  reactive, not self-healing.
- **Univariate only.** Single scalar (max-softmax), not the full softmax vector,
  and not a multivariate test (MMD, autoencoder error). Those are "future work".
- No concept-drift detection (that needs serving-time labels, which are
  unavailable). The monitor targets input/covariate-style drift as reflected in
  confidence.

## 9. Definition of done

- `drift_monitor.py` runs once against the real PostgreSQL DB, prints a clear
  verdict, and exits 0; handles the empty/cold-start case without crashing.
- Reads the predictions table through the app's SQLAlchemy layer; `SELECT` only,
  writes nothing.
- Config constants exposed at top; KS test via SciPy.
- Experiment script produces the no-drift vs drift comparison as CSV + plot.
- README updated with run + cron + reproduce instructions; `requirements.txt`
  updated.
- Report mismatches (real table/column names, confidence scalar vs vector)
  flagged back to me rather than silently reconciled.
