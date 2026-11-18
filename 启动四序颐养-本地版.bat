@echo off
chcp 936 >nul
title 四序颐养 · 本地版
mode con lines=22 cols=65

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║        四序颐养 · 本地单机版             ║
echo  ║   不需要 MySQL，不需要公网穿透          ║
echo  ║   数据保存在 ./server/local.db          ║
echo  ╚══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: 用 SQLite（零依赖）启动后端
echo  [1/2] 启动 FastAPI 后端...
echo        数据库: SQLite (server\local.db)
echo        地址:   http://127.0.0.1:8001/
echo.

cd server
set DATABASE_URL=sqlite:///./local.db
start "四序颐养后端" python -m uvicorn app:app --host 0.0.0.0 --port 8001
cd ..

echo        等待后端就绪 (5 秒)...
timeout /t 5 /nobreak >nul

:: 打开浏览器
start "" "http://127.0.0.1:8001/"

echo.
echo  ════════════════════════════════════════════
echo  后端正在运行！不要关闭此窗口。
echo  打开浏览器访问: http://127.0.0.1:8001/
echo.
echo  局域网访问 (同 Wi-Fi): 浏览器输入
echo    http://%COMPUTERNAME%:8001/
echo    或 http://你的IP:8001/
echo.
echo  关闭此窗口 = 停止服务
echo  ════════════════════════════════════════════
echo.
pause >nul
