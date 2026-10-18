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
    description: str = ""


class TaskPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    due_date: str | None = None
    done: int | None = None
    is_private: int | None = None


class SubtaskIn(BaseModel):
    title: str


class SubtaskPatch(BaseModel):
    done: int


class PresenceIn(BaseModel):
    user_id: int
    status: str
    status_text: str = ""


class TypingIn(BaseModel):
    user_id: int
    keys: int = 0
    minutes: int = 0


class Hub:
    def __init__(self):
        self.conns: set[WebSocket] = set()
        self.presence: dict[int, dict] = {}

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


@app.post("/api/tasks/{task_id}/subtasks")
async def api_add_subtask(task_id: int, body: SubtaskIn):
    subs = models.add_subtask(task_id, body.title[:100])
    await hub.broadcast({"type": "subtask:changed", "task_id": task_id, "subtasks": subs})
    return subs


@app.patch("/api/subtasks/{subtask_id}")
async def api_set_subtask(subtask_id: int, patch: SubtaskPatch):
    row = models.set_subtask_done(subtask_id, patch.done)
    if row:
        subs = models.subtasks_of(row["task_id"])
        await hub.broadcast({"type": "subtask:changed", "task_id": row["task_id"], "subtasks": subs})
    return row


@app.delete("/api/subtasks/{subtask_id}")
async def api_del_subtask(subtask_id: int):
    task_id = models.delete_subtask(subtask_id)
    if task_id:
        subs = models.subtasks_of(task_id)
        await hub.broadcast({"type": "subtask:changed", "task_id": task_id, "subtasks": subs})
    return {"ok": True}


@app.get("/api/presence")
async def api_presence_get():
    return hub.presence


@app.post("/api/presence")
async def api_presence(p: PresenceIn):
    hub.presence[p.user_id] = {"status": p.status, "text": p.status_text[:30]}
    await hub.broadcast(
        {
            "type": "presence",
            "user_id": p.user_id,
            "status": p.status,
            "status_text": p.status_text[:30],
        }
    )
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
