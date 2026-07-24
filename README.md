# flyrank-tasks

A collection of backend tasks completed for the FlyRank internship (Backend Track).
Each task lives in its own numbered folder.

## Tasks

| Folder  | Task                                   | Stack            |
|---------|----------------------------------------|------------------|
| `task-1/` | W2 · A1 — CRUD to-do list API         | Python + FastAPI |
| `task-2/` | (existing task)                        | Python + FastAPI |
| `task-3/` | W3 · A2 — CRUD API backed by SQLite   | Python + FastAPI + SQLite |
| `task-4/` | W2 · A4 — Auth with Supabase (login & protected routes) | Python + FastAPI + Supabase Auth |

## Running a task

Each task is self-contained. For example, to run `task-1`:

```bash
cd task-1
pip install -r requirements.txt
uvicorn task-1.main:app --port 8000
```

Then open http://localhost:8000/docs for interactive Swagger UI.

See each task folder's `README.md` for details, endpoints, and examples.
