<#
  mila-boot.ps1 - поднимает всю систему MILA при входе в Windows.

  Сервисы (все на 127.0.0.1, порядок важен - мост раньше n8n):
    1. n8n bridge   127.0.0.1:5051   (mila-office/n8n_bridge.py)
    2. n8n          127.0.0.1:5678   (+ task-runner :5679)
    3. webapp       127.0.0.1:5000   (mila-office/webapp.py)
    4. telegram poller (без порта - getUpdates поток ХОЧУ)

  Идемпотентно: если порт уже слушается (или поллер уже запущен) - сервис
  пропускается. Повторный вызов не плодит дубликаты. Окна скрыты, логи в logs\.

  Вручную:  powershell -ExecutionPolicy Bypass -File "E:\MILA GOLD\tools\mila-boot.ps1"
  Автозапуск: tools\mila-autostart-install.cmd (Scheduled Task при входе).
#>
$ErrorActionPreference = 'Continue'
$root = 'E:\MILA GOLD'
$logs = Join-Path $root 'logs'
if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs -Force | Out-Null }

function Test-Port($port) {
  $null -ne (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

function Test-PollerRunning {
  $p = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -like '*telegram_poller.py*' }
  return $null -ne $p
}

function Start-Svc($name, $cmdPath) {
  Write-Host "-> start $name ..."
  Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', "`"$cmdPath`"" -WindowStyle Hidden | Out-Null
}

function Wait-Port($name, $port, $seconds = 40) {
  for ($i = 0; $i -lt $seconds; $i++) {
    if (Test-Port $port) { Write-Host "  [OK] $name listening :$port"; return $true }
    Start-Sleep 1
  }
  Write-Host "  [WARN] $name did not come up in ${seconds}s (see logs)" -ForegroundColor Yellow
  return $false
}

Write-Host "=== MILA boot $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# 0) валидация .env ДО старта сервисов — ловим битый/пустой конфиг заранее,
#    чтобы агенты не сыпали ошибки, похожие на баги кода. Не блокируем запуск
#    (предупреждения норм), но печатаем отчёт в лог boot.
Write-Host "-> validate .env ..."
& python "$root\tools\validate_env.py" 2>&1 | ForEach-Object { Write-Host "   $_" }

# 1) bridge
if (Test-Port 5051) { Write-Host "= bridge already on :5051 - skip" }
else { Start-Svc 'bridge' "$root\tools\start-n8n-bridge.cmd"; Wait-Port 'bridge' 5051 20 }

# 2) n8n (slowest to start)
if (Test-Port 5678) { Write-Host "= n8n already on :5678 - skip" }
else { Start-Svc 'n8n' "$root\tools\start-n8n-local.cmd"; Wait-Port 'n8n' 5678 60 }

# 3) webapp
if (Test-Port 5000) { Write-Host "= webapp already on :5000 - skip" }
else { Start-Svc 'webapp' "$root\mila-office\start-webapp.cmd"; Wait-Port 'webapp' 5000 20 }

# 4) telegram poller (no port)
if (Test-PollerRunning) { Write-Host "= telegram poller already running - skip" }
else { Start-Svc 'telegram-poller' "$root\tools\start-telegram-poller.cmd"; Start-Sleep 2; Write-Host "  [OK] telegram poller started" }

Write-Host ""
Write-Host "=== HEALTH ==="
function Probe($n, $u) {
  try { $r = Invoke-WebRequest $u -TimeoutSec 3 -UseBasicParsing
        Write-Host ("  [OK]   {0,-8} HTTP {1}" -f $n, $r.StatusCode) -ForegroundColor Green }
  catch { Write-Host ("  [DOWN] {0,-8} {1}" -f $n, $_.Exception.Message.Split([Environment]::NewLine)[0]) -ForegroundColor Red }
}
Probe 'bridge' 'http://127.0.0.1:5051/health'
Probe 'n8n'    'http://127.0.0.1:5678/healthz'
Probe 'webapp' 'http://127.0.0.1:5000/api/health'
if (Test-PollerRunning) { Write-Host "  [OK]   poller   running" -ForegroundColor Green }
else { Write-Host "  [DOWN] poller   not found" -ForegroundColor Red }

Write-Host ""
Write-Host "Done. UI: http://127.0.0.1:5000 (office) | http://127.0.0.1:5678 (n8n)"
"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') boot done" | Out-File -Append -FilePath (Join-Path $logs 'mila-boot.log') -Encoding utf8
