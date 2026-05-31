import importlib
import sys


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


def _fresh_base(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MILA_FOLDER", str(tmp_path))
    monkeypatch.setenv("GEMINI_KEY", "gemini-test-key")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    sys.modules.pop("base", None)
    return importlib.import_module("base")


def test_gemini_runner_returns_text(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path)
    calls = []

    def fake_post(url, params, json, timeout):
        calls.append({"url": url, "params": params, "json": json, "timeout": timeout})
        return FakeResponse({
            "candidates": [{"content": {"parts": [{"text": "hello from gemini"}]}}]
        })

    monkeypatch.setattr(base.requests, "post", fake_post)
    reply, history = base.run_agent(None, "system", [], lambda *_: "", "hi", [], agent_key="marina")

    assert reply == "hello from gemini"
    assert history[-1] == {"role": "assistant", "content": "hello from gemini"}
    assert calls[0]["params"] == {"key": "gemini-test-key"}
    assert calls[0]["json"]["contents"][0]["role"] == "user"


def test_gemini_runner_executes_tool_call(monkeypatch, tmp_path):
    base = _fresh_base(monkeypatch, tmp_path)
    responses = [
        FakeResponse({
            "candidates": [{
                "content": {"parts": [{
                    "functionCall": {"name": "read_file", "args": {"path": "notes.txt"}}
                }]}
            }]
        }),
        FakeResponse({
            "candidates": [{"content": {"parts": [{"text": "tool result used"}]}}]
        }),
    ]
    payloads = []
    handled = []

    def fake_post(url, params, json, timeout):
        payloads.append(json)
        return responses.pop(0)

    def handle(name, args):
        handled.append((name, args))
        return "file contents"

    tools = [{
        "name": "read_file",
        "description": "Read a file",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": ""}},
            "required": ["path"],
        },
    }]

    monkeypatch.setattr(base.requests, "post", fake_post)
    reply, _ = base.run_agent(None, "system", tools, handle, "read it", [], agent_key="marina")

    assert reply == "tool result used"
    assert handled == [("read_file", {"path": "notes.txt"})]
    declaration = payloads[0]["tools"][0]["function_declarations"][0]
    assert declaration["name"] == "read_file"
    assert "default" not in declaration["parameters"]["properties"]["path"]
    assert payloads[1]["contents"][-1]["parts"][0]["functionResponse"]["response"] == {
        "result": "file contents"
    }
