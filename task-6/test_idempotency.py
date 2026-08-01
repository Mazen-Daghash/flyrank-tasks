"""Proves the two non-negotiables that don't show up just by reading the
code: run this, don't just trust the comments.

    python test_idempotency.py

1. If the same job_id gets claimed twice -- queue redelivery, two worker
   processes racing on the same row, a requeue racing the original worker
   that hadn't finished yet -- only one claim wins.
2. If a client retries its POST (network blip, timeout, at-least-once
   delivery on their end) with the same Idempotency-Key, it gets back the
   original job, not a second one.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import db
import jobs


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test_jobs.db"

        # Two connections standing in for two separate worker processes
        # (or the same worker seeing the same job_id twice) hitting the
        # same database file.
        conn_a = db.get_connection(db_path)
        conn_b = db.get_connection(db_path)
        db.init_db(conn_a)

        job, created = jobs.create_job(conn_a, payload={"text": "hello world"}, idempotency_key=None)
        assert created, "a job with no idempotency key should always be created"

        claimed_by_a = jobs.try_claim(conn_a, job.id)
        claimed_by_b = jobs.try_claim(conn_b, job.id)  # the duplicate delivery

        assert claimed_by_a is True, "the first claim should succeed"
        assert claimed_by_b is False, "the second claim of the SAME job must be rejected"

        after = jobs.get_job(conn_a, job.id)
        assert after.status == "processing"
        print("OK: duplicate delivery of the same job_id only lets one claim through")

        # A client retrying its POST with the same Idempotency-Key.
        conn_c = db.get_connection(db_path)
        first, first_created = jobs.create_job(
            conn_c, payload={"text": "hello world"}, idempotency_key="client-key-1"
        )
        replay, replay_created = jobs.create_job(
            conn_c, payload={"text": "hello world"}, idempotency_key="client-key-1"
        )

        assert first_created is True
        assert replay_created is False, "replaying the same Idempotency-Key must not create a new job"
        assert first.id == replay.id
        print("OK: replaying the same Idempotency-Key returns the original job, not a new one")

        # Windows holds the file open until every connection is closed --
        # close them before TemporaryDirectory tries to delete the file.
        for conn in (conn_a, conn_b, conn_c):
            conn.close()


if __name__ == "__main__":
    main()
    print("\nAll idempotency guarantees hold.")
