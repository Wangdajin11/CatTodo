# CatTodo 架构文档

## 总体架构

```
┌─ 客户端（每人一台 Windows）────────────────────────┐
│ pywebview 窗口（Edge WebView2 渲染前端页面）          │
│   └─ HTML/CSS/JS：清单 / 时间轴 / 日历 / 小猫弹窗    │
│ pynput 全局键盘钩子（后台线程）→ 打字计数             │
└───────────────┬─────────────────────────────────────┘
                │ REST + WebSocket（http://server:8017）
┌───────────────▼─────────────────────────────────────┐
│ 服务端（FastAPI / uvicorn，本机或 VPS）              │
│   /api/*       任务 CRUD、presence、typing、stats    │
│   /ws          WebSocket 广播（任务/状态/打字事件）   │
│   SQLite       users / tasks / typing_daily         │
└──────────────────────────────────────────────────────┘
```

## 实时协议（WebSocket /ws）

所有消息为 JSON，`type` 字段区分事件：

| type | 载荷 | 说明 |
|---|---|---|
| `task:created` | `task` | 新任务（服务端全量广播） |
| `task:updated` | `task` | 任务变更（完成/编辑） |
| `task:deleted` | `id` | 任务删除 |
| `presence` | `user_id, status` | 状态：focus / away / offline |
| `typing` | `user_id, keys, minutes` | 打字增量，客户端累计显示 |

客户端断线 3 秒自动重连；重连后通过 REST 全量刷新。

## 数据模型

```sql
users(id, name, color)              -- 固定双人：1 我(蓝) / 2 TA(橙)
tasks(id, title, owner_id, start_time, end_time,
      due_date, done, is_private, created_at, updated_at)
typing_daily(user_id, day, keys, minutes)  -- PK(user_id, day)，当天累计
```

- `start_time / end_time`：`YYYY-MM-DD HH:MM`，用于时间轴泳道定位
- `due_date`：`YYYY-MM-DD`，用于月历截止日
- `is_private`：1 时仅 owner 可见（查询按 `is_private = 0 OR owner_id = viewer` 过滤）

## 关键设计

1. **重叠显示**：时间轴按人分泳道（用户 1 上、用户 2 下），同一时间段两人任务各自成条并排，重叠自然可见
2. **打字统计**：pynput 全局钩子（不进 UI 焦点也统计），每 300 键 flush 一次到 `/api/typing`；服务端按天累计，广播增量让双方实时看到
3. **小猫弹窗**：客户端本地累计，每满阈值调用 `window.__catPopup(total)`，随机贴纸 + 文案，4 秒自动消失；贴纸为 `client/web/assets/cats/*.svg`
4. **身份**：每台机器 `client/config.json` 指定 `user_id`，前端以 `?user=` 查询参数读取

## 安全与隐私

- 数据存服务端 SQLite；私密任务标记后他人不可见
- 前端所有动态文本经 `esc()` HTML 转义，防 XSS
- 服务端默认 `--host 0.0.0.0`，公网部署需在防火墙/安全组放行 8017 端口（建议加 API Token，见部署文档）
