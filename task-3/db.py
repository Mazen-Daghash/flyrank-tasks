import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "tasks.db"

SEED_TASKS = [
    ("Learn what an API is", 1),
    ("Build a hello server", 1),
    ("Finish the CRUD API", 0),
]


def get_connection() -> sqlite3.Connection:
    """Open (and, on first call, create) the SQLite database file."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the tasks table if missing, and seed it only if it's empty."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done  INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO tasks (title, done) VALUES (?, ?)", SEED_TASKS
            )
            conn.commit()
    finally:
        conn.close()
