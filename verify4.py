"""CatTodo verify4 — M3: 周复盘、任务编辑、超时提醒、打气。"""
import asyncio
import json
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

BASE = "http://127.0.0.1:8017"
passed = 0


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"}, method=method,
    )
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())


def check(name, cond, detail=""):
    global passed
    assert cond, f"{name} 失败 {detail}"
    passed += 1
    print(f"  [PASS] {name}")


import backend.models as models  # noqa: E402
import backend.db as db  # noqa: E402

# 基线
review0 = req("GET", "/api/review/weekly")
cur = req("GET", "/api/focus/current")
assert cur is None, "当前有残留会话，验证脚本不能安全运行"
check("周复盘接口返回结构", "monday" in review0 and "users" in review0)
max_task_id = db.get_conn().execute("SELECT MAX(id) FROM tasks").fetchone()[0] or 0
max_focus_id = db.get_conn().execute("SELECT MAX(id) FROM focus_sessions").fetchone()[0] or 0

conn = db.get_conn()
checkin_before = bool(conn.execute(
    "SELECT 1 FROM checkins WHERE user_id = 1 AND day = ?", (date.today().isoformat(),)
).fetchone())
conn.close()

# 本周内非今天的一天（不污染真实打字数据）
sample_day = date.today() - timedelta(days=1)
monday = date.today() - timedelta(days=date.today().weekday())
if sample_day < monday:
    sample_day = monday

try:
    # 1. 完成任务统计
    t1 = req("POST", "/api/tasks", {
        "title": "M3验证-任务A", "owner_id": 1,
        "due_date": date.today().isoformat(),
        "start_time": "2026-10-18 09:00", "end_time": "2026-10-18 10:00",
    })
    t2 = req("POST", "/api/tasks", {
        "title": "M3验证-任务B", "owner_id": 2,
        "due_date": date.today().isoformat(),
    })
    req("PATCH", f"/api/tasks/{t1['id']}", {"done": 1})
    r1 = req("GET", "/api/review/weekly")
    check("完成任务计入复盘(我)", r1["users"]["1"]["tasks_done"] == review0["users"]["1"]["tasks_done"] + 1)

    req("PATCH", f"/api/tasks/{t1['id']}", {"done": 0})
    r2 = req("GET", "/api/review/weekly")
    check("取消完成后复盘回退", r2["users"]["1"]["tasks_done"] == review0["users"]["1"]["tasks_done"])

    # 2. 任务编辑
    req("PATCH", f"/api/tasks/{t1['id']}", {
        "done": 1, "title": "M3验证-改标题", "description": "加了描述",
        "due_date": (date.today() + timedelta(days=1)).isoformat(),
    })
    edited = req("GET", f"/api/tasks/{t1['id']}")
    check("编辑标题/描述/截止", edited["title"] == "M3验证-改标题"
          and edited["description"] == "加了描述"
          and edited["due_date"] == (date.today() + timedelta(days=1)).isoformat())
    check("completed_at 已写入", bool(edited["completed_at"]), edited.get("completed_at"))

    req("PATCH", f"/api/tasks/{t2['id']}", {"done": 1})
    r3 = req("GET", "/api/review/weekly")
    check("完成任务计入复盘(TA)", r3["users"]["2"]["tasks_done"] == review0["users"]["2"]["tasks_done"] + 1)

    # 3. 打卡天数
    if not checkin_before:
        req("POST", "/api/checkin", {"user_id": 1})
    r4 = req("GET", "/api/review/weekly")
    check("打卡天数计入复盘", r4["users"]["1"]["checkin_days"] >= review0["users"]["1"]["checkin_days"] + (0 if checkin_before else 1))

    # 4. 已完成番茄钟
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    sid = models.create_focus_session(1, 25, now.isoformat(), (now + timedelta(minutes=25)).isoformat(), [1])
    models.update_focus_session(sid, participants=[1], status="done")
    r5 = req("GET", "/api/review/weekly")
    check("番茄钟数与分钟计入复盘",
          r5["users"]["1"]["focus_count"] == review0["users"]["1"]["focus_count"] + 1
          and r5["users"]["1"]["focus_minutes"] == review0["users"]["1"]["focus_minutes"] + 25)
    check("TA 未参与不计入", r5["users"]["2"]["focus_count"] == review0["users"]["2"]["focus_count"])

    # 5. 打字键数（直接写入本周内非今天的一天，避免污染真实数据）
    conn2 = db.get_conn()
    conn2.execute(
        "INSERT INTO typing_daily (user_id, day, keys, minutes) VALUES (?, ?, 123, 1)",
        (1, sample_day.isoformat()),
    )
    conn2.commit()
    conn2.close()
    r6 = req("GET", "/api/review/weekly")
    check("打字键数计入复盘", r6["users"]["1"]["keys"] == review0["users"]["1"]["keys"] + 123)

    # 6. 周范围正确（周一到周日）
    check("周范围为周一到周日",
          date.fromisoformat(r6["monday"]).weekday() == 0
          and date.fromisoformat(r6["sunday"]) == date.fromisoformat(r6["monday"]) + timedelta(days=6))
    rp = req("GET", "/api/review/weekly?week_offset=1")
    check("上周复盘可查", rp["monday"] == (monday - timedelta(days=7)).isoformat())

    # 7. 超时提醒（进程内，阈值改为 2 秒）
    import backend.app as appmod
    appmod.OVERTIME_SECONDS = 2
    collected = []

    async def fake_broadcast(msg):
        collected.append(msg)

    appmod.hub.broadcast = fake_broadcast

    async def over_test():
        await appmod.focus.start(1, 5)
        await asyncio.sleep(2.6)
        assert any(m["type"] == "focus:overtime" for m in collected), "未收到 focus:overtime"
        await appmod.focus.stop()

    asyncio.run(over_test())
    check("专注超 45 分钟广播", any(m["type"] == "focus:overtime" for m in collected))
    check("停止后调度取消", appmod.focus.current is None)

    # 8. 打气 WS 广播
    import websockets

    async def cheer_test():
        async with websockets.connect("ws://127.0.0.1:8017/ws") as ws:
            req("POST", "/api/focus/cheer", {"from_user_id": 2})
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(msg)
            assert data["type"] == "focus:cheer" and data["from"] == 2, data

    asyncio.run(cheer_test())
    check("打气事件 WS 广播", True)

finally:
    # 清理
    conn = db.get_conn()
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM tasks WHERE id > ?", (max_task_id,)
    ).fetchall()]
    if ids:
        q = ",".join("?" for _ in ids)
        conn.execute(f"DELETE FROM subtasks WHERE task_id IN ({q})", ids)
        conn.execute(f"DELETE FROM tasks WHERE id IN ({q})", ids)
    conn.execute("DELETE FROM focus_sessions WHERE id > ?", (max_focus_id,))
    if not checkin_before:
        conn.execute("DELETE FROM checkins WHERE user_id = 1 AND day = ?", (date.today().isoformat(),))
    conn.execute("DELETE FROM typing_daily WHERE user_id = 1 AND day = ?", (sample_day.isoformat(),))
    conn.commit()
    conn.close()

# 清理后基线恢复
r_end = req("GET", "/api/review/weekly")
check("清理后数据恢复", r_end["users"]["1"]["tasks_done"] == review0["users"]["1"]["tasks_done"]
      and r_end["users"]["1"]["focus_count"] == review0["users"]["1"]["focus_count"]
      and r_end["users"]["1"]["keys"] == review0["users"]["1"]["keys"])

print(f"\nALL CHECKS PASSED: {passed} 项")
