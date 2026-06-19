from jarvis.db import Sound
from jarvis.web.serializers import sound_view


def test_sound_view():
    s = Sound(id=7, guild_id=1, name="airhorn", file_path="/x.mp3",
              length_ms=3000, owner_id=9, created_at=0, play_count=12, volume=80)
    assert sound_view(s) == {
        "id": 7, "name": "airhorn", "length_ms": 3000, "volume": 80, "play_count": 12,
    }
