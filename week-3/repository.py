from abc import ABC, abstractmethod
from typing import List, Optional

import os

from db import get_connection


class TaskRepository(ABC):
    """The storage contract. Both the in-memory and Postgres versions implement this,
    so the routes in main.py never need to know which one is in use."""

    @abstractmethod
    def list_tasks(self) -> List[dict]:
        ...

    @abstractmethod
    def get_task(self, task_id: int) -> Optional[dict]:
        ...

    @abstractmethod
    def create_task(self, title: str) -> dict:
        ...

    @abstractmethod
    def update_task(
        self, task_id: int, title: Optional[str], done: Optional[bool]
    ) -> Optional[dict]:
        ...

    @abstractmethod
    def delete_task(self, task_id: int) -> bool:
        ...


class InMemoryTaskRepository(TaskRepository):
    """The original A2 store, kept so the app can run with no database (STORAGE=memory)."""

    def __init__(self) -> None:
        self._tasks = [
            {"id": 1, "title": "Learn what an API is", "done": True},
            {"id": 2, "title": "Build a hello server", "done": True},
            {"id": 3, "title": "Finish the CRUD API", "done": False},
        ]

    def list_tasks(self) -> List[dict]:
        return list(self._tasks)

    def get_task(self, task_id: int) -> Optional[dict]:
        return next((t for t in self._tasks if t["id"] == task_id), None)

    def create_task(self, title: str) -> dict:
        new_id = max((t["id"] for t in self._tasks), default=0) + 1
        task = {"id": new_id, "title": title, "done": False}
        self._tasks.append(task)
        return task

    def update_task(
        self, task_id: int, title: Optional[str], done: Optional[bool]
    ) -> Optional[dict]:
        task = self.get_task(task_id)
        if task is None:
            return None
        if title is not None:
            task["title"] = title
        if done is not None:
            task["done"] = done
        return task

    def delete_task(self, task_id: int) -> bool:
        task = self.get_task(task_id)
        if task is None:
            return False
        self._tasks.remove(task)
        return True


class PostgresTaskRepository(TaskRepository):
    """Postgres-backed store. Same interface, same behaviour, data that survives restarts."""

    def __init__(self) -> None:
        self._conn = get_connection()

    def list_tasks(self) -> List[dict]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks ORDER BY id")
            return [dict(row) for row in cur.fetchall()]

    def get_task(self, task_id: int) -> Optional[dict]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT id, title, done FROM tasks WHERE id = %s", (task_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def create_task(self, title: str) -> dict:
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tasks (title) VALUES (%s) RETURNING id, title, done",
                (title,),
            )
            self._conn.commit()
            return dict(cur.fetchone())

    def update_task(
        self, task_id: int, title: Optional[str], done: Optional[bool]
    ) -> Optional[dict]:
        sets, params = [], []
        if title is not None:
            sets.append("title = %s")
            params.append(title)
        if done is not None:
            sets.append("done = %s")
            params.append(done)
        params.append(task_id)
        with self._conn.cursor() as cur:
            cur.execute(
                f"UPDATE tasks SET {', '.join(sets)} WHERE id = %s "
                "RETURNING id, title, done",
                params,
            )
            row = cur.fetchone()
            self._conn.commit()
            return dict(row) if row else None

    def delete_task(self, task_id: int) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tasks WHERE id = %s RETURNING id", (task_id,)
            )
            deleted = cur.fetchone() is not None
            self._conn.commit()
            return deleted


def get_repository() -> TaskRepository:
    """Pick the store from the STORAGE env var. Swapping storage changes ONLY this line
    (or the env var) - main.py and the routes stay exactly the same."""
    storage = os.environ.get("STORAGE", "postgres").lower()
    if storage == "memory":
        return InMemoryTaskRepository()
    return PostgresTaskRepository()
