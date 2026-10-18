# CatTodo · 猫猫待办

双人陪伴式待办清单桌面应用（Windows / Python 系）。两人协作写清单、互相看见对方在做什么；任务按人着色、重叠时间并排显示；日历联动看截止日；全局打字统计，累计到阈值弹出可爱小猫暖心提醒。

## 功能

- **双人实时协作**：WebSocket 实时同步，任务按人着色（我=蓝 / TA=橙），重叠时间两人任务并排显示
- **三种视图**：清单列表 · 时间轴（±3 天，24 小时泳道，支持放大缩小）· 月历（截止日）
- **任务详情**：任务描述 + 可勾选子任务，卡片点击展开，显示子任务完成进度
- **隐私开关**：单个任务可设为「仅自己可见」
- **状态可见**：专注 / 摸鱼 / 离线徽章 + 自定义状态文字（如「在背单词」）+ 双方今日按键数
- **打字统计**：pynput 全局键盘钩子统计任意软件打字数，每 5 秒上报，状态栏实时可见，弹窗阈值可在「专注」页调节（100/200/300/500 键），到阈值弹出小猫贴纸
- **共享番茄钟**：发起「一起自习」，对方可实时加入，双方同步倒计时；结束自动打卡并弹出庆祝小猫
- **超时暖心提醒**：连续专注满 45 分钟，自习的人收到休息小猫，另一方收到「给 TA 打气」提示；专注页常驻「给 TA 打气 🐾」按钮，实时送达
- **打卡连击**：每日打卡，连续天数 🔥 双方可见
- **每周双人复盘**：「复盘」页按周统计双方完成任务数、番茄钟数与分钟、打卡天数、按键总数，可翻看上一周
- **临期提醒**：清单顶部显示已逾期 / 今天截止 / 明天截止的任务；每天首次启动弹出小猫提醒一次
- **任务编辑**：本人任务可点 ✎ 修改标题、描述、时间、截止日与隐私
- **日历联动**：任务起止时间 + 截止日期，时间轴与月历双展示（二期接飞书日历同步）

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + WebSocket + SQLite |
| 桌面壳 | pywebview（Edge WebView2） |
| 键盘钩子 | pynput |
| 前端 | 原生 HTML / CSS / JS |

## 快速开始

```bat
:: 1. 创建虚拟环境（建议 Python 3.12）
py -3.12 -m venv venv

:: 2. 安装依赖（清华源加速）
venv\Scripts\python -m pip install -r backend\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

:: 3. 启动服务端
start_server.bat        :: 或 venv\Scripts\python -m uvicorn backend.app:app --host 0.0.0.0 --port 8017

:: 4. 启动桌面端（两人各自电脑上运行）
start_client.bat
```

**两人配置**：`client\config.json` 中，一方填 `user_id: 1`、另一方填 `user_id: 2`；异地使用时把 `server_url` 改成服务器地址（见 `deploy\README.md`）。

## 数据模型

- `users`：id / name / color
- `tasks`：title / owner_id / description / start_time / end_time / due_date / done / completed_at / is_private
- `subtasks`：task_id / title / done
- `typing_daily`：user_id / day / keys / minutes
- `checkins`：user_id / day
- `focus_sessions`：started_by / duration_min / start_at / end_at / participants / status

## 路线图

- [x] M1 双人实时面板 + 时间轴/日历视图
- [x] M1.1 时间轴缩放、任务描述/子任务、自定义状态文字、打字统计实时显示
- [x] M2 共享番茄钟「一起自习」、打卡连击、打字阈值可调
- [x] M3 截止日双方提醒、专注超时暖心提醒与打气、每周双人复盘、任务编辑（当前）
- [ ] M2.1 小猫贴纸包换用 AI 设计稿
- [ ] M4 飞书日历同步、VPS 一键部署

## 故障排查

- 打字没反应：先看 `client/client.log` 是否有 `keyboard listener started`；运行 `venv\Scripts\python test_hook.py` 并随便敲几个键，可单独自检键盘钩子
- 窗口打不开：确认服务端已启动（`start_server.bat`）且 `client\config.json` 里 `server_url` 正确

## 目录结构

```
backend/      FastAPI 服务端（REST + WebSocket + SQLite）
client/       pywebview 桌面端（键盘钩子 + 前端页面）
deploy/       VPS 部署说明
docs/         架构文档
```
