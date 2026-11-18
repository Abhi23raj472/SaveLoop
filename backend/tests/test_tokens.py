from app import tokens


def test_round_trip():
    t = tokens.sign({"m": "direct", "u": ["https://video.twimg.com/a.mp4"]})
    body = tokens.verify(t)
    assert body["m"] == "direct"


def test_rejects_tampering():
    t = tokens.sign({"m": "direct", "u": ["https://video.twimg.com/a.mp4"]})
    raw, sig = t.split(".")
    forged = tokens._b64(b'{"exp":9999999999,"m":"direct","u":["https://evil.com"]}')
    assert tokens.verify(f"{forged}.{sig}") is None
    assert tokens.verify("garbage") is None


def test_expiry():
    t = tokens.sign({"m": "direct"}, ttl=10, now=1000)
    assert tokens.verify(t, now=1005) is not None
    assert tokens.verify(t, now=1011) is None
