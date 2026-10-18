const params = new URLSearchParams(location.search);
const ME = { id: parseInt(params.get("user") || "1", 10) };

let users = [];
let tasks = [];
let presence = {};
let stats = {};
let focusSession = null;
let checkins = {};
let focusDuration = 25;
let ws = null;
let currentView = "list";
let calCursor = new Date();
let hourWidth = 48;
const expanded = new Set();

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
  return parts.length ? parts.join(" ~ ") : "全天";
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  return res.json();
}

async function refreshStats() {
  stats = await api("/api/stats/today");
  renderPresence();
}

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "task:created") tasks.push(msg.task);
    if (msg.type === "task:updated") tasks = tasks.map((t) => (t.id === msg.task.id ? msg.task : t));
    if (msg.type === "task:deleted") tasks = tasks.filter((t) => t.id !== msg.id);
    if (msg.type === "subtask:changed") {
      const t = tasks.find((x) => x.id === msg.task_id);
      if (t) t.subtasks = msg.subtasks;
    }
    if (msg.type === "presence") {
      presence[msg.user_id] = { status: msg.status, text: msg.status_text || "" };
    }
    if (msg.type === "typing") {
      if (!stats[msg.user_id]) stats[msg.user_id] = { keys: 0, minutes: 0 };
      stats[msg.user_id].keys += msg.keys;
    }
    if (msg.type === "focus:update") {
      focusSession = msg.session.status === "running" ? msg.session : null;
      if (currentView === "focus") renderFocus();
    }
    if (msg.type === "focus:finished") {
      const wasIn = msg.session.participants.includes(ME.id);
      focusSession = null;
      if (wasIn) showCat(msg.session.participants.length > 1 ? "一起完成了 " + msg.session.duration_min + " 分钟专注，太棒啦！" : "完成了 " + msg.session.duration_min + " 分钟专注，喵～", "cat5");
      if (currentView === "focus") renderFocus();
    }
    if (msg.type === "checkins") {
      checkins = msg.data;
      if (currentView === "focus") renderFocus();
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
  if (currentView === "focus") renderFocus();
}

function renderPresence() {
  const el = $("#presence");
  const statusText = { focus: "专注中", away: "摸鱼中", offline: "离线" };
  const items = users
    .map((u) => {
      const p = presence[u.id] || { status: "offline", text: "" };
      const keys = (stats[u.id] && stats[u.id].keys) || 0;
      const extra = p.text ? " · " + esc(p.text) : "";
      return `<div class="presence-item">
        <span class="dot ${p.status}"></span>
        <span class="pname" style="color:${u.color}">${esc(u.name)}</span>
        <span class="pstatus">${statusText[p.status] || "离线"}${extra} · 今日 ${keys} 键</span>
      </div>`;
    })
    .join("");
  const mine = presence[ME.id] || { status: "offline", text: "" };
  el.innerHTML =
    items +
    `<select id="my-status">
      <option value="focus">我的状态：专注</option>
      <option value="away">我的状态：摸鱼</option>
      <option value="offline">我的状态：离线</option>
    </select>
    <input id="my-status-text" class="status-text" maxlength="30" placeholder="在做什么？如：背单词" value="${esc(mine.text || "")}">`;
  const sel = $("#my-status");
  sel.value = mine.status || "offline";
  sel.onchange = () => pushPresence();
  const input = $("#my-status-text");
  let timer = null;
  input.oninput = () => {
    clearTimeout(timer);
    timer = setTimeout(pushPresence, 500);
  };
}

function pushPresence() {
  const status = $("#my-status").value;
  const text = $("#my-status-text").value;
  api("/api/presence", {
    method: "POST",
    body: JSON.stringify({ user_id: ME.id, status, status_text: text }),
  });
}

