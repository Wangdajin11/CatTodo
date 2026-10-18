const params = new URLSearchParams(location.search);
const ME = { id: parseInt(params.get("user") || "1", 10) };

let users = [];
let tasks = [];
let presence = {};
let stats = {};
let ws = null;
let currentView = "list";
let calCursor = new Date();

const $ = (s) => document.querySelector(s);
const esc = (s) =>
  String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

function colorOf(uid) {
  const u = users.find((x) => x.id === uid);
  return u ? u.color : "#999";
}
function nameOf(uid) {
  const u = users.find((x) => x.id === uid);
  return u ? u.name : "用户" + uid;
}
function fmtDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function timeToMin(s) {
  if (!s) return 0;
  const m = String(s).match(/(\d{1,2}):(\d{2})/);
  return m ? parseInt(m[1], 10) * 60 + parseInt(m[2], 10) : 0;
}
function fmtRange(t) {
  const parts = [];
  if (t.start_time) parts.push(t.start_time.slice(11));
  if (t.end_time) parts.push(t.end_time.slice(11));
  return parts.join(" ~ ");
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  return res.json();
}

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "task:created") tasks.push(msg.task);
    if (msg.type === "task:updated") tasks = tasks.map((t) => (t.id === msg.task.id ? msg.task : t));
    if (msg.type === "task:deleted") tasks = tasks.filter((t) => t.id !== msg.id);
    if (msg.type === "presence") presence[msg.user_id] = msg.status;
    if (msg.type === "typing") {
      if (!stats[msg.user_id]) stats[msg.user_id] = { keys: 0, minutes: 0 };
      stats[msg.user_id].keys += msg.keys;
      stats[msg.user_id].minutes += msg.minutes;
    }
    render();
    flash();
  };
  ws.onclose = () => setTimeout(connectWS, 3000);
}

function render() {
  renderPresence();
  if (currentView === "list") renderList();
  if (currentView === "timeline") renderTimeline();
  if (currentView === "calendar") renderCalendar();
}

function renderPresence() {
  const el = $("#presence");
  const statusText = { focus: "专注中", away: "摸鱼中", offline: "离线" };
  el.innerHTML =
    users
      .map((u) => {
        const st = presence[u.id] || "offline";
        const keys = (stats[u.id] && stats[u.id].keys) || 0;
        return `<div class="presence-item">
          <span class="dot ${st}"></span>
          <span class="pname" style="color:${u.color}">${esc(u.name)}</span>
          <span class="pstatus">${statusText[st] || "离线"}${u.id === ME.id ? "" : " · 今日 " + keys + " 字"}</span>
        </div>`;
      })
      .join("") +
    `<select id="my-status">
      <option value="focus">我的状态：专注</option>
      <option value="away">我的状态：摸鱼</option>
      <option value="offline">我的状态：离线</option>
    </select>`;
  const sel = $("#my-status");
  sel.value = presence[ME.id] || "offline";
  sel.onchange = () => api("/api/presence", { method: "POST", body: JSON.stringify({ user_id: ME.id, status: sel.value }) });
}

function renderList() {
  const el = $("#view-list");
  const sorted = [...tasks].sort(
    (a, b) => (a.done - b.done) || (a.start_time || "").localeCompare(b.start_time || "") || (a.due_date || "").localeCompare(b.due_date || "")
  );
  if (!sorted.length) {
    el.innerHTML = `<div class="empty">还没有任务，点右上角 ＋ 新建一个吧 🐾</div>`;
    return;
  }
  el.innerHTML = "";
  sorted.forEach((t) => {
    const card = document.createElement("div");
    card.className = "task-card" + (t.done ? " done" : "");
    card.innerHTML = `
      <div class="task-color" style="background:${colorOf(t.owner_id)}"></div>
      <div class="task-body">
        <div class="task-title">${esc(t.title)}${t.is_private ? '<span class="badge">仅自己</span>' : ""}</div>
        <div class="task-meta">${esc(fmtRange(t))}${t.due_date ? " · 截止 " + esc(t.due_date) : ""} · ${esc(nameOf(t.owner_id))}</div>
      </div>
      <button class="btn-done" data-act="toggle" data-id="${t.id}">${t.done ? "✓ 已完成" : "完成"}</button>
      ${t.owner_id === ME.id ? `<button class="btn-del" data-act="del" data-id="${t.id}">×</button>` : ""}`;
    el.appendChild(card);
  });
}

