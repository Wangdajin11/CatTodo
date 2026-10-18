import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

import websockets

PORT = 8018
TOKEN = "verify-secret-token-123"
BASE = f"http://127.0.0.1:{PORT}"
ROOT = os.path.dirname(os.path.abspath(__file__))

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(("[PASS] " if cond else "[FAIL] ") + name + (f"  {detail}" if detail else ""))


def http(method, path, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["X-CatTodo-Token"] = token
    req = urllib.request.Request(BASE + path, method=method, headers=headers,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


async def ws_connect(token=None):
    url = f"ws://127.0.0.1:{PORT}/ws" + (f"?token={token}" if token else "")
    try:
        async with websockets.connect(url, open_timeout=5):
            return True
    except Exception:
        return False


def wait_port(port, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.4)
    return False


def cleanup_test_data():
    # 清掉测试用户 99 的打字数据
    import sqlite3
    from backend.db import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM typing_daily WHERE user_id=99")
    conn.commit()
    conn.close()


def main():
    env = os.environ.copy()
    env["CATTODO_TOKEN"] = TOKEN
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app:app",
         "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        if not wait_port(PORT):
            print("[FAIL] server not started")
            return 1

        # 1. 无 token 访问 API 应 401
        s, _ = http("GET", "/api/users")
        check("no token -> 401", s == 401, f"got {s}")

        # 2. 错误 token 应 401
        s, _ = http("GET", "/api/users", token="wrong")
        check("wrong token -> 401", s == 401, f"got {s}")

        # 3. 正确 token 可访问
        s, body = http("GET", "/api/users", token=TOKEN)
        check("correct token -> 200", s == 200 and len(json.loads(body)) == 2, f"got {s}")

        # 4. query 参数 token 也可
        s, _ = http("GET", f"/api/users?token={TOKEN}")
        check("query token -> 200", s == 200, f"got {s}")

        # 5. 错误 token 写接口 401
        s, _ = http("POST", "/api/typing", token="x", body={"user_id": 99, "keys": 1})
        check("write with wrong token -> 401", s == 401, f"got {s}")

        # 6. 正确 token 写接口成功
        s, _ = http("POST", "/api/typing", token=TOKEN, body={"user_id": 99, "keys": 3})
        check("write with correct token -> 200", s == 200, f"got {s}")

        # 7. 首页不鉴权
        s, _ = http("GET", "/")
        check("index page public -> 200", s == 200, f"got {s}")

        # 8. 静态资源不鉴权
        s, _ = http("GET", "/static/app.js")
        check("static assets public -> 200", s == 200, f"got {s}")

        # 9. WS 无 token 被拒
        ok = __import__("asyncio").run(ws_connect(None))
        check("ws without token rejected", not ok)

        # 10. WS 错误 token 被拒
        ok = __import__("asyncio").run(ws_connect("nope"))
        check("ws with wrong token rejected", not ok)

        # 11. WS 正确 token 可连
        ok = __import__("asyncio").run(ws_connect(TOKEN))
        check("ws with correct token connected", ok)

        cleanup_test_data()
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    failed = [n for n, ok, _ in results if not ok]
    print("\n" + ("ALL CHECKS PASSED" if not failed else f"FAILED: {failed}"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
