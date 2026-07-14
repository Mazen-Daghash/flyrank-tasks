from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

tasks = [
    {"id": 1, "title": "Learn what an API is", "done": True},
    {"id": 2, "title": "Build a hello server", "done": True},
    {"id": 3, "title": "Finish the CRUD API", "done": False},
]


class TaskCreate(BaseModel):
    title: str


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


@app.get("/")
def read_root():
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"],
    }


@app.get("/health")
def read_health():
    return {"status": "ok"}


@app.get("/tasks")
def read_tasks():
    return tasks


@app.get("/tasks/{task_id}")
def read_task(task_id: int):
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    if not task.title or not task.title.strip():
        raise HTTPException(status_code=400, detail="Title is required and cannot be empty")
    new_id = max((t["id"] for t in tasks), default=0) + 1
    new_task = {"id": new_id, "title": task.title.strip(), "done": False}
    tasks.append(new_task)
    return new_task


@app.put("/tasks/{task_id}")
def update_task(task_id: int, update: TaskUpdate):
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
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    tasks.remove(task)
    return None
