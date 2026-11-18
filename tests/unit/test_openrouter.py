"""The OpenRouter helpers shared by the judge-model and temperature experiments."""
import importlib.util
import sys
from pathlib import Path

import pytest

EXPERIMENTS = Path(__file__).resolve().parents[2] / "experiments"
sys.path.insert(0, str(EXPERIMENTS))
from common import openrouter


class Reply:
    def __init__(self, status=200, content="an answer", text=""):
        self.status_code, self._content, self.text = status, content, text

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_chat_returns_the_answer_and_sends_the_settings(monkeypatch):
    made = []
    monkeypatch.setattr(openrouter.requests, "post", lambda url, headers=None, json=None, timeout=None: made.append((json, timeout, headers)) or Reply())
    monkeypatch.setattr(openrouter, "load_key", lambda: "test-key")
    out = openrouter.chat("some/model", [{"role": "user", "content": "hi"}], temperature=0.7, max_tokens=64, timeout=30)
    assert out == "an answer"
    payload, timeout, headers = made[0]
    assert payload == {"model": "some/model", "messages": [{"role": "user", "content": "hi"}], "temperature": 0.7, "max_tokens": 64}
    assert timeout == 30 and headers["Authorization"] == "Bearer test-key"


def test_chat_retries_then_reports_an_error(monkeypatch):
    replies = [Reply(status=500, text="server error"), ConnectionError("no route"), Reply(content=None), Reply(status=429, text="slow down")]
    seen = []

    def post(url, headers=None, json=None, timeout=None):
        seen.append(1)
        reply = replies[len(seen) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(openrouter.requests, "post", post)
    monkeypatch.setattr(openrouter.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(openrouter, "load_key", lambda: "test-key")
    out = openrouter.chat("some/model", [], retries=4)
    assert len(seen) == 4
    assert out.startswith(openrouter.ERROR_PREFIX) and "429" in out


def test_chat_succeeds_after_a_failed_attempt(monkeypatch):
    replies = [Reply(status=502), Reply(content="second try")]
    monkeypatch.setattr(openrouter.requests, "post", lambda url, headers=None, json=None, timeout=None: replies.pop(0))
    monkeypatch.setattr(openrouter.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(openrouter, "load_key", lambda: "test-key")
    assert openrouter.chat("some/model", []) == "second try"


@pytest.mark.parametrize("text, rating", [
    ("Good answer. Rating: [[7]]", 7.0), ("[[ 8.5 ]]", 8.5), ("rating: 3", 3.0), ("Rating 10", 10.0),
    ("[[11]]", None), ("[[0]]", None), ("no number here", None),
])
def test_parse_rating(text, rating):
    assert openrouter.parse_rating(text) == rating


def test_jsonl_round_trip(tmp_path):
    path = tmp_path / "runs.jsonl"
    assert openrouter.read_jsonl(path) == []
    openrouter.append_jsonl(path, {"a": 1})
    openrouter.append_jsonl(path, {"b": "ü"})
    assert openrouter.read_jsonl(path) == [{"a": 1}, {"b": "ü"}]


def test_key_comes_from_the_environment_when_there_is_no_env_file(monkeypatch, tmp_path):
    monkeypatch.setattr(openrouter, "REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "from-env")
    assert openrouter.load_key() == "from-env"
    (tmp_path / ".env").write_text('OPENROUTER_API_KEY="from-file"\n', encoding="utf-8")
    assert openrouter.load_key() == "from-file"


@pytest.mark.parametrize("script, call, expected", [
    ("judge_sensitivity/run_judge_sensitivity.py", lambda m: m.chat("x/y", [{"role": "user", "content": "q"}], max_tokens=100),
     {"temperature": 0.0, "max_tokens": 100, "timeout": 120}),
    ("judge_sensitivity_extended/run_judge_sensitivity_extended.py", lambda m: m.chat("x/y", [{"role": "user", "content": "q"}], max_tokens=100),
     {"temperature": 0.0, "max_tokens": 100, "timeout": 120}),
    ("judge_sensitivity_vicuna/run_judge_vicuna.py", lambda m: m.chat("x/y", [{"role": "user", "content": "q"}]),
     {"temperature": 0.0, "max_tokens": 800, "timeout": 120}),
    ("temperature_panel/run_temperature_panel.py", lambda m: m.chat("x/y", "q", 0.7),
     {"temperature": 0.7, "max_tokens": 1024, "timeout": 150}),
])
def test_each_experiment_script_calls_the_model_with_its_own_settings(monkeypatch, script, call, expected):
    made = []
    monkeypatch.setattr(openrouter.requests, "post", lambda url, headers=None, json=None, timeout=None: made.append((json, timeout)) or Reply())
    monkeypatch.setattr(openrouter, "load_key", lambda: "test-key")
    spec = importlib.util.spec_from_file_location("experiment_script", EXPERIMENTS / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert call(module) == "an answer"
    payload, timeout = made[0]
    assert payload["messages"] == [{"role": "user", "content": "q"}]
    assert {"temperature": payload["temperature"], "max_tokens": payload["max_tokens"], "timeout": timeout} == expected
