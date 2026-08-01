# Task 6 — Background Jobs: accept fast, work in the background, report status

FlyRank Backend Track · Week 6

A slow "AI call" moved out of the request path. `POST /jobs` answers in milliseconds with
`202 Accepted`; a completely separate `python worker.py` process does the actual (simulated)
several-second AI call; `GET /jobs/{id}` reports what happened. There's no real AI API here —
[the previous "A6" assignment that was supposed to feed this one didn't exist anywhere in this
repo](#no-real-a6-to-start-from), so the slow call is a stand-in with the same shape a real one
would have: network-latency delay, occasional provider failures, one function to swap for a real
`anthropic` call later.

## Run it

Two processes, in two terminals:

```bash
cd task-6
pip install -r requirements.txt

# terminal 1
uvicorn main:app --port 8006

# terminal 2
python worker.py
```

Then:

```bash
curl -i -X POST http://localhost:8006/jobs \
  -H "Content-Type: application/json" \
  -d '{"text":"Some long piece of text that would take an LLM a few seconds to summarize."}'
# -> 202 instantly, {"job_id":"...","status":"pending","status_url":"/jobs/..."}

curl http://localhost:8006/jobs/<job_id>
# -> {"status":"pending"} at first, then "completed" a few seconds later once the worker gets to it
```

Swagger UI: http://localhost:8006/docs

## Why two processes, not `BackgroundTasks`

FastAPI's `BackgroundTasks` runs the slow work after the response, but still inside the API
process — it dies if that process restarts, doesn't scale independently of the API, and doesn't
really match "a worker does the work." Here, the `jobs` SQLite table **is** the queue: a `pending`
row is a message waiting to be picked up. The API process only ever inserts a row and returns.
`worker.py` is a standalone script that polls that table, claims a row, and runs the job — it can
be stopped, restarted, or run multiple times in parallel without the API server knowing or caring.

## The three non-negotiables

**Jobs will run twice.** A message queue redelivering, a worker crashing mid-job and its work
getting requeued, two `worker.py` processes racing on the same row — all of it is the same
underlying event: *the same `job_id` gets handed to a worker more than once.* The fix is one
atomic SQL statement ([`jobs.py`](jobs.py) `try_claim`):

```sql
UPDATE jobs SET status = 'processing', ... WHERE id = ? AND status = 'pending' AND available_at <= ?
```

Only one caller's `UPDATE` can match `status = 'pending'` — the loser's `rowcount` comes back `0`
and it just moves on. [`test_idempotency.py`](test_idempotency.py) proves this directly (two
connections, one job, only one claim succeeds) rather than hoping a real race reproduces it:

```bash
python test_idempotency.py
```

I also verified it the "real" way — burst 6 jobs, start two `worker.py` processes at the same
instant, and confirm no job ID shows up as completed in both logs (see
[Verified end-to-end](#verified-end-to-end) below).

There's a second flavor of "runs twice": a client's own retry (their request timed out, they
retry the POST). `Idempotency-Key` handles that — send the same key twice, get the same job back,
not a second one:

```bash
curl -X POST http://localhost:8006/jobs -H "Idempotency-Key: my-key-1" -H "Content-Type: application/json" -d '{"text":"..."}'
curl -X POST http://localhost:8006/jobs -H "Idempotency-Key: my-key-1" -H "Content-Type: application/json" -d '{"text":"..."}'
# same job_id both times
```

**Jobs will fail.** `fail_or_retry` in [`jobs.py`](jobs.py) bumps the attempt count and, under
`max_attempts` (default 3), reschedules with exponential backoff (2s, 4s, 8s...) by pushing
`available_at` into the future — the worker's claim query (`available_at <= now`) naturally skips
it until then. Once attempts hit the max, the job is marked `failed` for good.

**Someone must find out.** When a job is marked permanently `failed`, an alert row is written to
the `alerts` table and printed to the worker's own log with an `[ALERT]` tag — the two channels a
real on-call setup would actually have: a queryable record (`GET /alerts`) and a log line a log
aggregator/alerting rule can match on. Swapping the `record_alert` call for a Slack/PagerDuty
webhook is a one-function change; the job/retry logic around it doesn't need to know the
difference.

## Testing the failure paths on purpose

The request body has a `simulate` field that's a testing hook, not something a real client would
send:

```bash
# fails twice, then succeeds on the 3rd attempt (max_attempts=3) -- watch it recover
curl -X POST http://localhost:8006/jobs -H "Content-Type: application/json" \
  -d '{"text":"watch this retry","simulate":"flaky"}'

# always fails -- watch it exhaust retries and fire an alert
curl -X POST http://localhost:8006/jobs -H "Content-Type: application/json" \
  -d '{"text":"watch this fail for good","simulate":"always_fail"}'

curl http://localhost:8006/alerts
```

## Endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/jobs` | Submit a job. Optional `Idempotency-Key` header. | `202`, `{job_id, status, status_url}` |
| GET | `/jobs/{id}` | Current status/result/error/attempts of one job | `200`, or `404` if unknown |
| GET | `/jobs` | List every job (newest first) | `200` |
| GET | `/alerts` | Every alert a permanently-failed job has fired | `200` |

## Files

| File | Job |
|------|-----|
| [`db.py`](db.py) | SQLite connection + schema (`jobs`, `alerts` tables) |
| [`jobs.py`](jobs.py) | The job repository — every state transition (`create_job`, `try_claim`, `claim_next_job`, `complete_job`, `fail_or_retry`, `requeue_stuck_jobs`, `record_alert`) as one atomic statement each |
| [`ai_provider.py`](ai_provider.py) | The slow operation — stands in for a real LLM API call |
| [`worker.py`](worker.py) | Standalone polling worker process |
| [`main.py`](main.py) | FastAPI app — accepts jobs, reports status, never does slow work itself |
| [`test_idempotency.py`](test_idempotency.py) | Proves duplicate-claim and Idempotency-Key replay are safe |

## Crash recovery

If a worker dies mid-job, its claimed row is stuck `processing` forever unless something notices.
Every worker, on startup, runs `requeue_stuck_jobs`: any job that's been `processing` for more
than 60s with no update gets put back to `pending`. Whichever worker (or worker restart) picks it
up next runs it through the exact same `try_claim` path as anything else — crash recovery isn't a
special case, it's just one more way the same job might get attempted again, which is exactly what
the idempotent claim already handles.

## Verified end-to-end

Ran it for real, not just read the code:

- **Fast accept**: `POST /jobs` returned `202` in ~0.4s (first-request overhead) while the worker
  wasn't even running yet — three jobs sat `pending`, proving the endpoint never touches the slow
  path itself.
- **Normal job**: completed in 1 attempt.
- **`simulate: flaky`**: failed attempt 1, failed attempt 2 (backoff in between), completed on
  attempt 3 — `attempts: 2` in the final record (0-indexed: it took 2 retries).
- **`simulate: always_fail`**: failed all 3 attempts, ended `status: failed`, and `GET /alerts`
  showed exactly one alert row referencing that job ID.
- **Two workers, one race**: submitted 6 jobs in a burst, launched `worker.py worker-A` and
  `worker.py worker-B` at the same time. Final logs: worker-A completed jobs 1, 3, 5; worker-B
  completed jobs 2, 4, 6. Six jobs in, six completions out, zero overlap — no job appears
  "completed" in both logs, which is the atomic claim doing its job under an actual race, not a
  simulated one.

## No real A6 to start from

The prompt for this task assumed an existing "A6" assignment that makes a slow AI call inside a
request handler ("your A6 AI call is perfect"). Searched this whole repo (`task-1` through
`task-5`, `week-3`) and the sibling project folders on disk — no A6, no AI/LLM API call anywhere.
Rather than invent a full LLM integration as a prerequisite, `ai_provider.py`'s
`call_ai_provider` stands in for it: same shape (network delay, a text-in/text-out contract,
provider errors), swappable for a real API call without touching anything else in this task.

## Notes

- `jobs.db` is git-ignored, same as `task-3`'s `tasks.db` — it's created automatically by
  whichever process (API or worker) starts first.
- Multiple `python worker.py` instances can run at once for more throughput; nothing about the
  claim logic assumes there's only one.
- The demo failure modes (`flaky`, `always_fail`) are deterministic on purpose — a real
  network-flake demo wouldn't reproduce reliably enough to verify against.
