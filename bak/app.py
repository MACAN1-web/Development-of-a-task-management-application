"""
Task Manager - главный файл приложения

"""

from flask import Flask, request, jsonify, send_from_directory
from database import TaskDatabase
import os

app = Flask(__name__, static_folder="static")
db = TaskDatabase("tasks.db")


# ─── Главная страница ───────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ─── API: получить все задачи ───────────────────────────────────────────────
@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    filter_status = request.args.get("status")  # todo / in_progress / done
    filter_priority = request.args.get("priority")  # low / medium / high
    tasks = db.get_all_tasks(status=filter_status, priority=filter_priority)
    return jsonify({"tasks": tasks, "total": len(tasks)})


# ─── API: создать задачу ────────────────────────────────────────────────────
@app.route("/api/tasks", methods=["POST"])
def create_task():
    data = request.get_json()

    # Валидация
    if not data or not data.get("title"):
        return jsonify({"error": "Название задачи обязательно"}), 400

    title = data["title"].strip()
    if len(title) > 100:
        return jsonify({"error": "Название слишком длинное (макс. 200 символов)"}), 400

    task = db.create_task(
        title=title,
        description=data.get("description", "").strip(),
        priority=data.get("priority", "medium"),
        due_date=data.get("due_date"),
    )
    return jsonify(task), 201


# ─── API: обновить задачу ───────────────────────────────────────────────────
@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    data = request.get_json()
    task = db.update_task(task_id, data)
    if not task:
        return jsonify({"error": "Задача не найдена"}), 404
    return jsonify(task)

 
# ─── API: удалить задачу ────────────────────────────────────────────────────
@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    success = db.delete_task(task_id)
    if not success:
        return jsonify({"error": "Задача не найдена"}), 404
    return jsonify({"message": "Задача удалена"})


# ─── API: статистика ────────────────────────────────────────────────────────
@app.route("/api/stats", methods=["GET"])
def get_stats():
    stats = db.get_stats()
    return jsonify(stats)


if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    print("🚀 Task Manager запущен: http://localhost:5000")
    app.run(debug=True, port=5000)
"""
Task Manager - модуль для работы с базой данных SQLite
"""

import sqlite3
from datetime import datetime


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
    def update_task(self, task_id: int, data: dict) -> dict | None:
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
            high      = conn.execute("SELECT COUNT(*) FROM tasks WHERE priority='high'").fetchone()[0]
        return {
            "total": total,
            "todo": todo,
            "in_progress": in_prog,
            "done": done,
            "high_priority": high,
        }

    # ── Вспомогательный метод ──────────────────────────────────────────────
    def _get_task(self, task_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None
