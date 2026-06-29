# PIXELWISE

This is a one-line project description of pixelwise, a full stack project
that teaches students how to deploy a small machine learning product on
a virtual machine.

First thing they learn is how to change things here in this repo. 
Such as this sentence itself.

---

## Drift Monitoring

The drift monitor detects when the distribution of model confidence scores on
live traffic has shifted away from the historical reference, using a two-sample
Kolmogorov-Smirnov test.

### Run the monitor once by hand

```bash
cd /home/user/pixelwise
.venv/bin/python3 -m monitoring.drift_monitor
```

The script prints one structured line and exits:

```
[2026-06-29T12:00:00+00:00] drift_monitor | n_ref=500 n_live=200 D=0.0412 p=0.8731 alpha=0.05 verdict=OK
```

If fewer than `MIN_SAMPLES` rows exist in either window it exits cleanly with
`verdict=insufficient_data`.

### Schedule with cron

Add the following line to your crontab (`crontab -e`) to run every 15 minutes.
Review and adjust the log path before installing.

```
*/15 * * * * cd /home/user/pixelwise && /home/user/pixelwise/.venv/bin/python3 -m monitoring.drift_monitor >> /var/log/pixelwise/drift_monitor.log 2>&1
```

`DB_PASSWORD` is loaded automatically from `.env` by `python-dotenv` (the same
mechanism the app uses for local runs).

### Run the experiment and reproduce Chapter 4 figures

Install dependencies first if you have not already:

```bash
cd /home/user/pixelwise
.venv/bin/pip install -r requirements.txt
```

Then run:

```bash
.venv/bin/python3 experiments/inject_drift.py
```

This produces:

- `experiments/drift_results.csv` — KS statistic, p-value, and verdict for
  each drift scenario
- `experiments/drift_plot.png` — confidence distributions and p-value bar chart

All randomness is seeded (`SEED = 42`), so results are fully reproducible on a
fresh clone.
