"""API server -- accepts a job and answers instantly. It never runs the
slow AI call itself; it only writes a row to the jobs table (the queue) and
returns 202. Run `python worker.py` separately to actually process jobs.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

import db
import jobs

DEFAULT_MAX_ATTEMPTS = 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db(db.get_connection())
    yield


app = FastAPI(
    title="FlyRank Task 6 -- Background Jobs",
    description=(
        "The slow 'AI call' moved out of the request path: POST /jobs answers "
        "instantly with 202, a separate `python worker.py` process does the "
        "work, GET /jobs/{id} reports status."
    ),
    lifespan=lifespan,
)


class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Text to summarize")
    simulate: str | None = Field(
        default=None,
        description="Testing hook: 'flaky' fails twice then succeeds, "
        "'always_fail' never succeeds, omit for a normal run.",
    )


class JobResponse(BaseModel):
    job_id: str
    status: str
    status_url: str


@app.get("/")
def root() -> dict:
    return {
        "service": "background-jobs",
        "docs": "/docs",
        "note": "run `python worker.py` in a separate process to process jobs",
    }


@app.post("/jobs", response_model=JobResponse, status_code=202)
def submit_job(
    body: SummarizeRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobResponse:
    conn = db.get_connection()
    job, _created = jobs.create_job(
        conn,
        payload={"text": body.text, "simulate": body.simulate},
        idempotency_key=idempotency_key,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
    )
    return JobResponse(job_id=job.id, status=job.status, status_url=f"/jobs/{job.id}")


@app.get("/jobs/{job_id}")
def get_job_status(job_id: str) -> dict:
    conn = db.get_connection()
    job = jobs.get_job(conn, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.to_dict()


@app.get("/jobs")
def list_jobs() -> list[dict]:
    conn = db.get_connection()
    return [job.to_dict() for job in jobs.list_all(conn)]


@app.get("/alerts")
def get_alerts() -> list[dict]:
    conn = db.get_connection()
    return jobs.list_alerts(conn)
