"""
MILA OFFICE — Главный лаунчер
python office.py

Запускает любого агента из одного места.
"""
import sys, io
# Принудительно UTF-8 для консоли Windows (иначе русский и ✓ — кракозябры).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
except Exception:
    pass

from base import console, MILA_FOLDER, ANTHROPIC_KEY, INSTAGRAM_TOKEN, TELEGRAM_TOKEN, GUMROAD_TOKEN
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
import subprocess, sys

AGENTS = {
    "1": ("📣 Марина",    "Маркетолог",           "agent.py",    "Контент, Instagram, стратегия роста"),
    "2": ("✍️  Виктория", "Редактор",              "victoria.py", "Проверка текстов перед публикацией"),
    "3": ("👩 Алина",     "Менеджер клиентов",     "alina.py",    "Анкеты, подготовка к сессиям, CRM"),
    "4": ("💰 Дима",      "Финансы",               "dima.py",     "Доход, Gumroad, прогнозы"),
    "5": ("💬 Тёма",      "Telegram",              "tyoma.py",    "Канал, бот, welcome-цепочка"),
    "6": ("🔍 Оля",       "Тренды",                "olya.py",     "Вирусный контент, конкуренты"),
    "7": ("📅 Вася",      "Планировщик",           "vasya.py",    "Расписание, scheduled posts"),
    "8": ("🎯 Лера",      "Продажи",               "lera.py",     "Воронка, офферы, Gumroad"),
    "9": ("🗂️  Стас",     "Офис-менеджер",         "manager.py",  "Ревью агентов, метрики, задачи, бизнес-стратегия"),
    "10": ("🎬 Кирилл",   "Продюсер",              "producer.py", "Продуктовая линейка, запуски, позиционирование, масштаб"),
}

def show_status():
    table = Table(show_header=True, header_style="bold", border_style="dim")
    table.add_column("#", width=3, style="bold")
    table.add_column("Агент", width=16)
    table.add_column("Роль", width=22)
    table.add_column("Описание", width=36)
    table.add_column("Статус", width=8)

    for num, (emoji_name, role, file, desc) in AGENTS.items():
        import os
        exists = "✓ OK" if os.path.exists(file) else "✗ нет"
        style = "green" if "OK" in exists else "red"
        table.add_row(num, emoji_name, role, desc, f"[{style}]{exists}[/{style}]")
    console.print(table)

def check_env():
    checks = [
        ("ANTHROPIC_API_KEY", ANTHROPIC_KEY, "Обязателен"),
        ("INSTAGRAM_TOKEN",   INSTAGRAM_TOKEN, "Для Instagram агентов"),
        ("TELEGRAM_TOKEN",    TELEGRAM_TOKEN, "Для Тёмы"),
        ("GUMROAD_TOKEN",     GUMROAD_TOKEN, "Для Димы и Леры"),
    ]
    console.print("\n[bold]Статус API ключей:[/bold]")
    for name, val, note in checks:
        status = "[green]✓[/green]" if val else "[red]✗[/red]"
        console.print(f"  {status} {name} — {note}")

BANNER = """
╔═══════════════════════════════════════════════╗
║          MILA OFFICE  ·  @liudmyla.lykova     ║
║         10 агентов  ·  E:\\MILA GOLD            ║
╚═══════════════════════════════════════════════╝"""

def main():
    console.print(BANNER, style="bold")
    console.print(f"\n📁 Папка: [bold]{MILA_FOLDER}[/bold]")
    check_env()
    console.print()
    show_status()
    console.print("\n[dim]Введи номер агента или 'все' чтобы запустить всех последовательно[/dim]")

    while True:
        try:
            choice = Prompt.ask("\n[bold]Выбери агента[/bold] (1-10 или /выход)").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]До свидания![/dim]")
            break

        if choice == "/выход": break
        if choice == "все":
            for num in AGENTS:
                _, _, file, _ = AGENTS[num]
                console.print(f"\n[bold]Запускаю {AGENTS[num][0]}...[/bold]")
                try: subprocess.run([sys.executable, file])
                except Exception as e: console.print(f"[red]Ошибка: {e}[/red]")
            break
        if choice in AGENTS:
            emoji_name, role, file, _ = AGENTS[choice]
            console.print(f"\n[bold]Запускаю {emoji_name}...[/bold]\n")
            try: subprocess.run([sys.executable, file])
            except FileNotFoundError:
                console.print(f"[red]Файл {file} не найден. Убедись что все агенты в одной папке.[/red]")
            except KeyboardInterrupt:
                console.print(f"\n[dim]{emoji_name} завершила работу[/dim]")
            show_status()
        else:
            console.print("[dim]Введи число от 1 до 10[/dim]")

if __name__ == "__main__":
    main()
