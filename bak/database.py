"""
Task Manager - модуль для работы с базой данных SQLite
"""

import sqlite3
from datetime import datetime
from typing import Optional


class TaskDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    title       TEXT    NOT NULL,
                    description TEXT    DEFAULT '',
                    status      TEXT    DEFAULT 'todo',
                    priority    TEXT    DEFAULT 'medium',
                    due_date    TEXT,
                    created_at  TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL
                )
            """)
            conn.commit()

    # ── Получить все задачи ────────────────────────────────────────────────
    def get_all_tasks(self, status: str = None, priority: str = None) -> list:
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if priority:
            query += " AND priority = ?"
            params.append(priority)

        query += " ORDER BY created_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    # ── Создать задачу ─────────────────────────────────────────────────────
    def create_task(self, title: str, description: str = "",
                    priority: str = "medium", due_date: str = None) -> dict:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO tasks (title, description, status, priority, due_date, created_at, updated_at)
                   VALUES (?, ?, 'todo', ?, ?, ?, ?)""",
                (title, description, priority, due_date, now, now)
            )
            conn.commit()
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)

    # ── Обновить задачу ────────────────────────────────────────────────────
    def update_task(self, task_id: int, data: dict) -> Optional[dict]:
        allowed = {"title", "description", "status", "priority", "due_date"}
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields:
            return self._get_task(task_id)

        fields["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [task_id]

        with self._connect() as conn:
            conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
            conn.commit()

        return self._get_task(task_id)

    # ── Удалить задачу ─────────────────────────────────────────────────────
    def delete_task(self, task_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        return cursor.rowcount > 0

    # ── Статистика ─────────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        with self._connect() as conn:
            total     = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            todo      = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='todo'").fetchone()[0]
            in_prog   = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='in_progress'").fetchone()[0]
            done      = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='done'").fetchone()[0]
            high      = conn.execute("SELECT COUNT(*) FROM tasks WHERE priority='high' AND status!='done'").fetchone()[0]
        return {
            "total": total,
            "todo": todo,
            "in_progress": in_prog,
            "done": done,
            "high_priority": high,
        }

    # ── Вспомогательный метод ──────────────────────────────────────────────
    def _get_task(self, task_id: int) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None
