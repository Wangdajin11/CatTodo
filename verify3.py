import asyncio
import json
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import db

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


def cleanup():
    conn = db.get_conn()
    conn.execute("DELETE FROM checkins")
    conn.execute("DELETE FROM focus_sessions")
    conn.commit()
    conn.close()


async def main():
    cleanup()
    assert req("/api/focus/current") is None
    req("/api/focus/stop", "POST")

    import websockets
    async with websockets.connect("ws://127.0.0.1:8017/ws") as ws:
        await asyncio.sleep(0.3)

        s = req("/api/focus/start", "POST", {"user_id": 1, "duration_min": 25})
        m1 = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
        assert m1["type"] == "focus:update" and m1["session"]["participants"] == [1], m1
        assert m1["session"]["duration_min"] == 25
        assert m1["session"]["end_at"] > m1["session"]["start_at"]

        s2 = req("/api/focus/join", "POST", {"user_id": 2})
        m2 = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
        assert m2["type"] == "focus:update" and m2["session"]["participants"] == [1, 2], m2
        assert s2["participants"] == [1, 2]

        again = req("/api/focus/start", "POST", {"user_id": 1, "duration_min": 60})
        assert again["id"] == s["id"] and again["duration_min"] == 25
        print("focus start/join/reuse: ok")

        req("/api/focus/stop", "POST")
        m3 = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
        assert m3["type"] == "focus:update" and m3["session"]["status"] == "cancelled", m3
        assert req("/api/focus/current") is None
        print("focus stop: ok")

    info1 = req("/api/checkin", "POST", {"user_id": 1})
    assert info1["today"] and info1["streak"] == 1, info1

    conn = db.get_conn()
    today = date.today()
    for i in range(1, 4):
        conn.execute(
            "INSERT OR IGNORE INTO checkins (user_id, day) VALUES (?, ?)",
            (2, (today - timedelta(days=i)).isoformat()),
        )
    conn.commit()
    conn.close()
    info2 = req("/api/checkin", "POST", {"user_id": 2})
    assert info2["today"] and info2["streak"] == 4, info2

    allc = req("/api/checkins")
    assert allc["1"]["streak"] == 1 and allc["2"]["streak"] == 4, allc
    print("checkin + streak: ok", allc)

    cleanup()
    print("ALL CHECKS PASSED")


asyncio.run(main())
