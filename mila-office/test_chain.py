# -*- coding: utf-8 -*-
"""Тестирование цепочки передачи между агентами."""
import sys
sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None

import json
import time
import requests
import secrets

BASE_URL = "http://127.0.0.1:5000"

def test_chain():
    """Протестировать цепочку передачи: Марина → Виктория."""
    print("\n" + "="*60)
    print("🧪 ТЕСТ ЦЕПОЧКИ ПЕРЕДАЧИ МЕЖДУ АГЕНТАМИ")
    print("="*60)

    # Проверяем что Flask доступен
    print("\n1️⃣  Проверяем доступность Flask...")
    try:
        r = requests.get(f"{BASE_URL}/api/meta", timeout=5)
        if r.status_code == 200:
            print("   ✅ Flask доступен на http://127.0.0.1:5000")
        else:
            print(f"   ❌ Flask вернул статус {r.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Flask недоступен: {e}")
        return False

    # Инициализируем сессию (для cookies и CSRF token в session)
    print("\n2️⃣  Инициализируем сессию...")
    session = requests.Session()
    try:
        r = session.get(f"{BASE_URL}/", timeout=5, allow_redirects=True)
        print(f"   ✅ Сессия инициализирована (cookies: {len(session.cookies)})")
    except Exception as e:
        print(f"   ⚠️  Не удалось инициализировать сессию: {e}")

    # Отправляем сообщение Марине (CSRF будет валиден через session cookies)
    print("\n3️⃣  Отправляем сообщение Марине (marina)...")

    # Создаём фиксированный токен для CSRF (простой подход)
    csrf_token = "test_csrf_token_12345"

    payload = {
        "agent": "marina",
        "message": "Готовый пост про выбор. [VERDICT: ready_next] [→ victoria]"
    }
    headers = {
        "X-CSRF-Token": csrf_token,
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/"
    }

    try:
        r = session.post(f"{BASE_URL}/api/chat", json=payload, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"   ❌ POST /api/chat вернул {r.status_code}")
            return False

        result = r.json()
        job_id = result.get("job")
        print(f"   ✅ Задача создана: {job_id}")
    except Exception as e:
        print(f"   ❌ Ошибка при отправке: {e}")
        return False

    # Ждём результата от агента
    print("\n4️⃣  Ожидаем результата от Марины...")
    max_attempts = 30  # 30 секунд максимум
    for attempt in range(max_attempts):
        try:
            r = requests.get(f"{BASE_URL}/api/result?job={job_id}", timeout=5)
            result = r.json()

            if result.get("status") == "pending":
                print(f"   ⏳ Попытка {attempt+1}: Марина ещё думает... ({(attempt+1) * 2}s)")
                time.sleep(2)
                continue

            if result.get("error"):
                print(f"   ❌ Ошибка от агента: {result['error']}")
                return False

            # Результат готов!
            print(f"\n   ✅ Марина ответила!")
            reply = result.get("reply", "")[:100]
            verdict = result.get("verdict", "unknown")
            next_agent = result.get("next_agent")

            print(f"\n5️⃣  РЕЗУЛЬТАТ МАРИНЫ:")
            print(f"   📝 Ответ: {reply}...")
            print(f"   🏷️  Verdict: {verdict}")
            print(f"   ➡️  Следующий агент: {next_agent}")

            # Проверяем что цепочка определена правильно
            if verdict == "ready_next" and next_agent == "victoria":
                print("\n" + "="*60)
                print("✅ ЦЕПОЧКА РАБОТАЕТ ПРАВИЛЬНО!")
                print("="*60)
                print("\n📊 РЕЗУЛЬТАТ ТЕСТИРОВАНИЯ:")
                print("   ✓ Марина получила сообщение")
                print("   ✓ Марина ответила с [VERDICT: ready_next]")
                print("   ✓ Марина указала [→ victoria]")
                print("   ✓ Система правильно определила next_agent=victoria")
                print("\n💡 ЧТО ПРОИСХОДИТ ДАЛЬШЕ:")
                print("   1. Фронтенд получает verdict='ready_next'")
                print("   2. Фронтенд видит next_agent='victoria'")
                print("   3. JavaScript автоматически переходит на Викторию")
                print("   4. Виктория видит историю и может редактировать")
                print("\n" + "="*60 + "\n")
                return True
            else:
                print(f"\n❌ НЕПРАВИЛЬНАЯ ЦЕПОЧКА!")
                print(f"   Ожидали: verdict=ready_next, next_agent=victoria")
                print(f"   Получили: verdict={verdict}, next_agent={next_agent}")
                return False

        except Exception as e:
            print(f"   ❌ Ошибка при получении результата: {e}")
            return False

    print(f"\n❌ Марина не ответила за {max_attempts*2} секунд")
    return False

if __name__ == "__main__":
    success = test_chain()
    sys.exit(0 if success else 1)
