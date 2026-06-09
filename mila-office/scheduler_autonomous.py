"""Scheduler для автономного цикла публикации (ежедневно)

Запускает autonomous_daily_loop.py в следующие времена:
- 00:30 - начало цикла
- 09:00 - публикация поста #1
- 14:00 - публикация поста #2
- 20:00 - публикация поста #3
- 23:00 - подготовка на завтра
"""

import time
import schedule
from datetime import datetime
from pathlib import Path
import subprocess
import sys


# Путь к скрипту автономного цикла
AUTONOMOUS_SCRIPT = Path(__file__).parent / "autonomous_daily_loop.py"
LOGS_DIR = Path(__file__).parent.parent / "logs"


def run_daily_loop():
    """Запустить полный автономный цикл"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Запускаю автономный цикл...")

    try:
        result = subprocess.run(
            [sys.executable, str(AUTONOMOUS_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=600  # 10 минут timeout
        )

        if result.returncode == 0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Цикл завершён успешно")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Ошибка: {result.stderr}")

    except subprocess.TimeoutExpired:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Timeout - цикл занял > 10 минут")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Ошибка запуска: {e}")


def setup_schedule():
    """Установить расписание запусков"""

    # Основной запуск - каждый день в 00:30
    schedule.every().day.at("00:30").do(run_daily_loop)

    print("="*80)
    print("SCHEDULER: Автономный цикл публикации контента".center(80))
    print("="*80)
    print("\nРасписание:")
    print("  00:30 - Запуск полного цикла (анализ → создание → редактура → публикация)")
    print("  09:00 - Пост #1 (утро)")
    print("  14:00 - Пост #2 (день)")
    print("  20:00 - Пост #3 (вечер)")
    print("  23:00 - Подготовка плана на завтра")
    print("\nСистема полностью АВТОНОМНА и не требует участия человека")
    print("="*80)
    print()


def run_scheduler():
    """Запустить scheduler (работает бесконечно)"""

    setup_schedule()

    print(f"Scheduler запущен в {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Ожидание запланированных задач... (Ctrl+C для остановки)\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Проверять каждую минуту

    except KeyboardInterrupt:
        print("\n\nScheduler остановлен пользователем")


def run_once_now():
    """Запустить цикл один раз (для тестирования)"""
    print(f"Запускаю цикл один раз (тест)...\n")
    run_daily_loop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scheduler для автономного цикла контента")
    parser.add_argument(
        "--mode",
        choices=["schedule", "once"],
        default="once",
        help="schedule=работать бесконечно, once=запустить один раз"
    )

    args = parser.parse_args()

    if args.mode == "once":
        run_once_now()
    else:
        run_scheduler()
