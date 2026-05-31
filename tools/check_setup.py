#!/usr/bin/env python3
"""
check_setup.py — проверка доступов MILA GOLD (Instagram / Threads).

Запускайте КАЖДЫЙ РАЗ после обновления токена. Скрипт:
  1. проверяет токен (живой / просрочен, какие scopes, когда истекает);
  2. находит Facebook-страницы, доступные токену;
  3. находит привязанный Instagram Business аккаунт и его ID;
  4. печатает готовые значения для .env (IG_USER_ID и т.д.);
  5. при флаге --write записывает найденные значения прямо в .env.

Использование:
    python check_setup.py            # только показать диагноз
    python check_setup.py --write    # ещё и вписать IG_USER_ID/IG_ACCESS_TOKEN в .env

Ничего не публикует — только чтение (плюс опциональная правка .env локально).
"""
import sys
import argparse
import datetime

from _common import ENV_PATH, graph_get, GraphError, run_cli

# Минимально нужные scope'ы для скриптов аналитики/публикации.
NEEDED_IG_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_comments",
    "instagram_manage_insights",
    "instagram_manage_messages",
]

OK = "✅"
NO = "❌"
WARN = "⚠️ "


def _read_env_lines():
    if not ENV_PATH.exists():
        sys.exit(f"{NO} Файл не найден: {ENV_PATH}\n"
                 "   Скопируйте .env.example → .env и впишите токен.")
    return ENV_PATH.read_text(encoding="utf-8").splitlines()


def _env_value(lines, key):
    for ln in lines:
        if ln.strip().startswith(f"{key}="):
            return ln.split("=", 1)[1].strip()
    return ""


def _mini_cfg(token, version):
    """Лёгкий cfg для graph_get без обязательных IG-полей."""
    return {"token": token, "version": version,
            "base": "https://graph.facebook.com"}


def _set_env_key(lines, key, value):
    """Возвращает новый список строк с обновлённым (или добавленным) key=value."""
    out, found = [], False
    for ln in lines:
        if ln.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"{key}={value}")
    return out


def _refresh_long_lived_token(lines, version):
    """
    Продлевает долгоживущий Instagram-токен ещё на ~60 дней
    (endpoint ig_refresh_token; токен должен быть уже долгоживущим).
    Записывает новый токен в .env.
    """
    token = _env_value(lines, "IG_ACCESS_TOKEN")
    if not token:
        sys.exit(f"{NO} В .env нет IG_ACCESS_TOKEN — нечего продлевать.")
    cfg = {"token": token, "version": version,
           "base": "https://graph.instagram.com"}
    try:
        res = graph_get(cfg, "refresh_access_token",
                        params={"grant_type": "ig_refresh_token"})
    except GraphError as e:
        print(f"{NO} Не удалось продлить токен:\n   {e}")
        print("   Токен должен быть ДОЛГОЖИВУЩИМ и старше 24 часов. "
              "Если он короткоживущий — сгенерируйте новый и запустите --write.")
        sys.exit(1)
    new_token = res.get("access_token")
    days = int(res.get("expires_in", 0)) // 86400
    new = _set_env_key(lines, "IG_ACCESS_TOKEN", new_token)
    ENV_PATH.write_text("\n".join(new) + "\n", encoding="utf-8")
    print(f"{OK} Токен продлён ещё на ~{days} дн. и записан в {ENV_PATH}.")


def main():
    p = argparse.ArgumentParser(description="Проверка доступов MILA GOLD")
    p.add_argument("--write", action="store_true",
                   help="вписать найденные IG_USER_ID/IG_ACCESS_TOKEN в .env")
    p.add_argument("--refresh", action="store_true",
                   help="продлить долгоживущий Instagram-токен на ~60 дней")
    args = p.parse_args()

    lines = _read_env_lines()
    version = _env_value(lines, "GRAPH_API_VERSION") or "v25.0"
    flow = (_env_value(lines, "IG_API_FLOW") or "facebook").lower()

    if args.refresh:
        _refresh_long_lived_token(lines, version)
        return

    # Токен берём из IG_ACCESS_TOKEN, иначе из FB_ACCESS_TOKEN.
    token = _env_value(lines, "IG_ACCESS_TOKEN") or _env_value(lines, "FB_ACCESS_TOKEN")
    token_src = "IG_ACCESS_TOKEN" if _env_value(lines, "IG_ACCESS_TOKEN") else "FB_ACCESS_TOKEN"
    if not token:
        sys.exit(f"{NO} Нет токена в .env (ни IG_ACCESS_TOKEN, ни FB_ACCESS_TOKEN).")

    print(f"\n🔑 Токен из {token_src}, способ подключения: {flow}, Graph API {version}\n")

    if flow == "instagram_login":
        _check_instagram_login(lines, token, version, args.write)
    else:
        _check_facebook(lines, token, version, args.write)


