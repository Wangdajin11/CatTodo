# CatTodo · 猫猫待办

双人陪伴式待办清单桌面应用（Windows / Python 系）。两人协作写清单、互相看见对方在做什么；任务按人着色、重叠时间并排显示；日历联动看截止日；全局打字统计，累计到阈值弹出可爱小猫暖心提醒。

## 功能

- **双人实时协作**：WebSocket 实时同步，任务按人着色（我=蓝 / TA=橙），重叠时间两人任务并排显示
- **三种视图**：清单列表 · 时间轴（±3 天，24 小时泳道）· 月历（截止日）
- **隐私开关**：单个任务可设为「仅自己可见」
- **状态可见**：专注 / 摸鱼 / 离线徽章 + 对方今日打字数
- **打字统计**：pynput 全局键盘钩子统计任意软件打字数，每 300 字弹出小猫贴纸提醒（随机 6 款）
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
- `tasks`：title / owner_id / start_time / end_time / due_date / done / is_private
- `typing_daily`：user_id / day / keys / minutes

## 路线图

- [x] M1 双人实时面板 + 时间轴/日历视图（当前）
- [ ] M2 打字小猫弹窗细化（阈值调节、贴纸包换用设计稿）、共享番茄钟「一起自习」、打卡连击
- [ ] M3 截止日双方提醒、暖心提醒（对方专注超 45 分钟）、每周双人复盘、任务编辑
- [ ] M4 飞书日历同步、VPS 一键部署

## 目录结构

```
backend/      FastAPI 服务端（REST + WebSocket + SQLite）
client/       pywebview 桌面端（键盘钩子 + 前端页面）
deploy/       VPS 部署说明
docs/         架构文档
```
