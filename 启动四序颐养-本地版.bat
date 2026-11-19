@echo off
chcp 936 >nul
title 四序颐养 · 本地版
mode con lines=24 cols=70

echo.
echo   ==========================================================
echo        四序颐养 · 本地版（前端 + 后端 + 数据库）
echo        自带运行环境，无需安装 Python / MySQL，双击即用
echo        数据保存在  数据库\local.db
echo   ==========================================================
echo.

cd /d "%~dp0"

set "PY=python"
set "BUNDLED=0"
if exist "%~dp0运行环境\python.exe" (
  set "PY=%~dp0运行环境\python.exe"
  set "BUNDLED=1"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo   [错误] 没有找到 Python，也没有自带运行环境。
    echo          请使用完整压缩包（含 运行环境 文件夹），或安装 Python 3.9+ 并勾选 Add to PATH。
    echo.
    pause
    exit /b
  )
)

echo   [1/3] 检查后端依赖 ...
if "%BUNDLED%"=="1" (
  echo         使用自带运行环境，无需联网安装
) else (
  "%PY%" -c "import fastapi, uvicorn" >nul 2>nul
  if errorlevel 1 (
    echo         首次运行，正在安装依赖（需要联网，约 1 分钟）...
    "%PY%" -m pip install -r 后端\requirements.txt
    echo.
  )
)

echo   [2/3] 启动后端 FastAPI ...
echo         数据库: SQLite  数据库\local.db
echo         本机地址: http://127.0.0.1:8001/
echo.

rem 自动获取本机局域网 IP（取有默认网关的网卡），并尝试放行 8001 端口（需管理员权限，失败不影响本机使用）
set "LANIP="
for /f "usebackq delims=" %%a in (`powershell -NoProfile -Command "(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' }).IPv4Address.IPAddress | Select-Object -First 1"`) do set "LANIP=%%a"
if defined LANIP (
  netsh advfirewall firewall show rule name="四序颐养8001" >nul 2>nul
  if errorlevel 1 netsh advfirewall firewall add rule name="四序颐养8001" dir=in action=allow protocol=TCP localport=8001 >nul 2>nul
)

cd 后端
set DATABASE_URL=sqlite:///./local.db
start "四序颐养-后端" "%PY%" -m uvicorn app:app --host 0.0.0.0 --port 8001
cd ..

echo   [3/3] 等待后端就绪（5 秒）...
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:8001/"

echo.
echo   ----------------------------------------------------------
echo    后端已启动，请不要关闭本窗口。
echo    电脑打开:  http://127.0.0.1:8001/     （自动进 PC 版）
if defined LANIP (
  echo    手机/其他电脑: http://%LANIP%:8001/   （同一 Wi-Fi 下输入这个）
) else (
  echo    手机打开:  http://电脑IP:8001/        （自动进手机版）
  echo              同一 Wi-Fi 下，用手机浏览器输入上面地址
)
echo              别的设备不要用 127.0.0.1（那是指设备自己）
echo              打不开就检查：是否同一 Wi-Fi、防火墙是否放行 8001
echo    强制切换:  /pc 电脑版      /m 手机版
echo.
echo    关闭本窗口 = 结束程序
echo   ----------------------------------------------------------
echo.
pause >nul
