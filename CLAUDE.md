# CLAUDE.md — Project context and rules of engagement

> Claude Code reads this file automatically at the start of every session.
> Treat everything here as binding for this repository.

## What this project is

PixelWise: a handwritten-digit classifier (model + web API + database) deployed
on a VM, built across the blocks of the Full Stack course. The stack is
**FastAPI + SQLAlchemy + PostgreSQL**, served behind **Nginx** and supervised by
**systemd**. The database connection is built in code from a `DB_PASSWORD`
environment variable supplied via a systemd EnvironmentFile (`DATABASE_URL`).
The base application already works. It is **not** yours to rebuild.

## Your task — the only task

Implement the drift-monitoring extension specified in **`MONITORING_BRIEF.md`**.
Read that file first; it is the technical build spec. Nothing in this repository
should change except what that brief requires.

## Scope boundaries

- Build **only** the monitoring extension. Do not refactor, "improve", reformat,
  rename, or upgrade anything outside it. Do not touch the classifier, the API,
  the training code, the Nginx/systemd config, or any existing file beyond the
  minimal additive edits the brief calls for.
- New code lives in **two new areas only**: the monitoring component
  (e.g. `monitoring/`) and the experiment harness (e.g. `experiments/`), plus
  small additive edits to `requirements.txt` and the README.
- The predictions table is **read-only**: `SELECT` only. Never `INSERT`,
  `UPDATE`, `DELETE`, or run DDL/migrations against it.

## Database access — match the existing app

- The app already uses **SQLAlchemy** against **PostgreSQL**. **Reuse the
  project's existing engine / `SessionLocal` and the predictions model** to read
  the data. Do not open a second raw connection, do not introduce `sqlite3`, and
  do not rebuild the connection URL by hand if the existing module can be
  imported.
- The connection comes from the existing `DATABASE_URL` / `DB_PASSWORD`
  mechanism. Reuse it. Never hardcode credentials, never read or print the
  contents of `.env` or the value of `DB_PASSWORD`.

## System / VM changes — strict approval gate

This is graded coursework on a managed VM. The governing rule is: **only perform
system-level changes that the course script (Full Stack Skript) documents.** I am
the authority on what the script permits — when in doubt, ask me.

- **Default: make no system-level change.** That includes installing system
  packages, editing `systemd` units or the Nginx config, changing `.env`,
  opening ports, or adding scheduled jobs.
- This extension needs **exactly two environment touches**, and each must be
  proposed and approved by me *before* you act:
  1. Installing **SciPy** into the project's **existing** environment
     (the venv / requirements the project already uses) — never system-wide,
     never with `sudo`.
  2. Adding a **single `cron` entry** to schedule the monitor. The course
     script's deployment block uses `cron`; still, confirm with me before adding
     it.
- Before any system change: **STOP** and tell me, in plain text, (a) what you
  want to change, (b) why, and (c) where the course script sanctions it. If you
  cannot point to the script, do not do it — ask me.
- Never use `sudo`. Never run destructive commands (`rm -rf`, `DROP`, schema
  migrations). Never modify anything outside this repository except the one
  approved `cron` entry.

## How to work

- **Start in plan mode.** Inspect how the app defines its SQLAlchemy engine,
  `SessionLocal`, and the predictions model/table, plus `requirements.txt`,
  first. Present a plan and wait for my approval before writing anything.
- **Report mismatches, do not silently fix them.** If the real schema or column
  names differ from `MONITORING_BRIEF.md`, or from how the written report
  describes them, surface it to me as a plain-text list. I will fix the report.
  **You do not edit the report.**
- **Small, reviewable steps.** Implement one piece at a time and let me approve
  each file write. Keep diffs minimal. Commit after each completed subtask.

## Definition of done

- `drift_monitor.py` runs once against the real PostgreSQL database, prints a
  structured verdict (timestamp, n_ref, n_live, D, p, alpha, decision), exits
  cleanly, and handles the empty / cold-start case without crashing.
- Reads the predictions table through the app's existing SQLAlchemy layer;
  `SELECT` only, writes nothing.
- KS test via `scipy.stats.ks_2samp`; config constants (`ALPHA`, `MIN_SAMPLES`,
  reference/live window sizes) exposed at the top of the file.
- Experiment script produces the no-drift-vs-drift comparison as CSV **and** a
  plot, with all randomness seeded.
- `requirements.txt` and README updated additively; the `cron` line is written
  out for me to review rather than installed unilaterally.
- A plain-text list of every code/report mismatch is handed to me.

## Out of scope — do not build

- No automated retraining or CI/CD trigger. The monitor only alerts.
- No multivariate or concept-drift detection (those are "future work" in the
  report).
- No changes to the model, the API, the training pipeline, or the
  Nginx/systemd/PostgreSQL provisioning.
