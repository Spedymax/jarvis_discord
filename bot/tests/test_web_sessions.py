from jarvis.web.auth import sign_session, verify_session


def test_roundtrip():
    tok = sign_session({"user_id": "42", "exp": 2000}, "secret", now=1000)
    assert verify_session(tok, "secret", now=1500) == {"user_id": "42", "exp": 2000}


def test_expired_rejected():
    tok = sign_session({"user_id": "42", "exp": 2000}, "secret", now=1000)
    assert verify_session(tok, "secret", now=2001) is None


def test_tampered_rejected():
    tok = sign_session({"user_id": "42", "exp": 2000}, "secret", now=1000)
    tampered = tok[:-2] + ("aa" if tok[-2:] != "aa" else "bb")
    assert verify_session(tampered, "secret", now=1500) is None


def test_wrong_secret_rejected():
    tok = sign_session({"user_id": "42", "exp": 2000}, "secret", now=1000)
    assert verify_session(tok, "other", now=1500) is None


def test_garbage_rejected():
    assert verify_session("not-a-token", "secret", now=1500) is None
    assert verify_session("", "secret", now=1500) is None
