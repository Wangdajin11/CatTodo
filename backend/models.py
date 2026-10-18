from . import db

TASK_FIELDS = {"title", "description", "start_time", "end_time", "due_date", "done", "is_private"}


def users():
    conn = db.get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _attach_subtasks(conn, tasks):
    sub_map = {}
    rows = conn.execute("SELECT * FROM subtasks ORDER BY id").fetchall()
    for r in rows:
        sub_map.setdefault(r["task_id"], []).append(dict(r))
    for t in tasks:
        t["subtasks"] = sub_map.get(t["id"], [])
    return tasks


def list_tasks(viewer_id):
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE is_private = 0 OR owner_id = ? ORDER BY start_time, id",
        (viewer_id,),
    ).fetchall()
    tasks = [dict(r) for r in rows]
    _attach_subtasks(conn, tasks)
    conn.close()
    return tasks


def get_task(task_id):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        conn.close()
        return None
    tasks = [dict(row)]
    _attach_subtasks(conn, tasks)
    conn.close()
    return tasks[0]


def create_task(title, owner_id, start_time=None, end_time=None, due_date=None,
                is_private=0, description=""):
    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO tasks (title, owner_id, start_time, end_time, due_date, is_private, description) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (title, owner_id, start_time, end_time, due_date, is_private, description),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    task = dict(row)
    task["subtasks"] = []
    conn.close()
    return task


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
    conn.close()
    return get_task(task_id)


def delete_task(task_id):
    conn = db.get_conn()
    conn.execute("DELETE FROM subtasks WHERE task_id = ?", (task_id,))
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


def add_subtask(task_id, title):
    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO subtasks (task_id, title) VALUES (?, ?)",
        (task_id, title),
    )
    conn.commit()
    conn.close()
    return subtasks_of(task_id)


def set_subtask_done(subtask_id, done):
    conn = db.get_conn()
    conn.execute("UPDATE subtasks SET done = ? WHERE id = ?", (done, subtask_id))
    conn.commit()
    row = conn.execute("SELECT * FROM subtasks WHERE id = ?", (subtask_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_subtask(subtask_id):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM subtasks WHERE id = ?", (subtask_id,)).fetchone()
    if not row:
        conn.close()
        return None
    task_id = row["task_id"]
    conn.execute("DELETE FROM subtasks WHERE id = ?", (subtask_id,))
    conn.commit()
    conn.close()
    return task_id


def subtasks_of(task_id):
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM subtasks WHERE task_id = ? ORDER BY id", (task_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
