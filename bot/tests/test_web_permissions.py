from jarvis.web.permissions import Level, resolve_level


def test_owner_is_admin():
    assert resolve_level(owner=True, permissions=0) is Level.ADMIN


def test_manage_guild_is_admin():
    assert resolve_level(owner=False, permissions=0x20) is Level.ADMIN


def test_plain_member_is_viewer():
    assert resolve_level(owner=False, permissions=0) is Level.VIEWER


def test_role_map_grants_dj():
    lvl = resolve_level(
        owner=False, permissions=0,
        member_role_ids=[10, 20], role_perm_map={20: "dj"},
    )
    assert lvl is Level.DJ


def test_highest_role_wins():
    lvl = resolve_level(
        owner=False, permissions=0,
        member_role_ids=[10, 20], role_perm_map={10: "dj", 20: "admin"},
    )
    assert lvl is Level.ADMIN


def test_level_str_roundtrip():
    assert Level.from_str("dj") is Level.DJ
    assert Level.DJ.to_str() == "dj"
    assert Level.from_str("garbage") is Level.VIEWER