function renderTimeline() {
  const el = $("#view-timeline");
  el.innerHTML = "";
  for (let i = -3; i <= 3; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    el.appendChild(dayRow(d));
  }
}

function dayRow(date) {
  const row = document.createElement("div");
  row.className = "day-row";
  const label = document.createElement("div");
  label.className = "day-label";
  const isToday = date.toDateString() === new Date().toDateString();
  label.innerHTML = `${date.getMonth() + 1}/${date.getDate()}${isToday ? "<b> 今天</b>" : ""}`;
  row.appendChild(label);

  const track = document.createElement("div");
  track.className = "day-track";
  for (let h = 0; h < 24; h++) {
    const cell = document.createElement("div");
    cell.className = "hour-cell";
    cell.style.left = (h / 24) * 100 + "%";
    track.appendChild(cell);
  }

  const ymd = fmtDate(date);
  users.forEach((u) => {
    const laneTasks = tasks.filter(
      (t) => t.owner_id === u.id && t.start_time && !t.done && t.start_time.slice(0, 10) === ymd
    );
    laneTasks.forEach((t) => {
      const startMin = timeToMin(t.start_time);
      let endMin = t.end_time ? timeToMin(t.end_time) : startMin + 60;
      if (endMin <= startMin) endMin = startMin + 60;
      if (endMin > 1440) endMin = 1440;
      const bar = document.createElement("div");
      bar.className = "task-bar";
      bar.style.left = (startMin / 1440) * 100 + "%";
      bar.style.width = Math.max(((endMin - startMin) / 1440) * 100 - 0.15, 1.5) + "%";
      bar.style.top = 20 + users.findIndex((x) => x.id === u.id) * 26 + "px";
      bar.style.background = colorOf(u.id);
      bar.innerHTML = `<span>${esc(t.title)}</span>`;
      bar.title = `${t.title} · ${t.start_time} ~ ${t.end_time || ""}`;
      track.appendChild(bar);
    });
  });

  const dueTasks = tasks.filter((t) => t.due_date === ymd && !t.done && !t.start_time);
  if (dueTasks.length) {
    const chips = document.createElement("div");
    chips.className = "due-chips";
    chips.innerHTML = dueTasks.map((t) => `<span style="background:${colorOf(t.owner_id)}">${esc(t.title)}</span>`).join("");
    track.appendChild(chips);
  }

  row.appendChild(track);
  return row;
}

