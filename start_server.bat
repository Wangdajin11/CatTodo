@echo off
cd /d %~dp0
venv\Scripts\python -m uvicorn backend.app:app --host 0.0.0.0 --port 8017
