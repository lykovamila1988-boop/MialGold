@echo off
chcp 65001 >nul
cd /d "E:\MILA GOLD\mila-office"
set PYTHONIOENCODING=utf-8
echo Запускаю MILA OFFICE (веб)...
python webapp.py
pause