function renderCalendar() {
  const el = $("#view-calendar");
  const y = calCursor.getFullYear();
  const m = calCursor.getMonth();
  const head = document.createElement("div");
  head.className = "cal-head";
  head.innerHTML = `<button data-calm="-1">‹</button><span>${y} 年 ${m + 1} 月</span><button data-calm="1">›</button>`;
  el.appendChild(head);

  const grid = document.createElement("div");
  grid.className = "cal-grid";
  ["一", "二", "三", "四", "五", "六", "日"].forEach((w) => {
    const d = document.createElement("div");
    d.className = "cal-week";
    d.textContent = w;
    grid.appendChild(d);
  });
  const offset = (new Date(y, m, 1).getDay() + 6) % 7;
  const daysInMonth = new Date(y, m + 1, 0).getDate();
  for (let i = 0; i < offset; i++) grid.appendChild(document.createElement("div"));
  for (let day = 1; day <= daysInMonth; day++) {
    const cell = document.createElement("div");
    cell.className = "cal-cell";
    const ymd = `${y}-${String(m + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const dayTasks = tasks.filter((t) => t.due_date === ymd);
    cell.innerHTML =
      `<div class="cal-day">${day}</div>` +
      dayTasks
        .slice(0, 3)
        .map((t) => `<div class="cal-chip" style="background:${colorOf(t.owner_id)}">${esc(t.title)}</div>`)
        .join("") +
      (dayTasks.length > 3 ? `<div class="cal-more">+${dayTasks.length - 3}</div>` : "");
    grid.appendChild(cell);
  }
  el.appendChild(grid);
}

function openModal() {
  $("#modal").classList.remove("hidden");
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  $("#f-start").value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
  $("#f-title").focus();
}
function closeModal() {
  $("#modal").classList.add("hidden");
}

async function saveTask() {
  const title = $("#f-title").value.trim();
  if (!title) return;
  const payload = {
    title,
    owner_id: ME.id,
    start_time: $("#f-start").value ? $("#f-start").value.replace("T", " ") : null,
    end_time: $("#f-end").value ? $("#f-end").value.replace("T", " ") : null,
    due_date: $("#f-due").value || null,
    is_private: $("#f-private").checked ? 1 : 0,
  };
  await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
  closeModal();
  $("#f-title").value = "";
  $("#f-end").value = "";
  $("#f-due").value = "";
  $("#f-private").checked = false;
}

const CATS = ["cat1", "cat2", "cat3", "cat4", "cat5", "cat6"];
const CAT_TIPS = [
  "喵~ 又敲了 N 次键盘，继续保持！",
  "敲了 N 下啦，辛苦啦，起来伸个懒腰吧～",
  "喵喵！已经 N 次了，记得喝口水 ☕",
  "打字好快！歇 5 秒，揉揉眼睛再看屏幕",
];
window.__catPopup = function (total) {
  const n = CATS[Math.floor(Math.random() * CATS.length)];
  const tip = CAT_TIPS[Math.floor(Math.random() * CAT_TIPS.length)].replace(/N/g, total);
  const p = $("#popup");
  p.innerHTML = `<img src="/static/assets/cats/${n}.svg" alt="猫猫"><div>${tip}</div>`;
  p.classList.remove("hidden");
  p.classList.add("show");
  clearTimeout(p._t);
  p._t = setTimeout(() => p.classList.remove("show"), 4000);
};

function flash() {
  const f = $("#flash");
  f.textContent = "已同步 ✓";
  f.classList.remove("hidden");
  clearTimeout(f._t);
  f._t = setTimeout(() => f.classList.add("hidden"), 1200);
}

document.addEventListener("click", (e) => {
  const nav = e.target.closest("button[data-view]");
  if (nav) {
    currentView = nav.dataset.view;
    document.querySelectorAll("nav button").forEach((b) => b.classList.remove("active"));
    nav.classList.add("active");
    document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
    $("#view-" + currentView).classList.remove("hidden");
    render();
    return;
  }
  const calm = e.target.closest("button[data-calm]");
  if (calm) {
    calCursor.setMonth(calCursor.getMonth() + parseInt(calm.dataset.calm, 10));
    $("#view-calendar").innerHTML = "";
    renderCalendar();
    return;
  }
  const act = e.target.closest("button[data-act]");
  if (act) {
    const id = parseInt(act.dataset.id, 10);
    if (act.dataset.act === "toggle") {
      const t = tasks.find((x) => x.id === id);
      api(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ done: t.done ? 0 : 1 }) });
    }
    if (act.dataset.act === "del") {
      if (confirm("删除这个任务？")) api(`/api/tasks/${id}`, { method: "DELETE" });
    }
    return;
  }
  if (e.target.id === "btn-add") openModal();
  if (e.target.id === "btn-cancel") closeModal();
  if (e.target.id === "btn-save") saveTask();
  if (e.target.id === "modal") closeModal();
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    api("/api/presence", { method: "POST", body: JSON.stringify({ user_id: ME.id, status: "away" }) });
  } else {
    api("/api/presence", { method: "POST", body: JSON.stringify({ user_id: ME.id, status: "focus" }) });
  }
});

async function boot() {
  const [u, t, p, s] = await Promise.all([
    api("/api/users"),
    api("/api/tasks?viewer_id=" + ME.id),
    api("/api/presence"),
    api("/api/stats/today"),
  ]);
  users = u;
  tasks = t;
  presence = p;
  stats = s;
  connectWS();
  render();
}

boot();