function subProgress(t) {
  const subs = t.subtasks || [];
  if (!subs.length) return "";
  const done = subs.filter((s) => s.done).length;
  return `<span class="sub-badge">${done}/${subs.length}</span>`;
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
        <div class="task-title">${esc(t.title)}${subProgress(t)}${t.is_private ? '<span class="badge">仅自己</span>' : ""}</div>
        <div class="task-meta">${esc(fmtRange(t))}${t.due_date ? " · 截止 " + esc(t.due_date) : ""} · ${esc(nameOf(t.owner_id))}${(t.description || (t.subtasks || []).length) ? " · ▸" : ""}</div>
        ${expanded.has(t.id) ? expandedHtml(t) : ""}
      </div>
      <button class="btn-done" data-act="toggle" data-id="${t.id}">${t.done ? "✓ 已完成" : "完成"}</button>
      ${t.owner_id === ME.id ? `<button class="btn-del" data-act="del" data-id="${t.id}">×</button>` : ""}`;
    el.appendChild(card);
  });
}

function expandedHtml(t) {
  const subs = t.subtasks || [];
  const desc = t.description ? `<div class="task-desc">${esc(t.description)}</div>` : "";
  const rows = subs
    .map(
      (s) => `<div class="sub-row${s.done ? " checked" : ""}">
        <input type="checkbox" data-act="sub-toggle" data-id="${s.id}" ${s.done ? "checked" : ""}>
        <span>${esc(s.title)}</span>
        <button class="sub-del" data-act="sub-del" data-id="${s.id}">×</button>
      </div>`
    )
    .join("");
  return `<div class="task-expand">
    ${desc}
    <div class="sub-list">${rows}</div>
    <div class="sub-add">
      <input type="text" placeholder="添加子任务，回车确认" data-sub-input="${t.id}" maxlength="60">
      <button data-act="sub-add" data-id="${t.id}">添加</button>
    </div>
  </div>`;
}

function renderTimeline() {
  const el = $("#view-timeline");
  el.innerHTML = "";
  const toolbar = document.createElement("div");
  toolbar.className = "tl-toolbar";
  toolbar.innerHTML = `<button id="tl-zoom-out">－</button><span>${hourWidth}px/时</span><button id="tl-zoom-in">＋</button><span class="tl-hint">Ctrl + 滚轮缩放</span>`;
  el.appendChild(toolbar);

  const scroll = document.createElement("div");
  scroll.className = "tl-scroll";
  scroll.appendChild(rulerRow());
  for (let i = -3; i <= 3; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    scroll.appendChild(dayRow(d));
  }
  scroll.addEventListener("wheel", (e) => {
    if (!e.ctrlKey) return;
    e.preventDefault();
    hourWidth = Math.min(160, Math.max(20, hourWidth + (e.deltaY < 0 ? 8 : -8)));
    renderTimeline();
  }, { passive: false });
  el.appendChild(scroll);
}

function rulerRow() {
  const row = document.createElement("div");
  row.className = "day-row tl-ruler";
  row.innerHTML = `<div class="day-label"></div><div class="day-track" style="width:${24 * hourWidth}px;height:18px"></div>`;
  const track = row.querySelector(".day-track");
  for (let h = 0; h < 24; h += 2) {
    const tick = document.createElement("div");
    tick.className = "hour-tick";
    tick.style.left = h * hourWidth + "px";
    tick.textContent = `${h}:00`;
    track.appendChild(tick);
  }
  return row;
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
  track.style.width = 24 * hourWidth + "px";
  track.style.height = "112px";
  for (let h = 0; h < 24; h++) {
    const cell = document.createElement("div");
    cell.className = "hour-cell";
    cell.style.left = h * hourWidth + "px";
    track.appendChild(cell);
  }

  const ymd = fmtDate(date);
  users.forEach((u) => {
    const lane = users.findIndex((x) => x.id === u.id);
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
      bar.style.left = (startMin / 60) * hourWidth + "px";
      bar.style.width = Math.max(((endMin - startMin) / 60) * hourWidth - 2, 24) + "px";
      bar.style.top = 22 + lane * 32 + "px";
      bar.style.height = "24px";
      bar.style.lineHeight = "24px";
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

function focusRemaining() {
  if (!focusSession) return focusDuration * 60;
  const end = new Date(focusSession.end_at).getTime();
  return Math.max(0, Math.round((end - Date.now()) / 1000));
}

function mmss(sec) {
  return `${String(Math.floor(sec / 60)).padStart(2, "0")}:${String(sec % 60).padStart(2, "0")}`;
}

function focusTick() {
  const remEl = $("#focus-remaining");
  const ringEl = $("#focus-ring-progress");
  if (!remEl) return;
  if (!focusSession) {
    remEl.textContent = mmss(focusDuration * 60);
    if (ringEl) ringEl.style.strokeDashoffset = "0";
    return;
  }
  const rem = focusRemaining();
  remEl.textContent = mmss(rem);
  const total = focusSession.duration_min * 60;
  const C = 2 * Math.PI * 100;
  const progress = total > 0 ? (total - rem) / total : 0;
  if (ringEl) ringEl.style.strokeDashoffset = String(C * (1 - progress));
}

function renderFocus() {
  const el = $("#view-focus");
  const running = focusSession;
  const inSession = running && running.participants.includes(ME.id);
  const starter = running && users.find((u) => u.id === running.started_by);

  const durChips = [25, 45, 60].map((d) =>
    `<button class="dur-chip ${d === focusDuration ? "active" : ""}" data-focus-dur="${d}" ${running ? "disabled" : ""}>${d} 分钟</button>`
  ).join("");

  let controls = "";
  if (!running) {
    controls = `<div class="dur-row">${durChips}</div>
      <button class="focus-primary" data-act="focus-start">开始一起自习</button>
      <div class="focus-state" id="focus-state">准备好就开始，TA 会看到你的自习</div>`;
  } else {
    const who = running.participants.map((id) =>
      `<span class="focus-who" style="color:${colorOf(id)}">${esc(nameOf(id))} 在自习中</span>`
    ).join("");
    controls = `<div class="focus-people">${who}</div>`;
    if (inSession) {
      controls += `<div class="focus-state" id="focus-state">${running.started_by === ME.id ? "你发起的自习，等 TA 加入" : "你们正在一起自习，加油～"}</div>
        <button class="focus-ghost" data-act="focus-stop">结束自习</button>`;
    } else {
      controls += `<div class="focus-state" id="focus-state">${esc(starter ? starter.name : "")} 发起了 ${running.duration_min} 分钟自习</div>
        <button class="focus-primary" data-act="focus-join">加入自习</button>`;
    }
  }

  const streakCards = users.map((u) => {
    const info = checkins[u.id] || { streak: 0, today: false };
    const mine = u.id === ME.id;
    const btn = mine && !info.today
      ? `<button class="checkin-btn" data-act="checkin">打卡</button>`
      : mine ? `<span class="checked-tag">今日已打卡 ✓</span>` : "";
    return `<div class="streak-card">
      <div class="streak-name" style="color:${u.color}">${esc(u.name)}</div>
      <div class="streak-num">🔥 ${info.streak} 天</div>
      <div class="streak-tip">${info.today ? "今天已打卡" : "今天还没打卡"}</div>
      ${btn}
    </div>`;
  }).join("");

  const threshold = localStorage.getItem("cattodo_threshold") || "300";
  const opts = [100, 200, 300, 500].map((n) =>
    `<option value="${n}" ${String(n) === String(threshold) ? "selected" : ""}>${n} 键</option>`
  ).join("");

  el.innerHTML = `
  <div class="focus-wrap">
    <div class="focus-card">
      <div class="focus-ring">
        <svg width="240" height="240" viewBox="0 0 240 240">
          <circle cx="120" cy="120" r="100" class="ring-bg" fill="none" stroke-width="14"/>
          <circle id="focus-ring-progress" cx="120" cy="120" r="100" class="ring-fg" fill="none" stroke-width="14"
            stroke-linecap="round" transform="rotate(-90 120 120)"/>
        </svg>
        <div class="focus-remaining" id="focus-remaining">25:00</div>
      </div>
      ${controls}
    </div>
    <div class="focus-side">
      <div class="focus-panel">
        <h4>打卡连击</h4>
        <div class="streak-row">${streakCards}</div>
        <div class="panel-tip">完成一次自习会自动打卡</div>
      </div>
      <div class="focus-panel">
        <h4>打字暖心提醒</h4>
        <div class="setting-row">
          <label>每敲够
            <select id="threshold-select">${opts}</select>
            弹一次小猫
          </label>
          <div class="panel-tip" id="threshold-tip">仅桌面端生效</div>
        </div>
      </div>
    </div>
  </div>`;
  focusTick();
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
    description: $("#f-desc").value.trim(),
    start_time: $("#f-start").value ? $("#f-start").value.replace("T", " ") : null,
    end_time: $("#f-end").value ? $("#f-end").value.replace("T", " ") : null,
    due_date: $("#f-due").value || null,
    is_private: $("#f-private").checked ? 1 : 0,
  };
  await api("/api/tasks", { method: "POST", body: JSON.stringify(payload) });
  closeModal();
  ["f-title", "f-desc", "f-end", "f-due"].forEach((id) => ($(`#${id}`).value = ""));
  $("#f-private").checked = false;
}

