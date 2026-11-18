@echo off
chcp 936 >nul
title 四序颐养 · 一键启动
mode con lines=30 cols=80

echo.
echo  ╔════════════════════════════════════════════════════╗
echo  ║            四序颐养 · 一键启动脚本                 ║
echo  ║   后端 + MySQL + 公网穿透（Cloudflare 自动切换）  ║
echo  ╚════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: ── 1. MySQL ──
echo  [1/3] MySQL 服务...
sc query MySQL80 | findstr /c:"RUNNING" >nul 2>&1
if errorlevel 1 net start MySQL80 >nul 2>&1
echo        ? 已运行

:: ── 2. 后端 ──
echo  [2/3] FastAPI 后端 (0.0.0.0:8001)...
netstat -ano | findstr ":8001" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    cd server
    start "四序颐养后端" python -m uvicorn app:app --host 0.0.0.0 --port 8001
    cd ..
    echo        等待后端就绪...
    timeout /t 6 /nobreak >nul
)
echo        ? 已运行

:: ── 3. 多 Tunnel 守护（PowerShell） ──
echo  [3/3] 公网穿透（Cloudflare + localhost.run 自动切换）...
echo        守护脚本正在后台启动，最多 20 秒获取公网地址...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_multi_tunnel.ps1"

echo.
echo  ══════════════════════════════════════════════════════
echo  说明:
echo    ? 本地访问: http://127.0.0.1:8001/
echo    ? 公网地址: 看上面 ?? 那一行
echo    ? 按 Ctrl+C 停止所有服务
echo  ══════════════════════════════════════════════════════
pause
