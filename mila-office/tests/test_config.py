"""Тесты загрузчика конфигурации base.py.

Проверяют две вещи, которые ломались в реальном .env:
  1. legacy-имена ключей резолвятся в канонические (ANTHROPIC_KEY → ANTHROPIC_KEY,
     TELEGRAM_API → TELEGRAM_TOKEN, GUMROAD_TOKEN → GUMROAD_TOKEN);
  2. канонические имена имеют приоритет над legacy;
  3. require_config("ANTHROPIC_API_KEY") падает с понятной ошибкой, если ключа нет.

base.py читает env в module-level константы на import и собирает _CONFIG, поэтому
каждый тест импортирует base заново в изолированном окружении.
"""
import importlib
import sys

import pytest

# Все имена, которые base.py читает — чистим перед каждым сценарием.
_ALL_KEYS = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_KEY",
    "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_API",
    "GUMROAD_ACCESS_TOKEN", "GUMROAD_TOKEN",
    "IG_ACCESS_TOKEN", "INSTAGRAM_ACCESS_TOKEN",
    "IG_USER_ID", "INSTAGRAM_BUSINESS_ACCOUNT_ID",
)


def _fresh_base(monkeypatch, tmp_path, env):
    """Импортирует base.py заново с полностью контролируемым окружением.

    MILA_FOLDER + chdir на пустую tmp-папку → реальные .env не подхватываются.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MILA_FOLDER", str(tmp_path))
    for k in _ALL_KEYS:
        monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    sys.modules.pop("base", None)
    return importlib.import_module("base")


def test_legacy_aliases_resolve(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path, {
        "ANTHROPIC_KEY": "legacy-anthropic",
        "TELEGRAM_API": "legacy-telegram",
        "GUMROAD_TOKEN": "legacy-gumroad",
    })
    assert base.ANTHROPIC_KEY == "legacy-anthropic"
    assert base.TELEGRAM_TOKEN == "legacy-telegram"
    assert base.GUMROAD_TOKEN == "legacy-gumroad"
    assert base._CONFIG["ANTHROPIC_API_KEY"] == "legacy-anthropic"


def test_canonical_takes_precedence(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path, {
        "ANTHROPIC_API_KEY": "canonical",
        "ANTHROPIC_KEY": "legacy",
    })
    assert base.ANTHROPIC_KEY == "canonical"


def _capture_client(monkeypatch, base):
    """Подменяет anthropic.Anthropic — ловит kwargs, не делает сетевых вызовов."""
    captured = {}
    monkeypatch.setattr(base.anthropic, "Anthropic",
                        lambda **kw: captured.update(kw) or "client")
    return captured


def test_get_client_uses_api_key_by_default(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path, {"ANTHROPIC_API_KEY": "k-123"})
    cap = _capture_client(monkeypatch, base)
    base.get_client()
    assert cap.get("api_key") == "k-123"
    assert "auth_token" not in cap


def test_get_client_uses_auth_token_when_set(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path, {"ANTHROPIC_AUTH_TOKEN": "bearer-xyz"})
    cap = _capture_client(monkeypatch, base)
    base.get_client()
    assert cap.get("auth_token") == "bearer-xyz"
    assert "api_key" not in cap   # bearer-путь не требует ключа


def test_get_client_passes_base_url(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path, {
        "ANTHROPIC_API_KEY": "k", "ANTHROPIC_BASE_URL": "https://gw.example"})
    cap = _capture_client(monkeypatch, base)
    base.get_client()
    assert cap.get("base_url") == "https://gw.example"


def test_require_config_fails_when_missing(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path, {})  # никаких ключей
    with pytest.raises(SystemExit):
        base.require_config("ANTHROPIC_API_KEY")


def test_require_config_passes_when_present(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path, {"ANTHROPIC_API_KEY": "ok"})
    base.require_config("ANTHROPIC_API_KEY")  # не должно бросать
