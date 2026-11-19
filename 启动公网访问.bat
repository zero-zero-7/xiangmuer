@echo off
chcp 936 >nul
title 四序颐养 · 公网访问（Cloudflare 临时隧道）
mode con lines=22 cols=78

echo.
echo   ==========================================================
echo     四序颐养 · 公网访问（Cloudflare 临时隧道）
echo   ==========================================================
echo.
echo   使用前请先双击运行「启动四序颐养-本地版.bat」，
echo   并确认后端窗口里显示 http://127.0.0.1:8001/ 可正常打开。
echo.
echo   隧道启动后，下面会出现一行
echo       https://xxxx.trycloudflare.com
echo   这就是公网地址，任何网络、任何设备都能打开。
echo.
echo   注意：
echo     - 地址每次重启都会变；
echo     - 本窗口和后端窗口都不能关，关了公网访问即中断；
echo     - 公网开放后请尽快修改演示账号密码。
echo.
pause

set "CF=%ProgramFiles(x86)%\cloudflared\cloudflared.exe"
if not exist "%CF%" set "CF=%ProgramFiles%\cloudflared\cloudflared.exe"
if not exist "%CF%" (
  echo   [错误] 未找到 cloudflared，请先安装：
  echo          https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
  echo.
  pause
  exit /b
)

"%CF%" tunnel --url http://127.0.0.1:8001 --no-autoupdate

echo.
echo   隧道已结束。
pause >nul
