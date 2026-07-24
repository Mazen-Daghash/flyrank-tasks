from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from db import get_connection, init_db

app = FastAPI()

init_db()


def row_to_task(row) -> dict:
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


class TaskCreate(BaseModel):
    title: str


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


@app.get("/")
def read_root():
    """Describe the API: its name, version, and available endpoints."""
    return {
        "name": "Task API",
        "version": "3.0",
        "storage": "sqlite",
        "endpoints": ["/tasks"],
    }


@app.get("/health")
def read_health():
    """Health check used to confirm the server is alive."""
    return {"status": "ok"}


@app.get("/tasks")
def read_tasks():
    """List every task in the database."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM tasks").fetchall()
    finally:
        conn.close()
    return [row_to_task(row) for row in rows]


@app.get("/tasks/{task_id}")
def read_task(task_id: int):
    """Get a single task by its id, or 404 if it does not exist."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return row_to_task(row)


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    """Create a new task. Returns 201 with the created task, or 400 if the title is empty."""
    if not task.title or not task.title.strip():
        raise HTTPException(status_code=400, detail="Title is required and cannot be empty")
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)", (task.title.strip(), 0)
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    finally:
        conn.close()
    return row_to_task(row)


@app.put("/tasks/{task_id}")
def update_task(task_id: int, update: TaskUpdate):
    """Update a task's title and/or done flag. Returns 404 if missing, 400 if the body is empty."""
    if update.title is None and update.done is None:
        raise HTTPException(status_code=400, detail="Provide a title or done value to update")
    if update.title is not None and not update.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        new_title = update.title.strip() if update.title is not None else existing["title"]
        new_done = int(update.done) if update.done is not None else existing["done"]

        conn.execute(
            "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
            (new_title, new_done, task_id),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()
    return row_to_task(row)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    """Delete a task by id. Returns 204 with no content, or 404 if it does not exist."""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    finally:
        conn.close()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return None
