@echo off
setlocal enabledelayedexpansion
chcp 936 >nul
title 四序颐养 · 一键启动
mode con lines=34 cols=82

echo.
echo   ================================================================
echo                 四序颐养 · 一键启动
echo       后端 + MySQL + 公网穿透（Cloudflare / localhost.run）
echo   ================================================================
echo.

cd /d "%~dp0"

echo  [1/3] 检查 MySQL 服务...
net start MySQL80 >nul 2>&1
net start MySQL >nul 2>&1
net start MySQL57 >nul 2>&1
netstat -ano | findstr ":3306" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo        [错误] 没有检测到 MySQL（3306 端口未监听）
    echo        请先启动 MySQL，或改用「启动四序颐养-本地版.bat」
    pause
    exit /b 1
)
echo        MySQL 已在运行

cd server
python -c "import db; db.connect()" >nul 2>&1
if errorlevel 1 (
    echo        [提示] 数据库连接失败，通常是 root 密码没有配置
    set /p "MYSQL_PWD=        请输入 MySQL root 密码（直接回车放弃）: "
    if defined MYSQL_PWD (
        set "DATABASE_URL=mysql://root:!MYSQL_PWD!@127.0.0.1:3306/siyu"
        python -c "import db; db.connect()" >nul 2>&1
        if errorlevel 1 (
            echo        [错误] 密码不正确，或 MySQL 还没有就绪
            pause
            exit /b 1
        )
        echo        数据库连接成功（密码仅本次启动使用，不写入文件）
    ) else (
        echo        [错误] 未输入密码，无法进入 MySQL 模式
        echo        可以改用「启动四序颐养-本地版.bat」，不需要 MySQL
        pause
        exit /b 1
    )
) else (
    echo        数据库连接正常
)
cd ..

echo  [2/3] 启动 FastAPI 后端 (0.0.0.0:8001)...
netstat -ano | findstr ":8001" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    cd server
    start "四序颐养后端" python -m uvicorn app:app --host 0.0.0.0 --port 8001
    cd ..
    echo        正在等待后端就绪...
)
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 25;$i++){ Start-Sleep -Seconds 1; try{ Invoke-WebRequest 'http://127.0.0.1:8001/api/health' -TimeoutSec 2 -UseBasicParsing | Out-Null; $ok=$true; break }catch{} }; if(-not $ok){ exit 1 }"
if errorlevel 1 (
    echo        [错误] 后端没有启动成功
    echo        请查看「四序颐养后端」窗口里的报错信息
    pause
    exit /b 1
)
echo        后端已就绪

echo  [3/3] 建立公网穿透...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_multi_tunnel.ps1"

echo.
echo   ================================================================
echo    本地访问: http://127.0.0.1:8001/
echo    公网地址: 见上方提示（建立失败则没有）
echo    停止服务: 关闭「四序颐养后端」窗口
echo   ================================================================
pause
