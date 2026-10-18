from . import db

TASK_FIELDS = {"title", "start_time", "end_time", "due_date", "done", "is_private"}


def users():
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_tasks(viewer_id):
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE is_private = 0 OR owner_id = ? ORDER BY start_time, id",
        (viewer_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_task(task_id):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_task(title, owner_id, start_time=None, end_time=None, due_date=None, is_private=0):
    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO tasks (title, owner_id, start_time, end_time, due_date, is_private) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title, owner_id, start_time, end_time, due_date, is_private),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)


def update_task(task_id, changes):
    conn = db.get_conn()
    keys = [k for k in changes if k in TASK_FIELDS]
    if not keys:
        conn.close()
        return get_task(task_id)
    sets = ", ".join(f"{k} = ?" for k in keys)
    values = [changes[k] for k in keys]
    conn.execute(
        f"UPDATE tasks SET {sets}, updated_at = datetime('now','localtime') WHERE id = ?",
        (*values, task_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_task(task_id):
    conn = db.get_conn()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def add_typing(user_id, keys, minutes):
    conn = db.get_conn()
    conn.execute(
        """INSERT INTO typing_daily (user_id, day, keys, minutes) VALUES (?, date('now','localtime'), ?, ?)
           ON CONFLICT(user_id, day) DO UPDATE SET
             keys = keys + excluded.keys,
             minutes = minutes + excluded.minutes""",
        (user_id, keys, minutes),
    )
    conn.commit()
    conn.close()


def typing_today():
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT user_id, keys, minutes FROM typing_daily WHERE day = date('now','localtime')"
    ).fetchall()
    conn.close()
    return {r["user_id"]: {"keys": r["keys"], "minutes": r["minutes"]} for r in rows}
