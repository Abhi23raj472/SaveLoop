from app import config, downloads, extractor, main, tokens
from tests.test_extractor import IG_INFO


def test_extract_success(client, monkeypatch):
    monkeypatch.setattr(extractor, "fetch_info", lambda url: IG_INFO)
    r = client.post("/api/extract", json={"url": "https://www.instagram.com/reel/C8xYz12AbCd/"})
    assert r.status_code == 200
    body = r.json()
    assert body["formats"][0]["url"].startswith("/api/download/")


def test_extract_rejects_bad_urls(client):
    r = client.post("/api/extract", json={"url": "https://example.com/v"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_platform"
    r = client.post("/api/extract", json={})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_url"


def test_extract_maps_errors(client, monkeypatch):
    def boom(url):
        raise extractor.map_ytdlp_error("This account is private")
    monkeypatch.setattr(extractor, "fetch_info", boom)
    r = client.post("/api/extract", json={"url": "https://instagram.com/p/x"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "private"


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(extractor, "fetch_info", lambda url: IG_INFO)
    codes = [client.post("/api/extract", json={"url": "https://x.com/a/status/1"}).status_code
             for _ in range(config.EXTRACT_PER_MINUTE + 1)]
    assert codes[-1] == 429 and all(c == 200 for c in codes[:-1])


def test_download_bad_token(client):
    r = client.get("/api/download/nope")
    assert r.status_code == 410 and r.json()["error"]["code"] == "link_expired"


def test_download_refuses_untrusted_host_even_if_signed(client):
    t = tokens.sign({"m": "direct", "u": ["https://evil.com/a.mp4"]})
    r = client.get(f"/api/download/{t}")
    assert r.status_code == 400


def test_ffmpeg_commands():
    gif = downloads.build_ffmpeg_cmd({"m": "gif", "u": ["https://video.twimg.com/a.mp4"], "h": {"User-Agent": "UA"}})
    assert "-protocol_whitelist" in gif and "gif" in gif and "pipe:1" in gif
    mux = downloads.build_ffmpeg_cmd({"m": "mux", "u": ["https://a.fbcdn.net/v.mp4", "https://a.fbcdn.net/a.m4a"]})
    assert mux.count("-i") == 2 and "1:a:0" in mux


def test_serves_frontend_with_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200 and "SaveLoop" in r.text
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert client.get("/static/js/app.js").status_code == 200


def test_ffmpeg_stream_end_to_end(client, monkeypatch, tmp_path):
    import shutil
    import subprocess
    if not shutil.which("ffmpeg"):
        return
    src = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10",
                    "-t", "1", "-pix_fmt", "yuv420p", str(src)], check=True)
    monkeypatch.setattr(downloads, "build_ffmpeg_cmd", lambda p: [
        "ffmpeg", "-loglevel", "error", "-i", str(src), "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "pipe:1"])
    t = tokens.sign({"m": "png", "u": ["https://pbs.twimg.com/a.jpg"], "n": "x.png", "t": "image/png"})
    r = client.get(f"/api/download/{t}")
    assert r.status_code == 200 and r.content[:4] == b"\x89PNG"
    assert 'filename="x.png"' in r.headers["content-disposition"]


def test_ffmpeg_failure_returns_json(client, monkeypatch):
    monkeypatch.setattr(downloads, "build_ffmpeg_cmd", lambda p: ["ffmpeg", "-loglevel", "error", "-i", "/nope.mp4", "-f", "null", "-"])
    t = tokens.sign({"m": "png", "u": ["https://pbs.twimg.com/a.jpg"]})
    r = client.get(f"/api/download/{t}")
    assert r.status_code == 502 and r.json()["error"]["code"] == "extraction_failed"


def test_missing_ffmpeg_is_reported(client, monkeypatch):
    monkeypatch.setattr(downloads, "build_ffmpeg_cmd", lambda p: ["definitely-not-ffmpeg"])
    t = tokens.sign({"m": "gif", "u": ["https://pbs.twimg.com/a.jpg"]})
    r = client.get(f"/api/download/{t}")
    assert r.status_code == 500 and "FFmpeg" in r.json()["error"]["message"]
