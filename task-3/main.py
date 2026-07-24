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
    new_id = max((t["id"] for t in tasks), default=0) + 1
    new_task = {"id": new_id, "title": task.title.strip(), "done": False}
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}")
def update_task(task_id: int, update: TaskUpdate):
    """Update a task's title and/or done flag. Returns 404 if missing, 400 if the body is empty."""
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if update.title is None and update.done is None:
        raise HTTPException(status_code=400, detail="Provide a title or done value to update")
    if update.title is not None:
        if not update.title.strip():
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        task["title"] = update.title.strip()
    if update.done is not None:
        task["done"] = update.done
    return task


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    """Delete a task by id. Returns 204 with no content, or 404 if it does not exist."""
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    tasks.remove(task)
    return None
