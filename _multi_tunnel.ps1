# 四序颐养 · 公网隧道守护脚本
# 优先 Cloudflare 快速隧道，失败后自动切换到 localhost.run
$ErrorActionPreference = "SilentlyContinue"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = "http://127.0.0.1:8001"
$urlFile = Join-Path $root "_tunnel_url.txt"
Remove-Item $urlFile -Force

$children = @()
$publicUrl = $null
$provider = ""

function Find-Url([string]$file, [string]$pattern) {
    if (-not (Test-Path $file)) { return $null }
    $text = Get-Content $file -Raw
    if (-not $text) { return $null }
    $m = [regex]::Match($text, $pattern)
    if ($m.Success) { return $m.Value }
    return $null
}

# ---------- 1. Cloudflare ----------
$cf = Join-Path $root "cloudflared.exe"
if (Test-Path $cf) {
    Write-Host "  尝试 Cloudflare 隧道..." -ForegroundColor DarkGray
    $log = Join-Path $env:TEMP "siyu_cf_$PID.log"
    Remove-Item $log -Force
    $p = Start-Process -FilePath $cf -ArgumentList @("tunnel", "--url", $target, "--no-autoupdate") `
        -RedirectStandardError $log -RedirectStandardOutput "$log.out" -WindowStyle Hidden -PassThru
    $children += $p
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        $u = Find-Url $log "https://[a-z0-9-]+\.trycloudflare\.com"
        if ($u) { $publicUrl = $u; $provider = "Cloudflare"; break }
        if ($p.HasExited) { break }
    }
    if (-not $publicUrl -and $p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force }
}

# ---------- 2. localhost.run ----------
if (-not $publicUrl -and (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Write-Host "  Cloudflare 不可用，尝试 localhost.run..." -ForegroundColor DarkGray
    $log = Join-Path $env:TEMP "siyu_lhr_$PID.log"
    $err = "$log.err"
    Remove-Item $log, $err -Force
    $p = Start-Process -FilePath "ssh" -ArgumentList @(
        "-tt", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=NUL",
        "-o", "ServerAliveInterval=30", "-R", "80:localhost:8001", "nokey@localhost.run"
    ) -RedirectStandardOutput $log -RedirectStandardError $err -WindowStyle Hidden -PassThru
    $children += $p
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        $u = Find-Url $log "https://[a-z0-9-]+\.lhr\.life"
        if (-not $u) { $u = Find-Url $err "https://[a-z0-9-]+\.lhr\.life" }
        if ($u) { $publicUrl = $u; $provider = "localhost.run"; break }
        if ($p.HasExited) { break }
    }
    if (-not $publicUrl -and $p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force }
}

Write-Host ""

if ($publicUrl) {
    Set-Content -Path $urlFile -Value $publicUrl -Encoding UTF8
    Write-Host "  ================================================================" -ForegroundColor Green
    Write-Host "   公网地址（$provider）" -ForegroundColor Green
    Write-Host "   $publicUrl" -ForegroundColor Green
    Write-Host "   本地地址  http://127.0.0.1:8001/" -ForegroundColor Green
    Write-Host "  ================================================================" -ForegroundColor Green
    Write-Host "   按 Ctrl+C 停止隧道"
} else {
    Write-Host "  [提示] 公网隧道未建立成功（Cloudflare 限流或网络不可达）。" -ForegroundColor Yellow
    Write-Host "  本地地址仍可使用: http://127.0.0.1:8001/"
    Write-Host "  如需稳定的公网访问，建议把后端部署到 CloudBase 等云平台。"
}

# ---------- 守护 ----------
try {
    while ($publicUrl) {
        Start-Sleep -Seconds 5
        foreach ($c in $children) {
            if ($c.HasExited) { throw "tunnel exited" }
        }
    }
} catch {
    Write-Host "  [提示] 隧道已断开。" -ForegroundColor Yellow
} finally {
    foreach ($c in $children) {
        if ($c -and -not $c.HasExited) { Stop-Process -Id $c.Id -Force }
    }
    Remove-Item $urlFile -Force
}
