import importlib
import sys


def _fresh_base(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MILA_FOLDER", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    sys.modules.pop("base", None)
    return importlib.import_module("base")


def test_safe_path_rejects_parent_escape(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path)

    try:
        base._safe_path("../outside.txt")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal should be rejected")


def test_safe_path_keeps_alias_inside_workspace(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path)

    path = base._safe_path("content/posts/draft.txt")

    assert path == tmp_path / "MILA-BUSINESS" / "02-content" / "posts" / "draft.txt"


def test_run_command_blocks_arbitrary_shell(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path)

    result = base.run_command("powershell Get-ChildItem")

    assert "not allowed" in result or "не разреш" in result
