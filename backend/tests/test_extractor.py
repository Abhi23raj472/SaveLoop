from app import extractor, tokens

IG_INFO = {
    "id": "C8xYz12AbCd",
    "uploader_id": "sample_creator",
    "duration": 24.3,
    "width": 1080,
    "height": 1920,
    "http_headers": {"User-Agent": "UA", "Cookie": "secret=1"},
    "thumbnails": [
        {"url": "https://scontent.cdninstagram.com/small.jpg", "width": 320, "height": 568},
        {"url": "https://scontent.cdninstagram.com/big.jpg", "width": 1080, "height": 1920},
        {"url": "https://evil.com/huge.jpg", "width": 4000, "height": 4000},
    ],
    "formats": [
        {"format_id": "p720", "url": "https://scontent.cdninstagram.com/720.mp4", "protocol": "https",
         "width": 720, "height": 1280, "vcodec": "avc1", "acodec": "mp4a", "tbr": 1500},
        {"format_id": "v1080", "url": "https://scontent.cdninstagram.com/1080v.mp4", "protocol": "https",
         "width": 1080, "height": 1920, "vcodec": "avc1", "acodec": "none", "tbr": 4000},
        {"format_id": "v480", "url": "https://scontent.cdninstagram.com/480v.mp4", "protocol": "https",
         "width": 480, "height": 854, "vcodec": "avc1", "acodec": "none", "tbr": 800},
        {"format_id": "a", "url": "https://scontent.cdninstagram.com/a.m4a", "protocol": "https",
         "vcodec": "none", "acodec": "mp4a", "abr": 128},
        {"format_id": "hls", "url": "https://scontent.cdninstagram.com/x.m3u8", "protocol": "m3u8_native",
         "width": 1080, "height": 1920, "vcodec": "avc1", "acodec": "mp4a"},
        {"format_id": "bad", "url": "https://evil.com/1080.mp4", "protocol": "https",
         "width": 1080, "height": 1920, "vcodec": "avc1", "acodec": "mp4a"},
    ],
}


def _payload(fmt):
    return tokens.verify(fmt["url"].split("/api/download/")[1].split("?")[0])


def test_builds_qualities_gif_and_images(monkeypatch):
    monkeypatch.setattr(extractor, "has_ffmpeg", lambda: True)
    res = extractor.build_result(IG_INFO, "instagram")
    assert res["creator"] == "@sample_creator"
    assert res["platform"] == "instagram"
    by_id = {f["id"]: f for f in res["formats"]}
    assert [f["quality"] for f in res["formats"] if f["type"] == "video"] == ["1080p", "720p", "480p"]

    p1080 = _payload(by_id["v1080"])
    assert p1080["m"] == "mux"
    assert p1080["u"] == ["https://scontent.cdninstagram.com/1080v.mp4", "https://scontent.cdninstagram.com/a.m4a"]
    assert "Cookie" not in p1080["h"]

    p720 = _payload(by_id["v720"])
    assert p720["m"] == "direct" and p720["u"] == ["https://scontent.cdninstagram.com/720.mp4"]

    assert _payload(by_id["gif"])["u"] == ["https://scontent.cdninstagram.com/480v.mp4"]
    assert _payload(by_id["png"])["u"] == ["https://scontent.cdninstagram.com/big.jpg"]
    assert res["thumbnail"].endswith("?inline=1")


def test_never_uses_untrusted_hosts(monkeypatch):
    monkeypatch.setattr(extractor, "has_ffmpeg", lambda: True)
    res = extractor.build_result(IG_INFO, "instagram")
    for f in res["formats"]:
        for u in _payload(f)["u"]:
            assert "evil.com" not in u and ".m3u8" not in u


def test_image_only_post(monkeypatch):
    monkeypatch.setattr(extractor, "has_ffmpeg", lambda: True)
    info = {"id": "1", "thumbnails": [{"url": "https://pbs.twimg.com/media/a.jpg", "width": 1200, "height": 800}]}
    res = extractor.build_result(info, "x")
    assert res["kind"] == "Image"
    assert {f["id"] for f in res["formats"]} == {"webp", "png"}


def test_error_mapping():
    assert extractor.map_ytdlp_error("ERROR: This content is private").code == "private"
    assert extractor.map_ytdlp_error("ERROR: login required").code == "private"
    assert extractor.map_ytdlp_error("HTTP Error 404: Not Found").code == "not_found"
    assert extractor.map_ytdlp_error("ERROR: Unsupported URL: x").code == "unsupported_platform"
    assert extractor.map_ytdlp_error("something odd").code == "extraction_failed"


def test_without_ffmpeg_only_ready_made_files(monkeypatch):
    monkeypatch.setattr(extractor, "has_ffmpeg", lambda: False)
    res = extractor.build_result(IG_INFO, "instagram")
    ids = [f["id"] for f in res["formats"]]
    assert ids == ["v720", "jpg"]
    assert _payload(res["formats"][0])["m"] == "direct"


def test_photo_only_post_maps_to_no_video():
    err = extractor.map_ytdlp_error("ERROR: [twitter] 123: Media #1 is not a video")
    assert err.code == "no_video" and err.status == 422


X_GIF_INFO = {
    "id": "2122936075857666221",
    "uploader_id": "gavin",
    "thumbnails": [{"url": "https://pbs.twimg.com/tweet_video_thumb/abc.jpg", "width": 498, "height": 280}],
    "formats": [
        {"format_id": "http", "url": "https://video.twimg.com/tweet_video/abc.mp4", "protocol": "https", "ext": "mp4"},
    ],
}


def test_x_gif_post_leads_with_gif(monkeypatch):
    monkeypatch.setattr(extractor, "has_ffmpeg", lambda: True)
    res = extractor.build_result(X_GIF_INFO, "x")
    assert res["kind"] == "GIF" and res["primary"] == "gif"
    assert res["formats"][0]["type"] == "gif"
    assert any(f["type"] == "video" for f in res["formats"])
    assert _payload(res["formats"][0])["u"] == ["https://video.twimg.com/tweet_video/abc.mp4"]


def test_unknown_codec_x_video_is_a_video(monkeypatch):
    monkeypatch.setattr(extractor, "has_ffmpeg", lambda: True)
    info = {"id": "1", "formats": [{"format_id": "http-2176", "protocol": "https", "ext": "mp4",
            "url": "https://video.twimg.com/ext_tw_video/1/pu/vid/720x1280/a.mp4", "width": 720, "height": 1280}]}
    res = extractor.build_result(info, "x")
    assert res["kind"] == "Post" and res["formats"][0]["quality"] == "720p"
    assert _payload(res["formats"][0])["m"] == "direct"
