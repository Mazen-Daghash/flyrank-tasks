"""Background worker process -- the thing that actually does the slow work.

Runs completely separately from the API server:

    python worker.py [worker-name]

Polls the `jobs` table for due work, claims a job atomically (safe even
with several `python worker.py` processes running at once, or the same job
getting handed out twice), runs the simulated AI call, and either completes
it, reschedules it with backoff, or -- once retries are exhausted -- marks
it failed and fires an alert.
"""
from __future__ import annotations

import sys
import time

import db
import jobs
from ai_provider import AIProviderError, call_ai_provider

POLL_INTERVAL_SECONDS = 1.0
STUCK_JOB_TIMEOUT_SECONDS = 60


def log(msg: str) -> None:
    # flush=True so a worker piped to a log file (as any real deployment
    # would run it) doesn't sit buffered -- an alert nobody sees until the
    # process happens to exit defeats the point of alerting.
    print(msg, flush=True)


def process(conn, worker_name: str, job: jobs.Job) -> None:
    log(f"[{worker_name}] {job.id}: attempt {job.attempts + 1}/{job.max_attempts}")
    try:
        result = call_ai_provider(
            text=job.payload["text"],
            mode=job.payload.get("simulate"),
            attempts_before_this_call=job.attempts,
        )
    except AIProviderError as exc:
        outcome, delay = jobs.fail_or_retry(conn, job, str(exc))
        if outcome == "retry":
            log(f"[{worker_name}] {job.id}: failed ({exc}) -- retrying in {delay:.0f}s")
        else:
            jobs.record_alert(
                conn, job.id, f"job {job.id} failed after {job.max_attempts} attempts: {exc}"
            )
            log(f"[{worker_name}] {job.id}: FAILED permanently after {job.max_attempts} attempts")
            log(f"  [ALERT] {job.id} exhausted retries -- see GET /alerts ({exc})")
        return

    jobs.complete_job(conn, job.id, result)
    log(f"[{worker_name}] {job.id}: completed -> {result}")


def run_forever(worker_name: str) -> None:
    conn = db.get_connection()
    db.init_db(conn)

    recovered = jobs.requeue_stuck_jobs(conn, STUCK_JOB_TIMEOUT_SECONDS)
    if recovered:
        log(f"[{worker_name}] requeued {recovered} job(s) stuck 'processing' from a previous crash")

    log(f"[{worker_name}] polling every {POLL_INTERVAL_SECONDS}s (Ctrl+C to stop)")
    while True:
        job = jobs.claim_next_job(conn)
        if job is None:
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        process(conn, worker_name, job)


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "worker-1"
    try:
        run_forever(name)
    except KeyboardInterrupt:
        log(f"\n[{name}] stopped")
