"""Алина — Менеджер клиентов. python alina.py"""
from base import *
from shared_tools import find_clients_by_pattern, get_client_list

SYSTEM = """Ты — Алина, менеджер клиентов Людмилы Лыковой. Ты знаешь каждую клиентку, ведёшь их истории и готовишь Людмилу к сессиям.

МЕТОДОЛОГИЯ «ТОЧКИ ВЫБОРА»:
- Ловушка знакомой боли (Спасатель)
- Синдром заслуживания (Угодница)
- Точка выбора (Избегание)
- Интеграция новой идентичности

ПРОДУКТЫ:
- Бесплатная диагностика 20 мин
- Консультация $120 CAD
- Пакет 4 сессии $420 CAD
- Пакет 8 сессий $750 CAD

СТРУКТУРА ПАПКИ КЛИЕНТОВ:
- 03-clients/intake-forms/ — анкеты
- 03-clients/session-notes/ — заметки после сессий
- 03-clients/profiles/ — профили клиенток

ЧТО ДЕЛАЕШЬ:
1. Анализируешь анкеты → определяешь паттерн
2. Готовишь к первой сессии: профиль, вопросы, красные флаги
3. После сессии — структурируешь заметки Людмилы
4. Отслеживаешь прогресс клиенток
5. Напоминаешь о follow-up

СТИЛЬ:
Профессиональный, конфиденциальный. Клиентки — реальные люди, относись бережно."""

TOOLS = core_tools("Читать анкету или заметки клиентки",
                   "Сохранить профиль или сводку сессии",
                   "Показать список клиенток или файлов",
                   list_default="03-clients") + [
    {"name": "find_clients_by_pattern", "description": "Найти клиентов с заданным паттерном (Спасатель, Угодница, Избегание)",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string", "description": "Паттерн: Спасатель, Угодница или Избегание"}}, "required": ["pattern"]}},
    {"name": "get_client_list", "description": "Получить полный список всех клиентов из intake-форм",
     "input_schema": {"type": "object", "properties": {}}},
]

def handle(name, inp):
    if name == "find_clients_by_pattern": return find_clients_by_pattern(inp.get("pattern", ""))
    if name == "get_client_list": return get_client_list()
    if name == "write_file":
        log("clients", f"Saved: {inp['path']}")
    res = core_handle(name, inp, list_default="03-clients")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/клиентки":  "Покажи список всех клиенток из папки 03-clients/",
    "/анкета":    "Прочитай последнюю анкету из 03-clients/intake-forms/ и подготовь меня к первой сессии",
    "/сводка":    "Прочитай мои заметки из 03-clients/session-notes/ и создай структурированную сводку",
    "/прогресс":  "Покажи все профили клиенток и сравни начало с последними заметками",
}

if __name__ == "__main__":
    chat_loop("Алина", "👩‍💼", "cyan", SYSTEM, TOOLS, handle, QUICK)
