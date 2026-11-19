import json
from types import SimpleNamespace

from app import llm
from app.candidates import Candidate
from app.config import Settings

CANDS = [Candidate(10, 40, 0.9), Candidate(100, 130, 0.8), Candidate(200, 230, 0.7)]


def settings(enabled=True):
    return Settings("http://x/v1" if enabled else None, "k" if enabled else None,
                    "m" if enabled else None, None)


def fake_client(content=None, exc=None):
    class C:
        def __init__(self, **kw):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

        def create(self, **kw):
            if exc:
                raise exc
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])
    return C


def test_rank_without_llm_returns_signal_order():
    out = llm.rank_candidates(CANDS, {}, "", settings(False))
    assert [r.candidate for r in out] == CANDS
    assert all(r.title for r in out) and out[0].llm_score is None


def test_rank_with_valid_json_reorders_and_titles(monkeypatch):
    content = "Sure:\n" + json.dumps([
        {"index": 1, "score": 4, "title": "A", "hook": "ha"},
        {"index": 3, "score": 9, "title": "C", "hook": "hc"},
        {"index": 2, "score": 6, "title": "B", "hook": "hb"}])
    monkeypatch.setattr(llm, "OpenAI", fake_client(content))
    out = llm.rank_candidates(CANDS, {0: "t"}, "clutches", settings())
    assert [r.title for r in out] == ["C", "B", "A"]
    assert out[0].llm_score == 9


def test_rank_invalid_json_falls_back(monkeypatch):
    monkeypatch.setattr(llm, "OpenAI", fake_client("not json at all"))
    out = llm.rank_candidates(CANDS, {}, "", settings())
    assert [r.candidate for r in out] == CANDS


def test_rank_client_exception_falls_back(monkeypatch):
    monkeypatch.setattr(llm, "OpenAI", fake_client(exc=TimeoutError("slow")))
    out = llm.rank_candidates(CANDS, {}, "", settings())
    assert [r.candidate for r in out] == CANDS
