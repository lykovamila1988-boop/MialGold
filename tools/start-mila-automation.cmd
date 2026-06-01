@echo off
rem ============================================================
rem MILA automation — единый запуск: bridge + n8n + webapp,
rem затем проверка health всех сервисов. Окна остаются открытыми.
rem ============================================================
echo Starting MILA automation (bridge + n8n + webapp)...

start "MILA n8n bridge" cmd /c "%~dp0start-n8n-bridge.cmd"
timeout /t 3 /nobreak >nul
start "MILA n8n" cmd /c "%~dp0start-n8n-local.cmd"
start "MILA webapp" cmd /c "%~dp0..\mila-office\start-webapp.cmd"

echo.
echo Жду подъёма сервисов (даю n8n до ~40с)...
rem n8n стартует дольше всех — поллим его health, прежде чем проверять всё.
powershell -NoProfile -Command ^
  "$ok=$false; for($i=0;$i -lt 20;$i++){ try{ if((Invoke-WebRequest 'http://127.0.0.1:5678/healthz' -TimeoutSec 2 -UseBasicParsing).StatusCode -eq 200){$ok=$true;break} }catch{}; Start-Sleep 2 }; if(-not $ok){ Write-Host '  n8n ещё не ответил — проверь окно MILA n8n' -ForegroundColor Yellow }"

echo.
echo === HEALTH CHECK ===
powershell -NoProfile -Command ^
  "function probe($n,$u){ try{ $r=Invoke-WebRequest $u -TimeoutSec 3 -UseBasicParsing; Write-Host ('  [OK]   {0,-8} HTTP {1}' -f $n,$r.StatusCode) -ForegroundColor Green }catch{ Write-Host ('  [DOWN] {0,-8} {1}' -f $n,$_.Exception.Message.Split([Environment]::NewLine)[0]) -ForegroundColor Red } };" ^
  "probe 'bridge' 'http://127.0.0.1:5051/health';" ^
  "probe 'n8n'    'http://127.0.0.1:5678/healthz';" ^
  "probe 'webapp' 'http://127.0.0.1:5000/api/health';" ^
  "Write-Host ''; Write-Host 'Сводка webapp /api/health:' -ForegroundColor Cyan;" ^
  "try{ $h=(Invoke-WebRequest 'http://127.0.0.1:5000/api/health' -TimeoutSec 3 -UseBasicParsing).Content | ConvertFrom-Json; Write-Host ('  gemini={0} claude={1} telegram={2} supabase={3} n8n_up={4} bridge_up={5} | OK={6}' -f $h.gemini.configured,$h.claude.configured,$h.telegram.configured,$h.supabase.configured,$h.n8n.up,$h.bridge.up,$h.ok) }catch{ Write-Host '  (webapp /api/health недоступен)' -ForegroundColor Yellow }"

echo.
echo Bridge:  http://127.0.0.1:5051/health
echo n8n UI:  http://127.0.0.1:5678
echo webapp:  http://127.0.0.1:5000   (health: /api/health)
echo.
echo Готово. Сервисы крутятся в отдельных окнах; закрой их, чтобы остановить.
pause
