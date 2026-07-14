import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from repository import TaskRepository, get_repository

load_dotenv()

app = FastAPI()

repo: TaskRepository = get_repository()


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
        "version": "2.0",
        "storage": os.environ.get("STORAGE", "postgres"),
        "endpoints": ["/tasks"],
    }


@app.get("/health")
def read_health():
    """Health check used to confirm the server (and its store) is alive."""
    return {"status": "ok"}


@app.get("/tasks")
def read_tasks():
    """List every task in the store."""
    return repo.list_tasks()


@app.get("/tasks/{task_id}")
def read_task(task_id: int):
    """Get a single task by its id, or 404 if it does not exist."""
    task = repo.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    """Create a new task. Returns 201 with the created task, or 400 if the title is empty."""
    if not task.title or not task.title.strip():
        raise HTTPException(status_code=400, detail="Title is required and cannot be empty")
    return repo.create_task(task.title.strip())


@app.put("/tasks/{task_id}")
def update_task(task_id: int, update: TaskUpdate):
    """Update a task's title and/or done flag. Returns 404 if missing, 400 if the body is empty."""
    if update.title is None and update.done is None:
        raise HTTPException(status_code=400, detail="Provide a title or done value to update")
    if update.title is not None and not update.title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    task = repo.update_task(task_id, update.title, update.done)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    """Delete a task by id. Returns 204 with no content, or 404 if it does not exist."""
    if not repo.delete_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return None
