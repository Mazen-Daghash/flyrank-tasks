"""The job repository: every state transition a job can go through, each
one a single atomic SQL statement so two callers (two worker processes, a
redelivered message, a client retrying its POST) can never both "win" the
same transition.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    id: str
    idempotency_key: str | None
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    attempts: int
    max_attempts: int
    created_at: str
    updated_at: str
    available_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Job":
        return cls(
            id=row["id"],
            idempotency_key=row["idempotency_key"],
            status=row["status"],
            payload=json.loads(row["payload"]),
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            available_at=row["available_at"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "status": self.status,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def find_by_idempotency_key(conn: sqlite3.Connection, key: str) -> Job | None:
    row = conn.execute("SELECT * FROM jobs WHERE idempotency_key = ?", (key,)).fetchone()
    return Job.from_row(row) if row else None


def create_job(
    conn: sqlite3.Connection,
    payload: dict[str, Any],
    idempotency_key: str | None,
    max_attempts: int = 3,
) -> tuple[Job, bool]:
    """Returns (job, created). `created` is False when idempotency_key
    matched a job that already existed -- the caller should not enqueue it
    again, since the original request already did."""
    if idempotency_key:
        existing = find_by_idempotency_key(conn, idempotency_key)
        if existing:
            return existing, False

    job_id = str(uuid.uuid4())
    ts = now_iso()
    try:
        conn.execute(
            """INSERT INTO jobs
                   (id, idempotency_key, status, payload, attempts, max_attempts,
                    created_at, updated_at, available_at)
               VALUES (?, ?, 'pending', ?, 0, ?, ?, ?, ?)""",
            (job_id, idempotency_key, json.dumps(payload), max_attempts, ts, ts, ts),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Lost a race against a concurrent request carrying the same key.
        conn.rollback()
        return find_by_idempotency_key(conn, idempotency_key), False  # type: ignore[return-value]

    return get_job(conn, job_id), True  # type: ignore[return-value]


def get_job(conn: sqlite3.Connection, job_id: str) -> Job | None:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return Job.from_row(row) if row else None


def list_all(conn: sqlite3.Connection) -> list[Job]:
    rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
    return [Job.from_row(row) for row in rows]


def try_claim(conn: sqlite3.Connection, job_id: str) -> bool:
    """Atomically flip one specific job pending -> processing. False means
    someone else already claimed it (or it's not due yet) -- this single
    WHERE clause is what makes it safe for the same job_id to be handed to
    two workers, or the same worker twice: only one UPDATE can match."""
    now = now_iso()
    cur = conn.execute(
        """UPDATE jobs SET status = 'processing', updated_at = ?
           WHERE id = ? AND status = 'pending' AND available_at <= ?""",
        (now, job_id, now),
    )
    conn.commit()
    return cur.rowcount == 1


def claim_next_job(conn: sqlite3.Connection) -> Job | None:
    """The worker's 'dequeue': look at a few of the oldest due jobs and try
    to claim the first one nobody else has grabbed yet."""
    now = now_iso()
    candidates = conn.execute(
        """SELECT id FROM jobs WHERE status = 'pending' AND available_at <= ?
           ORDER BY created_at LIMIT 5""",
        (now,),
    ).fetchall()
    for row in candidates:
        if try_claim(conn, row["id"]):
            return get_job(conn, row["id"])
    return None


def complete_job(conn: sqlite3.Connection, job_id: str, result: dict[str, Any]) -> None:
    conn.execute(
        "UPDATE jobs SET status = 'completed', result = ?, error = NULL, updated_at = ? WHERE id = ?",
        (json.dumps(result), now_iso(), job_id),
    )
    conn.commit()


def fail_or_retry(conn: sqlite3.Connection, job: Job, error: str) -> tuple[str, float]:
    """Bump the attempt count. Under max_attempts: reschedule with
    exponential backoff (2s, 4s, 8s, ...) and return ('retry', delay).
    At max_attempts: mark permanently failed and return ('failed', 0)."""
    attempts = job.attempts + 1
    now = now_iso()

    if attempts >= job.max_attempts:
        conn.execute(
            "UPDATE jobs SET status = 'failed', attempts = ?, error = ?, updated_at = ? WHERE id = ?",
            (attempts, error, now, job.id),
        )
        conn.commit()
        return "failed", 0.0

    delay = float(2**attempts)
    available_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
    conn.execute(
        """UPDATE jobs SET status = 'pending', attempts = ?, error = ?, updated_at = ?,
                            available_at = ? WHERE id = ?""",
        (attempts, error, now, available_at, job.id),
    )
    conn.commit()
    return "retry", delay


def requeue_stuck_jobs(conn: sqlite3.Connection, stuck_after_seconds: int = 60) -> int:
    """Crash recovery: a job left 'processing' with no update for a while
    means the worker that claimed it died mid-job. Put it back in the
    pool -- whichever worker picks it up next runs it via the same claim
    path as everything else, so this is just another case of 'the same job
    might run again,' not a special code path."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=stuck_after_seconds)).isoformat()
    cur = conn.execute(
        "UPDATE jobs SET status = 'pending', updated_at = ? WHERE status = 'processing' AND updated_at <= ?",
        (now_iso(), cutoff),
    )
    conn.commit()
    return cur.rowcount


def record_alert(conn: sqlite3.Connection, job_id: str, message: str) -> None:
    conn.execute(
        "INSERT INTO alerts (job_id, message, created_at) VALUES (?, ?, ?)",
        (job_id, message, now_iso()),
    )
    conn.commit()


def list_alerts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM alerts ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]
