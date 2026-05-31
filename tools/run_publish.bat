@echo off
REM MILA авто-постинг: публикует одобренные посты, чьё время пришло.
REM Запускать по расписанию (Планировщик задач Windows) каждые ~15 минут.
set PYTHONIOENCODING=utf-8
cd /d "E:\MILA GOLD\tools"
python pipeline.py publish_due >> "E:\MILA GOLD\logs\autopost.log" 2>&1
