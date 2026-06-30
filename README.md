# PixelWise — Distribution Drift Monitoring

PixelWise is a handwritten-digit recognition service: a small machine-learning
product deployed end to end on a virtual machine. The classifier is served
through a **FastAPI** application, every prediction is persisted to a
**PostgreSQL** database via the **SQLAlchemy** ORM, and the service is exposed
behind an **Nginx** reverse proxy under a **systemd** unit.

This repository extends that base system with an automated **distribution-drift
monitor**. The monitor detects when the distribution of the model's confidence
scores on live traffic has shifted away from a historical reference, using a
two-sample Kolmogorov–Smirnov (KS) test. It accompanies the project report
(*Automated Detection of Distribution Drift in Production Machine Learning
Infrastructures*) and contains the code, experiment, and reproduction steps
referenced there.

---

## Why monitor confidence scores?

Inspecting the raw 28×28 image inputs for drift is impractical: each input spans
hundreds of dimensions, and two-sample tests lose statistical power as
dimensionality grows. Instead, the monitor tracks a single scalar — the maximum
of the classifier's nine-class softmax output (the prediction confidence). A
two-sample test on this one-dimensional signal is a cheap and reliable proxy:
when the input distribution shifts, the confidence distribution shifts with it.

The test used is the **two-sample Kolmogorov–Smirnov test**. Its statistic *D*
is the maximum distance between the empirical cumulative distribution functions
of a reference sample and a live sample. Drift is flagged when the associated
*p*-value falls below a significance level *α*.

---

## Architecture

The monitor is a **decoupled background component**. It shares only the database
with the live system and never enters the request path, so the classification
endpoint's latency is unaffected and a failure in the monitor cannot disturb
serving.

```
 User ──▶ API ──▶ Classifier ──▶ writes ──▶ [ PostgreSQL: predictions ]
                                                      │ read-only
 cron ──▶ drift_monitor ──▶ KS test (SciPy) ──▶ alert ┘
```

The monitor reuses the application's existing SQLAlchemy engine, session
factory, and `Prediction` model, so it opens no second connection and shares one
data layer with the service. All database access is read-only (`SELECT`).

---

## How drift detection works

Two windows are drawn from the `predictions` table:

- **Reference window** — the earliest `REF_SIZE` predictions, taken as the
  known-good baseline.
- **Live window** — the most recent `LIVE_SIZE` predictions, a sliding window
  over current traffic.

Both windows are reduced to their confidence values and passed to
`scipy.stats.ks_2samp`, which returns *D* and the *p*-value. If `p < ALPHA`, the
run reports drift.

A **cold-start guard** precedes the test: if either window holds fewer than
`MIN_SAMPLES` predictions, the test is skipped and the run reports
`insufficient_data` rather than a verdict on a sample too small to be reliable.

The behaviour is controlled by configuration constants at the top of
`monitoring/drift_monitor.py`:

| Constant      | Default | Meaning                                          |
| ------------- | ------- | ------------------------------------------------ |
| `ALPHA`       | 0.05    | Significance threshold for the KS test           |
| `MIN_SAMPLES` | 30      | Minimum rows per window before the test runs     |
| `REF_SIZE`    | 500     | Size of the reference (baseline) window          |
| `LIVE_SIZE`   | 200     | Size of the live (sliding) window                |

---

## Running

### Run the monitor once by hand

```bash
cd /home/user/Projektbericht
.venv/bin/python3 -m monitoring.drift_monitor
```

The script prints one structured line and exits:

```
[2026-06-29T16:04:20+00:00] drift_monitor | n_ref=500 n_live=200 D=0.0600 p=0.6644 alpha=0.05 verdict=OK
```

If fewer than `MIN_SAMPLES` rows exist in either window it exits cleanly with
`verdict=insufficient_data`.

### Schedule with cron

The monitor is a single-shot script; scheduling is handled externally so the
service and the monitoring task stay decoupled. Add this to your crontab
(`crontab -e`) to run every 15 minutes — review and adjust the log path first:

```
*/15 * * * * cd /home/user/Projektbericht && /home/user/Projektbericht/.venv/bin/python3 -m monitoring.drift_monitor >> /var/log/pixelwise/drift_monitor.log 2>&1
```

### Run the experiment and reproduce the report figures

```bash
cd /home/user/Projektbericht
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 experiments/inject_drift.py
```

This produces:

- `experiments/drift_results.csv` — *D*, *p*-value, and verdict per scenario
- `experiments/drift_plot.png` — confidence distributions and *p*-value chart

All randomness is seeded (`SEED = 42`), so results are fully reproducible on a
fresh clone.

---

## Database configuration

The connection string is assembled in `app/models.py` from a single secret,
`DB_PASSWORD`, loaded from `.env` by `python-dotenv` (and supplied via a systemd
EnvironmentFile in deployment). Copy `.env.example` to `.env` and set the
password before running:

```bash
cp .env.example .env
# then edit .env and set DB_PASSWORD
```

`.env` is git-ignored and must never be committed.

---

## A note on data collection

The `/classify` endpoint is rate-limited to 30 requests per minute, which makes
accumulating a large prediction history through the public interface slow. To
build a representative reference baseline for evaluation, predictions were
written directly to the database through the same ORM, bypassing the
rate-limited endpoint while preserving the stored data format.

---

## Scope and limitations

The monitor is intentionally lightweight; the following are deliberate
boundaries rather than oversights, and are discussed as future work in the
report:

- **Synthetic drift in the experiment.** `inject_drift.py` draws confidence
  scores from beta distributions of decreasing mean rather than feeding shifted
  images through the classifier. This isolates the test's response and keeps the
  ground-truth drift state known by construction, but it is a simulation of
  drifted confidence, not drift induced through the real model.
- **Univariate signal.** The monitor reduces each prediction to a single scalar,
  so it detects *that* a shift occurred but cannot localise its cause. A
  multivariate test on the full softmax vector (or methods such as MMD or
  autoencoder reconstruction error) would be needed to localise shifts.
- **Covariate drift only.** Because true labels are unavailable at serving time,
  the monitor observes input-driven (covariate) drift reflected in confidence,
  not concept drift in the posterior P(Y|X).
- **Alert-only.** The monitor is reactive: it raises an alert but does not
  trigger retraining. Coupling the alert to an automated retraining step would
  close the MLOps feedback loop.

---

## Project structure

```
app/            FastAPI application, classifier, SQLAlchemy models
monitoring/     drift_monitor.py — the drift-monitoring component
experiments/    inject_drift.py — synthetic drift experiment + outputs
frontend/       drawing canvas and classify UI
models/         model card and loader (the .pkl is fetched at setup, not committed)
deploy/         systemd service and Nginx configuration
setup-server.sh provisioning script (PostgreSQL, systemd, Nginx, frontend)
init_db.py      database/table initialisation
predict.py      batch prediction helper
```

---

## AI assistance

The drift-monitoring component (`monitoring/` and `experiments/`) was
implemented with the assistance of an AI coding tool, working from a written
specification and under review: every change was inspected, tested against the
live database, and approved before being committed. The system architecture,
statistical methodology, source selection, and the full text of the report are
the author's own. See the report's AI-usage declaration for details.
