@echo off
chcp 65001 >nul
cd /d "%~dp0server"
echo 正在启动四序颐养服务（MySQL 数据库：siyu）...
start "" cmd /c "timeout /t 4 >nul & start "" http://127.0.0.1:8001/"
python -m uvicorn app:app --host 127.0.0.1 --port 8001
pause
