from datetime import datetime, timezone
import sys

from scipy import stats

from app.models import Prediction, SessionLocal

# --- Configuration -----------------------------------------------------------
ALPHA = 0.05        # significance threshold for the KS test
MIN_SAMPLES = 30    # minimum rows in each window before the test runs
REF_SIZE = 500      # number of earliest rows used as the reference baseline
LIVE_SIZE = 200     # number of most-recent rows used as the live window
# -----------------------------------------------------------------------------


def load_reference(session):
    """Return confidence scores of the earliest REF_SIZE predictions."""
    rows = (
        session.query(Prediction.confidence)
        .order_by(Prediction.created_at.asc())
        .limit(REF_SIZE)
        .all()
    )
    return [r.confidence for r in rows]


def load_live(session):
    """Return confidence scores of the most recent LIVE_SIZE predictions."""
    rows = (
        session.query(Prediction.confidence)
        .order_by(Prediction.created_at.desc())
        .limit(LIVE_SIZE)
        .all()
    )
    return [r.confidence for r in rows]


def run_ks_test(reference, live):
    """Run the two-sample KS test and return (statistic D, p-value)."""
    result = stats.ks_2samp(reference, live)
    return result.statistic, result.pvalue


def emit_result(ts, n_ref, n_live, D, p, alpha, verdict):
    """Print a single structured, log-friendly result line."""
    print(
        f"[{ts}] drift_monitor | "
        f"n_ref={n_ref} n_live={n_live} "
        f"D={D:.4f} p={p:.4f} alpha={alpha} "
        f"verdict={verdict}"
    )


def main():
    session = SessionLocal()
    try:
        reference = load_reference(session)
        live = load_live(session)
    finally:
        session.close()

    ts = datetime.now(timezone.utc).isoformat()

    if len(reference) < MIN_SAMPLES or len(live) < MIN_SAMPLES:
        print(
            f"[{ts}] drift_monitor | verdict=insufficient_data "
            f"n_ref={len(reference)} n_live={len(live)} "
            f"min_samples={MIN_SAMPLES}"
        )
        sys.exit(0)

    D, p = run_ks_test(reference, live)
    verdict = "DRIFT" if p < ALPHA else "OK"
    emit_result(ts, len(reference), len(live), D, p, ALPHA, verdict)


if __name__ == "__main__":
    main()