const CATS = ["cat1", "cat2", "cat3", "cat4", "cat5", "cat6"];
const CAT_TIPS = [
  "喵~ 又敲了 N 次键盘，继续保持！",
  "敲了 N 下啦，辛苦啦，起来伸个懒腰吧～",
  "喵喵！已经 N 次了，记得喝口水 ☕",
  "打字好快！歇 5 秒，揉揉眼睛再看屏幕",
];

function showCat(message, catName) {
  const n = catName || CATS[Math.floor(Math.random() * CATS.length)];
  const p = $("#popup");
  p.innerHTML = `<img src="/static/assets/cats/${n}.svg" alt="猫猫"><div>${esc(message)}</div>`;
  p.classList.remove("hidden");
  p.classList.add("show");
  clearTimeout(p._t);
  p._t = setTimeout(() => p.classList.remove("show"), 4000);
}

window.__catPopup = function (total) {
  const tip = CAT_TIPS[Math.floor(Math.random() * CAT_TIPS.length)].replace(/N/g, total);
  showCat(tip);
};

function flash() {
  const f = $("#flash");
  f.textContent = "已同步 ✓";
  f.classList.remove("hidden");
  clearTimeout(f._t);
  f._t = setTimeout(() => f.classList.add("hidden"), 1200);
}