def _check_instagram_login(lines, token, version, do_write):
    """Новый «Instagram API with Instagram Login»: graph.instagram.com, узел me."""
    cfg = {"token": token, "version": version,
           "base": "https://graph.instagram.com"}
    try:
        me = graph_get(cfg, "me", params={
            "fields": "user_id,username,account_type,media_count,followers_count"})
    except GraphError as e:
        print(f"{NO} Токен не работает на graph.instagram.com:\n   {e}")
        print("   Нужен токен из flow «Instagram API with Instagram Login», "
              "а не из Facebook Login.")
        sys.exit(1)

    ig_id = me.get("user_id") or me.get("id")
    print(f"{OK} Подключён Instagram: @{me.get('username')} "
          f"(id {ig_id}, тип {me.get('account_type','?')}, "
          f"{me.get('followers_count','?')} подписчиков, "
          f"{me.get('media_count','?')} постов)")

    if me.get("account_type") not in ("BUSINESS", "MEDIA_CREATOR", None):
        print(f"{WARN}Тип аккаунта {me.get('account_type')} — для публикации "
              "нужен Business или Creator.")

    print(f"\n{OK} Готово к работе! Значения для .env:")
    print(f"     IG_API_FLOW=instagram_login")
    print(f"     IG_USER_ID={ig_id}")
    print(f"     IG_ACCESS_TOKEN=<этот токен>")

    if do_write:
        new = _set_env_key(lines, "IG_API_FLOW", "instagram_login")
        new = _set_env_key(new, "IG_USER_ID", ig_id)
        new = _set_env_key(new, "IG_ACCESS_TOKEN", token)
        ENV_PATH.write_text("\n".join(new) + "\n", encoding="utf-8")
        print(f"\n💾 Записано в {ENV_PATH}.  Проверка: python get_analytics.py account")
    else:
        print("\n   Запустите с --write, чтобы вписать это в .env автоматически.")


def _check_facebook(lines, token, version, do_write):
    """«Instagram Graph API» через Facebook-страницу: graph.facebook.com."""
    cfg = _mini_cfg(token, version)

    # 1) Токен: валидность, scopes, срок.
    try:
        dbg = graph_get(cfg, "debug_token",
                        params={"input_token": token}).get("data", {})
    except GraphError as e:
        print(f"{NO} Токен недействителен:\n   {e}")
        sys.exit(1)
    if not dbg.get("is_valid"):
        print(f"{NO} Токен НЕ валиден (is_valid=false). Сгенерируйте новый.")
        sys.exit(1)

    scopes = dbg.get("scopes", [])
    exp = dbg.get("data_access_expires_at") or dbg.get("expires_at") or 0
    when = ("∞" if not exp else
            datetime.datetime.fromtimestamp(exp).strftime("%Y-%m-%d"))
    print(f"{OK} Токен валиден. Тип: {dbg.get('type')}, истекает: {when}")

    missing = [s for s in NEEDED_IG_SCOPES if s not in scopes]
    if missing:
        print(f"{WARN}Не хватает Instagram-разрешений: {', '.join(missing)}")
        print("   Добавьте их в Graph API Explorer и сгенерируйте токен заново.")
    else:
        print(f"{OK} Все нужные Instagram-разрешения на месте.")

    # 2) Страницы + привязанный IG.
    print("\n📄 Доступные Facebook-страницы:")
    pages = graph_get(cfg, "me/accounts",
                      params={"fields": "name,id,instagram_business_account{id,username,followers_count,media_count}"}
                      ).get("data", [])
    if not pages:
        print(f"   {NO} Токену не видно ни одной страницы (нужен scope pages_show_list "
              "и доступ к странице при генерации токена).")
        sys.exit(1)

    ig_id = None
    for pg in pages:
        iga = pg.get("instagram_business_account")
        if iga:
            ig_id = iga.get("id")
            print(f"   {OK} {pg.get('name')} (id {pg.get('id')}) → "
                  f"IG @{iga.get('username')} (id {ig_id}, "
                  f"{iga.get('followers_count','?')} подписчиков, "
                  f"{iga.get('media_count','?')} постов)")
        else:
            print(f"   {WARN}{pg.get('name')} (id {pg.get('id')}) → "
                  f"Instagram не привязан")

    print()
    if not ig_id:
        print(f"{NO} Instagram Business аккаунт не найден ни на одной странице.")
        print("   Привяжите IG (Business/Creator) к странице FB и/или добавьте "
              "scope instagram_basic, затем перегенерируйте токен.")
        sys.exit(1)

    print(f"{OK} Готово к работе! Значения для .env:")
    print(f"     IG_USER_ID={ig_id}")
    print(f"     IG_ACCESS_TOKEN=<тот же токен, что и FB_ACCESS_TOKEN>")

    if do_write:
        new = _set_env_key(lines, "IG_USER_ID", ig_id)
        new = _set_env_key(new, "IG_ACCESS_TOKEN", token)
        ENV_PATH.write_text("\n".join(new) + "\n", encoding="utf-8")
        print(f"\n💾 Записано в {ENV_PATH}: IG_USER_ID и IG_ACCESS_TOKEN.")
        print("   Проверка: python get_analytics.py account")
    else:
        print("\n   Запустите с --write, чтобы вписать это в .env автоматически.")


if __name__ == "__main__":
    run_cli(main)
