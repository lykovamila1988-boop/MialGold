@echo off
rem Удаляет задачу автозапуска MILA. Сами сервисы не трогает (закрой окна/процессы вручную).
setlocal
set "TASK=MILA Automation Boot"
echo Удаляю задачу "%TASK%"...
schtasks /Delete /TN "%TASK%" /F
if %ERRORLEVEL%==0 ( echo [OK] Автозапуск отключён. ) else ( echo [инфо] Задача не найдена (возможно, уже удалена). )
endlocal
pause