document.addEventListener("click", (e) => {
  if (e.target.id === "tl-zoom-in") { hourWidth = Math.min(160, hourWidth + 12); renderTimeline(); return; }
  if (e.target.id === "tl-zoom-out") { hourWidth = Math.max(20, hourWidth - 12); renderTimeline(); return; }

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
  const dur = e.target.closest("[data-focus-dur]");
  if (dur) {
    focusDuration = parseInt(dur.dataset.focusDur, 10);
    renderFocus();
    return;
  }
  const act = e.target.closest("[data-act]");
  if (act) {
    const id = parseInt(act.dataset.id, 10);
    if (act.dataset.act === "focus-start") {
      api("/api/focus/start", { method: "POST", body: JSON.stringify({ user_id: ME.id, duration_min: focusDuration }) });
    }
    if (act.dataset.act === "focus-join") {
      api("/api/focus/join", { method: "POST", body: JSON.stringify({ user_id: ME.id }) });
    }
    if (act.dataset.act === "focus-stop") {
      api("/api/focus/stop", { method: "POST" });
    }
    if (act.dataset.act === "checkin") {
      api("/api/checkin", { method: "POST", body: JSON.stringify({ user_id: ME.id }) });
    }
    if (act.dataset.act === "toggle") {
      const t = tasks.find((x) => x.id === id);
      api(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ done: t.done ? 0 : 1 }) });
    }
    if (act.dataset.act === "del") {
      if (confirm("删除这个任务？")) api(`/api/tasks/${id}`, { method: "DELETE" });
    }
    if (act.dataset.act === "sub-toggle") {
      const checked = act.target.checked;
      api(`/api/subtasks/${id}`, { method: "PATCH", body: JSON.stringify({ done: checked ? 1 : 0 }) });
    }
    if (act.dataset.act === "sub-del") {
      api(`/api/subtasks/${id}`, { method: "DELETE" });
    }
    if (act.dataset.act === "sub-add") {
      const input = $(`[data-sub-input="${id}"]`);
      const title = input.value.trim();
      if (title) {
        api(`/api/tasks/${id}/subtasks`, { method: "POST", body: JSON.stringify({ title }) });
        input.value = "";
      }
    }
    return;
  }
  const card = e.target.closest(".task-card");
  if (card && currentView === "list" && !e.target.closest(".task-expand")) {
    const id = parseInt(card.querySelector("[data-act='toggle']").dataset.id, 10);
    if (expanded.has(id)) expanded.delete(id); else expanded.add(id);
    renderList();
    return;
  }
  if (e.target.id === "btn-add") openModal();
  if (e.target.id === "btn-cancel") closeModal();
  if (e.target.id === "btn-save") saveTask();
  if (e.target.id === "modal") closeModal();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.matches("[data-sub-input]")) {
    const id = e.target.dataset.subInput;
    const title = e.target.value.trim();
    if (title) {
      api(`/api/tasks/${id}/subtasks`, { method: "POST", body: JSON.stringify({ title }) });
      e.target.value = "";
    }
  }
});

document.addEventListener("visibilitychange", () => {
  const status = document.hidden ? "away" : "focus";
  const sel = $("#my-status");
  if (sel) sel.value = status;
  pushPresence();
});

document.addEventListener("change", (e) => {
  if (e.target.id === "threshold-select") {
    const n = parseInt(e.target.value, 10);
    localStorage.setItem("cattodo_threshold", n);
    if (window.pywebview && window.pywebview.api && window.pywebview.api.set_threshold) {
      window.pywebview.api.set_threshold(n);
      $("#threshold-tip").textContent = "已生效 ✓";
    } else {
      $("#threshold-tip").textContent = "浏览器预览不可用，桌面端生效";
    }
  }
});

async function loadThreshold() {
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.get_threshold) {
      const n = await window.pywebview.api.get_threshold();
      localStorage.setItem("cattodo_threshold", n);
    }
  } catch (e) { /* 浏览器预览时忽略 */ }
}

async function boot() {
  const [u, t, p, s, f, c] = await Promise.all([
    api("/api/users"),
    api("/api/tasks?viewer_id=" + ME.id),
    api("/api/presence"),
    api("/api/stats/today"),
    api("/api/focus/current"),
    api("/api/checkins"),
  ]);
  users = u;
  tasks = t;
  presence = p;
  stats = s;
  focusSession = f;
  checkins = c || {};
  await loadThreshold();
  connectWS();
  render();
  setInterval(refreshStats, 10000);
  setInterval(focusTick, 1000);
}

boot();
