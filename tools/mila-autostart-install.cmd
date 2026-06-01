@echo off
rem ============================================================
rem Регистрирует автозапуск MILA при входе в Windows (Scheduled Task).
rem Запускается ОТ ТЕКУЩЕГО пользователя (нужны его пути python/npm и .env),
rem поэтому триггер — logon, не system boot.
rem ============================================================
setlocal
set "TASK=MILA Automation Boot"
set "PS=powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""E:\MILA GOLD\tools\mila-boot.ps1"""

echo Регистрирую задачу "%TASK%" (автозапуск при входе %USERNAME%)...
schtasks /Create /TN "%TASK%" /TR "%PS%" /SC ONLOGON /RU "%USERNAME%" /RL LIMITED /F /DELAY 0000:30

if %ERRORLEVEL%==0 (
  echo.
  echo [OK] Задача создана. При следующем входе в систему MILA поднимется сама.
  echo      Проверить:  schtasks /Query /TN "%TASK%"
  echo      Запустить сейчас:  schtasks /Run /TN "%TASK%"
  echo      Удалить:    tools\mila-autostart-uninstall.cmd
) else (
  echo.
  echo [ОШИБКА] Не удалось создать задачу. Запусти этот файл от своего пользователя
  echo          (НЕ «от администратора», иначе задача привяжется к другому профилю^).
)
endlocal
pause
