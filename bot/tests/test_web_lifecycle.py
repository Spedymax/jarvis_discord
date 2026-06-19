from unittest.mock import MagicMock

from jarvis.__main__ import _maybe_start_dashboard


async def test_disabled_returns_none():
    s = MagicMock()
    s.dashboard_enabled = False
    runner = await _maybe_start_dashboard(MagicMock(), s, started_at=0)
    assert runner is None


async def test_enabled_starts(monkeypatch):
    started = {}

    async def fake_start(bot, settings, *, started_at):
        started["called"] = True
        return "RUNNER"

    monkeypatch.setattr("jarvis.web.server.start_dashboard", fake_start)
    s = MagicMock()
    s.dashboard_enabled = True
    runner = await _maybe_start_dashboard(MagicMock(), s, started_at=0)
    assert runner == "RUNNER"
    assert started["called"] is True
