"""Алина — Менеджер клиентов (CRM). python alina.py

Отслеживает путь клиентки через воронку:
intake-form → первая сессия → пакет сессий → follow-up → повторные консультации

Поддерживает сквозную идентификацию через chain_id для отслеживания цепочки взаимодействий.
Знает, от какого агента пришёл запрос (from_agent), и логирует вехи customer journey.
"""
import uuid
from datetime import datetime
from base import *
from shared_tools import find_clients_by_pattern, get_client_list

SYSTEM = """Ты — Алина, менеджер клиентов Людмилы Лыковой. Ты знаешь каждую клиентку, ведёшь их истории и готовишь Людмилу к сессиям.

ВОРОНКА КЛИЕНТА (CUSTOMER JOURNEY):
Стадия 1: ЛИДИРОВАНИЕ
  - Источник: Instagram DM / Telegram / Website
  - Действие: Прием intake-формы (Лера → ты)
  - Вывод: паттерн (Спасатель/Угодница/Избегание), готовность, цена
  - Выход: Передача Людмиле на консультацию или диагностику

Стадия 2: КОНСУЛЬТАЦИЯ/ДИАГНОСТИКА
  - Бесплатная диагностика 20 мин → осознание + скрытая оценка
  - Консультация $120 CAD → направление работы + рекомендация пакета
  - После консультации → сводка и профиль в 03-clients/session-notes/

Стадия 3: ПАКЕТ СЕССИЙ
  - Пакет 4 сессии $420 CAD (или 8 сессий $750 CAD)
  - Твоя роль: готовить Людмилу к каждой сессии (история, дома задания, флаги)
  - Отслеживать приверженность (сколько сессий пройдено)

Стадия 4: FOLLOW-UP & ПОВТОРНЫЕ КОНСУЛЬТАЦИИ
  - После пакета: проверка прогресса, напоминание о достижениях
  - Поддержание контакта: письма, предложение follow-up сессий
  - Новые консультации или рекомендация workbook практикума

МЕТОДОЛОГИЯ «ТОЧКИ ВЫБОРА»:
- Ловушка знакомой боли (Спасатель) → ждет спасения, не берет ответственность
- Синдром заслуживания (Угодница) → берет на себя всё, игнорирует потребности
- Точка выбора (Избегание) → избегает конфликтов, откладывает решения
- Интеграция новой идентичности → выход из цикла

СТРУКТУРА ПАПКИ КЛИЕНТОВ:
- 03-clients/intake-forms/ — анкеты (источник лидов)
- 03-clients/session-notes/ — заметки Людмилы после каждой сессии
- 03-clients/profiles/ — профили клиенток (история, тип пакета, статус)

ЧТО ДЕЛАЕШЬ:
1. Анализируешь анкеты → определяешь паттерн + готовность к пакету
2. Готовишь профиль перед первой сессией: история, ключевые вопросы, красные флаги
3. После каждой сессии (заметки Людмилы) → структурируешь, вносишь в профиль
4. Отслеживаешь прогресс → количество сессий, результаты, готовность к пакету
5. Напоминаешь о follow-up → через 2 недели, месяц, 3 месяца после финала

КОНТЕКСТ ЗАПРОСА (from_agent):
- Если запрос от Лера (sales) → ты получаешь новый лид и готовишь first-contact профиль
- Если запрос от Людмилы/user → ты подготавливаешь к сессии или анализируешь прогресс
- Если от другого агента → учитываешь их контекст в рекомендациях

CHAIN_ID для сквозного отслеживания:
- Каждое взаимодействие с клиенткой привязано к chain_id (цепочка обработки)
- Позволяет отследить: лид → первая консультация → пакет → результат
- Логируется автоматически; ты просто работаешь как обычно

СТИЛЬ:
Профессиональный, конфиденциальный, заботливый. Клиентки — реальные люди с реальными болями.
Говори «клиентка» и «она», не «клиент». Отноись бережно к истории каждой.
Нет стресса по срокам — у каждой свой темп.
"""

TOOLS = core_tools(
    "Читать анкету, заметки сессии или профиль клиентки",
    "Сохранить профиль, сводку сессии или план follow-up",
    "Показать список клиенток или файлов в 03-clients",
    list_default="03-clients"
) + [
    {
        "name": "find_clients_by_pattern",
        "description": "Найти клиентов по паттерну (Спасатель, Угодница, Избегание) для анализа или рекомендаций",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Паттерн: Спасатель, Угодница или Избегание"}
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "get_client_list",
        "description": "Получить полный список всех клиентов из intake-форм (для управления воронкой)",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "log_client_journey",
        "description": "Логировать вехи customer journey (лид → первая сессия → пакет → follow-up)",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string", "description": "Имя клиентки"},
                "stage": {"type": "string", "description": "Стадия: intake, consultation, package, followup, repeat"},
                "notes": {"type": "string", "description": "Заметки о переходе"},
                "chain_id": {"type": "string", "description": "ID цепочки обработки (опц.)"}
            },
            "required": ["client_name", "stage"]
        }
    },
    {
        "name": "generate_chain_id",
        "description": "Сгенерировать уникальный chain_id для отслеживания цепочки взаимодействий (автоматически если не указан)",
        "input_schema": {"type": "object", "properties": {"prefix": {"type": "string", "description": "Префикс (напр. 'client_journey')"}}}
    },
]

def _generate_chain_id(prefix="journey"):
    """Создать уникальный ID для цепочки обработки."""
    return f"{prefix}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"

def log_client_journey(inp):
    """Логировать вехи customer journey клиентки."""
    client_name = inp.get("client_name", "unknown")
    stage = inp.get("stage", "unknown")
    notes = inp.get("notes", "")
    chain_id = inp.get("chain_id")

    msg = f"CLIENT={client_name} STAGE={stage}"
    if notes:
        msg += f" NOTES={notes[:100]}"
    if chain_id:
        msg += f" CHAIN={chain_id}"

    log("client_journey", msg)
    return f"✓ Веха зафиксирована: {client_name} → {stage} {f'(цепочка {chain_id})' if chain_id else ''}"

def generate_chain_id(inp):
    """Сгенерировать chain_id для отслеживания."""
    prefix = inp.get("prefix", "journey")
    cid = _generate_chain_id(prefix)
    log("chain", f"Generated chain_id={cid}")
    return cid

def handle(name, inp):
    if name == "find_clients_by_pattern":
        return find_clients_by_pattern(inp.get("pattern", ""))
    if name == "get_client_list":
        return get_client_list()
    if name == "log_client_journey":
        return log_client_journey(inp)
    if name == "generate_chain_id":
        return generate_chain_id(inp)
    if name == "write_file":
        client_path = inp.get("path", "")
        log("clients", f"Saved: {client_path}")
    res = core_handle(name, inp, list_default="03-clients")
    return res if res is not None else f"Неизвестный инструмент: {name}"

QUICK = {
    "/клиентки": "Покажи список всех клиенток из папки 03-clients/ (сколько всего, стадии)",
    "/анкета": "Прочитай последнюю анкету из 03-clients/intake-forms/ и подготовь меня к первой сессии с анализом паттерна",
    "/сводка": "Прочитай мои заметки из 03-clients/session-notes/ и создай структурированную сводку с прогрессом",
    "/прогресс": "Покажи все профили клиенток и сравни начало с последними заметками — где сдвиги?",
    "/воронка": "Проанализируй воронку: intake → диагностика → пакет → follow-up. Кто где застрял?",
}

if __name__ == "__main__":
    chat_loop("Алина", "👩‍💼", "cyan", SYSTEM, TOOLS, handle, QUICK)
