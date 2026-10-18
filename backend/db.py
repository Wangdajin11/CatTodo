import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "cattodo.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            color TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            start_time TEXT,
            end_time TEXT,
            due_date TEXT,
            done INTEGER DEFAULT 0,
            is_private INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(owner_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS typing_daily (
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            keys INTEGER DEFAULT 0,
            minutes INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, day)
        );
        """
    )
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO users (id, name, color) VALUES (?, ?, ?)",
            [(1, "我", "#4A90D9"), (2, "TA", "#F5A623")],
        )
    conn.commit()
    conn.close()
