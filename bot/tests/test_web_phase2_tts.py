from unittest.mock import MagicMock

from jarvis.cogs import tts


async def test_synthesize_uses_voice(monkeypatch, tmp_path):
    captured = {}

    class FakeCommunicate:
        def __init__(self, text, voice):
            captured["text"] = text
            captured["voice"] = voice
        async def save(self, path):
            captured["path"] = path

    import sys
    sys.modules["edge_tts"] = MagicMock(Communicate=FakeCommunicate)
    dest = tmp_path / "o.mp3"
    await tts._synthesize("привет", dest, "en-US-GuyNeural")
    assert captured["voice"] == "en-US-GuyNeural"
    assert captured["text"] == "привет"


def test_tts_voices_shape():
    assert isinstance(tts.TTS_VOICES, list) and tts.TTS_VOICES
    v = tts.TTS_VOICES[0]
    assert "id" in v and "label" in v
