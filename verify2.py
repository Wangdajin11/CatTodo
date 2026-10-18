import asyncio
import json
import urllib.request

BASE = "http://127.0.0.1:8017"


def req(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(r, timeout=5) as resp:
        return json.loads(resp.read())


def main():
    t = req("/api/tasks", "POST", {
        "title": "保研材料",
        "owner_id": 1,
        "description": "个人陈述 + 成绩单，重点写量化竞赛经历",
        "due_date": "2026-10-25",
    })
    assert t["description"].startswith("个人陈述"), t
    assert t["subtasks"] == [], t

    subs = req(f"/api/tasks/{t['id']}/subtasks", "POST", {"title": "写个人陈述"})
    assert len(subs) == 1 and subs[0]["title"] == "写个人陈述", subs
    subs = req(f"/api/tasks/{t['id']}/subtasks", "POST", {"title": "盖章成绩单"})
    assert len(subs) == 2

    req(f"/api/subtasks/{subs[0]['id']}", "PATCH", {"done": 1})
    fresh = req("/api/tasks?viewer_id=1")
    ft = [x for x in fresh if x["id"] == t["id"]][0]
    assert ft["description"].startswith("个人陈述")
    assert sum(1 for s in ft["subtasks"] if s["done"]) == 1, ft
    print("description + subtasks: ok", len(ft["subtasks"]), "subtasks")

    req("/api/presence", "POST", {"user_id": 1, "status": "focus", "status_text": "在背单词"})
    p = req("/api/presence")
    assert p["1"] == {"status": "focus", "text": "在背单词"}, p
    print("presence text: ok ->", p)

    req(f"/api/subtasks/{subs[1]['id']}", "DELETE")
    ft2 = [x for x in req("/api/tasks?viewer_id=1") if x["id"] == t["id"]][0]
    assert len(ft2["subtasks"]) == 1
    print("subtask delete: ok")

    for x in req("/api/tasks?viewer_id=1"):
        req(f"/api/tasks/{x['id']}", "DELETE")
    print("cleanup: ok")


async def ws_test():
    import websockets
    async with websockets.connect("ws://127.0.0.1:8017/ws") as ws:
        await asyncio.sleep(0.3)
        t = req("/api/tasks", "POST", {"title": "子任务WS", "owner_id": 1})
        req(f"/api/tasks/{t['id']}/subtasks", "POST", {"title": "子1"})
        m1 = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
        m2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
        assert m1["type"] == "task:created", m1
        assert m2["type"] == "subtask:changed" and len(m2["subtasks"]) == 1, m2
        print("ws subtask: ok")
        req(f"/api/tasks/{t['id']}", "DELETE")
        await asyncio.wait_for(ws.recv(), timeout=3)


main()
asyncio.run(ws_test())
print("ALL CHECKS PASSED")
