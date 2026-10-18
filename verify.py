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
    t1 = req("/api/tasks", "POST", {"title": "写保研个人陈述", "owner_id": 1, "start_time": "2026-10-18 14:00", "end_time": "2026-10-18 16:00", "due_date": "2026-10-20"})
    t2 = req("/api/tasks", "POST", {"title": "一起自习 18:00", "owner_id": 2, "start_time": "2026-10-18 18:00", "end_time": "2026-10-18 20:00"})
    req("/api/tasks", "POST", {"title": "私密任务", "owner_id": 1, "is_private": 1})
    v1 = req("/api/tasks?viewer_id=1")
    v2 = req("/api/tasks?viewer_id=2")
    print("viewer1:", [t["title"] for t in v1])
    print("viewer2:", [t["title"] for t in v2], "(应只有2条，无私密)")
    assert len(v2) == 2, "privacy filter failed"

    req(f"/api/tasks/{t2['id']}", "PATCH", {"done": 1})
    done = req(f"/api/tasks?viewer_id=2")
    assert any(t["id"] == t2["id"] and t["done"] == 1 for t in done), "toggle failed"
    print("toggle done: ok")

    req("/api/presence", "POST", {"user_id": 1, "status": "focus"})
    req("/api/presence", "POST", {"user_id": 2, "status": "away"})
    print("presence:", req("/api/presence"))

    req("/api/typing", "POST", {"user_id": 1, "keys": 300, "minutes": 5})
    print("stats:", req("/api/stats/today"))

    req(f"/api/tasks/{t1['id']}", "DELETE")
    after = req("/api/tasks?viewer_id=1")
    assert all(t["id"] != t1["id"] for t in after), "delete failed"
    print("delete: ok")

    for url in ["/", "/static/app.js", "/static/style.css", "/static/assets/cats/cat2.jpg"]:
        code = urllib.request.urlopen(BASE + url, timeout=5).status
        print(url, code)


async def ws_test():
    import websockets
    async with websockets.connect("ws://127.0.0.1:8017/ws") as ws:
        await asyncio.sleep(0.3)
        t = req("/api/tasks", "POST", {"title": "WS广播测试", "owner_id": 1, "due_date": "2026-10-19"})
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
        print("ws broadcast:", msg["type"], msg["task"]["title"])
        assert msg["type"] == "task:created" and msg["task"]["id"] == t["id"], "ws failed"
        req(f"/api/tasks/{t['id']}", "DELETE")
        msg2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
        print("ws delete:", msg2)


main()
asyncio.run(ws_test())
print("ALL CHECKS PASSED")
