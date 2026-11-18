@echo off
chcp 936 >nul
title 四序颐养 · 本地版
mode con lines=24 cols=70

echo.
echo   ==========================================================
echo        四序颐养 · 本地版（前端 + 后端 + 数据库）
echo        不用安装 MySQL，数据保存在  数据库\local.db
echo   ==========================================================
echo.

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo   [错误] 没有检测到 Python，请先安装 Python 3.9+ 并勾选 Add to PATH
  echo.
  pause
  exit /b
)

echo   [1/3] 检查后端依赖 ...
python -c "import fastapi, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo         首次运行，正在安装依赖（需要联网，约 1 分钟）...
  python -m pip install -r 后端\requirements.txt
  echo.
)

echo   [2/3] 启动后端 FastAPI ...
echo         数据库: SQLite  数据库\local.db
echo         地址:   http://127.0.0.1:8001/
echo.

cd 后端
set DATABASE_URL=sqlite:///./local.db
start "四序颐养-后端" python -m uvicorn app:app --host 0.0.0.0 --port 8001
cd ..

echo   [3/3] 等待后端就绪（5 秒）...
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:8001/"

echo.
echo   ----------------------------------------------------------
echo    后端已启动，请不要关闭本窗口。
echo    电脑打开:  http://127.0.0.1:8001/     （自动进 PC 版）
echo    手机打开:  http://电脑IP:8001/        （自动进手机版）
echo              同一 Wi-Fi 下，用手机浏览器输入上面地址
echo    强制切换:  /pc 电脑版      /m 手机版
echo.
echo    关闭本窗口 = 结束程序
echo   ----------------------------------------------------------
echo.
pause >nul
