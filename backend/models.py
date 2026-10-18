import json
from datetime import date, timedelta

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
    if "done" in changes:
        if changes["done"]:
            sets += ", completed_at = datetime('now','localtime')"
        else:
            sets += ", completed_at = NULL"
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


def checkin(user_id):
    conn = db.get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO checkins (user_id, day) VALUES (?, date('now','localtime'))",
        (user_id,),
    )
    conn.commit()
    conn.close()
    return checkin_info(user_id)


def checkin_info(user_id):
    conn = db.get_conn()
    rows = [r["day"] for r in conn.execute(
        "SELECT day FROM checkins WHERE user_id = ?", (user_id,))]
    conn.close()
    days = set(rows)
    today = date.today()
    today_s = today.isoformat()
    cur = today if today_s in days else today - timedelta(days=1)
    streak = 0
    while cur.isoformat() in days:
        streak += 1
        cur -= timedelta(days=1)
    return {"streak": streak, "today": today_s in days}


def all_checkins():
    return {u["id"]: checkin_info(u["id"]) for u in users()}


def create_focus_session(started_by, duration_min, start_at, end_at, participants):
    conn = db.get_conn()
    cur = conn.execute(
        "INSERT INTO focus_sessions (started_by, duration_min, start_at, end_at, participants, status) "
        "VALUES (?, ?, ?, ?, ?, 'running')",
        (started_by, duration_min, start_at, end_at, json.dumps(participants)),
    )
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid


def update_focus_session(sid, participants=None, status=None):
    conn = db.get_conn()
    if participants is not None:
        conn.execute(
            "UPDATE focus_sessions SET participants = ? WHERE id = ?",
            (json.dumps(participants), sid),
        )
    if status is not None:
        conn.execute("UPDATE focus_sessions SET status = ? WHERE id = ?", (status, sid))
    conn.commit()
    conn.close()


def weekly_review(week_offset=0):
    today = date.today()
    monday = today - timedelta(days=today.weekday(), weeks=week_offset)
    sunday = monday + timedelta(days=6)
    start_s = monday.isoformat() + " 00:00:00"
    end_s = sunday.isoformat() + " 23:59:59"
    conn = db.get_conn()
    result = {}
    for u in users():
        uid = u["id"]
        done_count = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE owner_id = ? AND completed_at BETWEEN ? AND ?",
            (uid, start_s, end_s),
        ).fetchone()[0]
        keys_row = conn.execute(
            "SELECT COALESCE(SUM(keys), 0) FROM typing_daily WHERE user_id = ? AND day BETWEEN ? AND ?",
            (uid, monday.isoformat(), sunday.isoformat()),
        ).fetchone()[0]
        checkin_days = conn.execute(
            "SELECT COUNT(*) FROM checkins WHERE user_id = ? AND day BETWEEN ? AND ?",
            (uid, monday.isoformat(), sunday.isoformat()),
        ).fetchone()[0]
        focus_rows = conn.execute(
            "SELECT duration_min, participants FROM focus_sessions "
            "WHERE status = 'done' AND created_at BETWEEN ? AND ?",
            (start_s, end_s),
        ).fetchall()
        focus_count = 0
        focus_minutes = 0
        for r in focus_rows:
            if uid in json.loads(r["participants"]):
                focus_count += 1
                focus_minutes += r["duration_min"]
        result[uid] = {
            "tasks_done": done_count,
            "keys": keys_row,
            "checkin_days": checkin_days,
            "focus_count": focus_count,
            "focus_minutes": focus_minutes,
        }
    conn.close()
    return {"monday": monday.isoformat(), "sunday": sunday.isoformat(), "users": result}
