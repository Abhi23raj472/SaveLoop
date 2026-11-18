import pytest

from app import errors
from app.security import is_allowed_media_url, validate_post_url


@pytest.mark.parametrize("url,platform", [
    ("https://www.instagram.com/reel/C8xYz12AbCd/", "instagram"),
    ("instagram.com/p/abc", "instagram"),
    ("https://m.facebook.com/watch/?v=123", "facebook"),
    ("https://fb.watch/abcd/", "facebook"),
    ("https://x.com/user/status/123", "x"),
    ("http://twitter.com/user/status/123", "x"),
])
def test_accepts_platform_links(url, platform):
    normalized, got = validate_post_url(url)
    assert got == platform
    assert normalized.startswith("https://")


@pytest.mark.parametrize("url,code", [
    ("", "invalid_url"),
    ("not a url", "invalid_url"),
    ("ftp://instagram.com/p/abc", "invalid_url"),
    ("https://user:pass@instagram.com/p/abc", "invalid_url"),
    ("https://instagram.com:8080/p/abc", "invalid_url"),
    ("https://example.com/video", "unsupported_platform"),
    ("https://instagram.com.evil.com/p/abc", "unsupported_platform"),
    ("https://evilinstagram.com/p/abc", "unsupported_platform"),
    ("https://127.0.0.1/admin", "unsupported_platform"),
    ("https://[::1]/admin", "unsupported_platform"),
    ("https://169.254.169.254/latest/meta-data", "unsupported_platform"),
    ("https://x.com/" + "a" * 3000, "invalid_url"),
])
def test_rejects_bad_links(url, code):
    with pytest.raises(errors.ApiError) as exc:
        validate_post_url(url)
    assert exc.value.code == code


@pytest.mark.parametrize("url,ok", [
    ("https://scontent.cdninstagram.com/v/t50/video.mp4?x=1", True),
    ("https://video.xx.fbcdn.net/v/video.mp4", True),
    ("https://video.twimg.com/ext_tw_video/1/vid/720x1280/a.mp4", True),
    ("http://video.twimg.com/a.mp4", False),
    ("https://evil.com/a.mp4", False),
    ("https://twimg.com.evil.com/a.mp4", False),
    ("https://10.0.0.1/a.mp4", False),
    ("https://video.twimg.com:8443/a.mp4", False),
])
def test_media_host_allowlist(url, ok):
    assert is_allowed_media_url(url) is ok


@pytest.mark.parametrize("url", [
    "https://x.com/user/status/2122936075857666221/photo/1",
    "https://x.com/user/status/2122936075857666221/video/1/",
    "https://twitter.com/user/status/2122936075857666221",
])
def test_x_media_suffix_is_dropped(url):
    normalized, _ = validate_post_url(url)
    assert normalized.rstrip("/").endswith("/status/2122936075857666221")
