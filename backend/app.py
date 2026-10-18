import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
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


class FocusStartIn(BaseModel):
    user_id: int
    duration_min: int = 25


class FocusJoinIn(BaseModel):
    user_id: int


class CheckinIn(BaseModel):
    user_id: int


class CheerIn(BaseModel):
    from_user_id: int


OVERTIME_SECONDS = 45 * 60


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


class FocusManager:
    def __init__(self):
        self.current = None
        self._task = None
        self._overtime_task = None

    def _session(self, sid, started_by, duration, start, end, participants):
        return {
            "id": sid,
            "started_by": started_by,
            "duration_min": duration,
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "participants": participants,
            "status": "running",
        }

    async def start(self, user_id, duration_min):
        if self.current is not None:
            return await self.join(user_id)
        duration_min = min(180, max(5, int(duration_min)))
        start = datetime.now(timezone.utc)
        end = start + timedelta(minutes=duration_min)
        participants = [user_id]
        sid = models.create_focus_session(
            user_id, duration_min, start.isoformat(), end.isoformat(), participants
        )
        self.current = self._session(sid, user_id, duration_min, start, end, participants)
        self._task = asyncio.create_task(self._finish_at(sid, end))
        overtime_at = start + timedelta(seconds=OVERTIME_SECONDS)
        if overtime_at < end:
            self._overtime_task = asyncio.create_task(self._overtime_at(sid, overtime_at))
        await hub.broadcast({"type": "focus:update", "session": self.current})
        return self.current

    async def join(self, user_id):
        if self.current is None:
            return None
        if user_id not in self.current["participants"]:
            self.current["participants"].append(user_id)
            models.update_focus_session(self.current["id"], participants=self.current["participants"])
            await hub.broadcast({"type": "focus:update", "session": self.current})
        return self.current

    async def stop(self):
        if self.current is None:
            return None
        if self._task:
            self._task.cancel()
        if self._overtime_task:
            self._overtime_task.cancel()
        models.update_focus_session(self.current["id"], status="cancelled")
        self.current["status"] = "cancelled"
        await hub.broadcast({"type": "focus:update", "session": self.current})
        self.current = None
        self._task = None
        self._overtime_task = None
        return None

    async def _overtime_at(self, sid, at):
        wait = max(0.0, (at - datetime.now(timezone.utc)).total_seconds())
        await asyncio.sleep(wait)
        if self.current is None or self.current["id"] != sid:
            return
        await hub.broadcast({
            "type": "focus:overtime",
            "session": self.current,
            "participants": self.current["participants"],
        })

    async def _finish_at(self, sid, end):
        wait = max(0.0, (end - datetime.now(timezone.utc)).total_seconds())
        await asyncio.sleep(wait)
        if self.current is None or self.current["id"] != sid:
            return
        if self._overtime_task:
            self._overtime_task.cancel()
        models.update_focus_session(sid, status="done")
        participants = self.current["participants"]
        for uid in participants:
            models.checkin(uid)
        finished = dict(self.current, status="done")
        self.current = None
        self._task = None
        self._overtime_task = None
        await hub.broadcast({"type": "focus:finished", "session": finished})
        await hub.broadcast({"type": "checkins", "data": models.all_checkins()})


focus = FocusManager()


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


@app.get("/api/tasks/{task_id}")
async def api_task_detail(task_id: int):
    return models.get_task(task_id)


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


@app.get("/api/focus/current")
async def api_focus_current():
    return focus.current


@app.post("/api/focus/start")
async def api_focus_start(body: FocusStartIn):
    return await focus.start(body.user_id, body.duration_min)


@app.post("/api/focus/join")
async def api_focus_join(body: FocusJoinIn):
    return await focus.join(body.user_id)


@app.post("/api/focus/stop")
async def api_focus_stop():
    return await focus.stop()


@app.post("/api/focus/cheer")
async def api_focus_cheer(body: CheerIn):
    await hub.broadcast({"type": "focus:cheer", "from": body.from_user_id})
    return {"ok": True}


@app.get("/api/review/weekly")
async def api_weekly_review(week_offset: int = 0):
    return models.weekly_review(week_offset)


@app.get("/api/checkins")
async def api_checkins():
    return models.all_checkins()


@app.post("/api/checkin")
async def api_checkin(body: CheckinIn):
    info = models.checkin(body.user_id)
    await hub.broadcast({"type": "checkins", "data": models.all_checkins()})
    return info


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
