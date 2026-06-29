# IMPORTANT: This script simulates drifted confidence distributions using
# synthetic data drawn from Beta distributions. It does NOT call the real
# classifier, hit the API, or write to the database. It exists solely to
# reproduce the Chapter 4 experiment results in a controlled, seeded setting
# where the ground-truth presence or absence of drift is known by construction.

import numpy as np
import pandas as pd
from scipy import stats
import matplotlib.pyplot as plt

# --- Configuration -----------------------------------------------------------
SEED = 42
REF_SIZE = 500
LIVE_SIZE = 200
ALPHA = 0.05
OUTPUT_CSV = "experiments/drift_results.csv"
OUTPUT_PLOT = "experiments/drift_plot.png"
# -----------------------------------------------------------------------------

np.random.seed(SEED)

# Reference baseline: a well-calibrated model produces high-confidence scores.
# Beta(8, 2) has mean 0.8 and is right-skewed — a reasonable proxy.
reference = np.random.beta(8, 2, REF_SIZE)

# Live windows across four scenarios of increasing drift severity.
# Each draws from a Beta whose mean shifts progressively downward.
scenarios = [
    ("no_drift",        np.random.beta(8, 2, LIVE_SIZE)),   # same dist, mean ~0.80
    ("mild_drift",      np.random.beta(5, 5, LIVE_SIZE)),   # symmetric,  mean ~0.50
    ("moderate_drift",  np.random.beta(3, 7, LIVE_SIZE)),   # left-skewed, mean ~0.30
    ("severe_drift",    np.random.beta(1, 9, LIVE_SIZE)),   # heavily left, mean ~0.10
]

# --- Run KS test for each scenario -------------------------------------------
records = []
for name, live in scenarios:
    D, p = stats.ks_2samp(reference, live)
    verdict = "DRIFT" if p < ALPHA else "OK"
    records.append({
        "scenario": name,
        "n_ref": REF_SIZE,
        "n_live": LIVE_SIZE,
        "D": round(float(D), 4),
        "p": round(float(p), 4),
        "alpha": ALPHA,
        "verdict": verdict,
    })
    print(f"{name:18s}  D={D:.4f}  p={p:.4f}  verdict={verdict}")

df = pd.DataFrame(records)
df.to_csv(OUTPUT_CSV, index=False)
print(f"\nResults saved to {OUTPUT_CSV}")

# --- Plot --------------------------------------------------------------------
fig, (ax_dist, ax_pval) = plt.subplots(1, 2, figsize=(12, 4))

# Left panel: confidence distributions
ax_dist.hist(
    reference, bins=25, density=True, alpha=0.6,
    color="black", label="reference", histtype="stepfilled",
)
colors = ["steelblue", "orange", "darkorange", "crimson"]
for (name, live), color in zip(scenarios, colors):
    ax_dist.hist(live, bins=25, density=True, alpha=0.45, color=color, label=name)
ax_dist.set_xlabel("Confidence score")
ax_dist.set_ylabel("Density")
ax_dist.set_title("Confidence distributions by scenario")
ax_dist.legend(fontsize=8)

# Right panel: KS p-value per scenario
p_values = [r["p"] for r in records]
labels = [r["scenario"] for r in records]
bar_colors = ["green" if p >= ALPHA else "crimson" for p in p_values]
ax_pval.bar(labels, p_values, color=bar_colors)
ax_pval.axhline(ALPHA, color="black", linestyle="--", linewidth=1.2, label=f"α = {ALPHA}")
ax_pval.set_ylabel("KS p-value")
ax_pval.set_title("KS p-value by drift scenario")
ax_pval.legend(fontsize=9)
plt.setp(ax_pval.get_xticklabels(), rotation=15, ha="right")

plt.tight_layout()
plt.savefig(OUTPUT_PLOT, dpi=150)
print(f"Plot saved to {OUTPUT_PLOT}")
