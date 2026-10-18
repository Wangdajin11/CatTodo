import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import db, models

WEB_DIR = Path(__file__).resolve().parent.parent / "client" / "web"


@asynccontextmanager
async def lifespan(_app):
    db.init_db()
    yield


app = FastAPI(title="CatTodo", lifespan=lifespan)


class TaskIn(BaseModel):
    title: str
    owner_id: int
    start_time: str | None = None
    end_time: str | None = None
    due_date: str | None = None
    is_private: int = 0


class TaskPatch(BaseModel):
    title: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    due_date: str | None = None
    done: int | None = None
    is_private: int | None = None


class PresenceIn(BaseModel):
    user_id: int
    status: str


class TypingIn(BaseModel):
    user_id: int
    keys: int = 0
    minutes: int = 0


class Hub:
    def __init__(self):
        self.conns: set[WebSocket] = set()
        self.presence: dict[int, str] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.conns.add(ws)

    def disconnect(self, ws: WebSocket):
        self.conns.discard(ws)

    async def broadcast(self, message: dict):
        data = json.dumps(message, ensure_ascii=False)
        for ws in list(self.conns):
            try:
                await ws.send_text(data)
            except Exception:
                self.conns.discard(ws)


hub = Hub()


@app.get("/")
async def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/users")
async def api_users():
    return models.users()


@app.get("/api/tasks")
async def api_tasks(viewer_id: int = 1):
    return models.list_tasks(viewer_id)


@app.post("/api/tasks")
async def api_create(task: TaskIn):
    t = models.create_task(**task.model_dump())
    await hub.broadcast({"type": "task:created", "task": t})
    return t


@app.patch("/api/tasks/{task_id}")
async def api_update(task_id: int, patch: TaskPatch):
    t = models.update_task(task_id, patch.model_dump(exclude_none=True))
    if t:
        await hub.broadcast({"type": "task:updated", "task": t})
    return t


@app.delete("/api/tasks/{task_id}")
async def api_delete(task_id: int):
    models.delete_task(task_id)
    await hub.broadcast({"type": "task:deleted", "id": task_id})
    return {"ok": True}


@app.get("/api/presence")
async def api_presence_get():
    return hub.presence


@app.post("/api/presence")
async def api_presence(p: PresenceIn):
    hub.presence[p.user_id] = p.status
    await hub.broadcast({"type": "presence", "user_id": p.user_id, "status": p.status})
    return {"ok": True}


@app.post("/api/typing")
async def api_typing(t: TypingIn):
    models.add_typing(t.user_id, t.keys, t.minutes)
    await hub.broadcast(
        {"type": "typing", "user_id": t.user_id, "keys": t.keys, "minutes": t.minutes}
    )
    return {"ok": True}


@app.get("/api/stats/today")
async def api_stats():
    return models.typing_today()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
