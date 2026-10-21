import http.client

from laf import usgs


class _Resp:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self.body


def test_download_retries_a_truncated_body(monkeypatch):
    calls = []

    def urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise http.client.IncompleteRead(b"partial")
        return _Resp(b"complete")

    monkeypatch.setattr(usgs.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(usgs.time, "sleep", lambda s: None)
    assert usgs.download("https://example.invalid/x") == b"complete"
    assert len(calls) == 2


def test_manifest_has_lf_line_endings_on_every_platform(tmp_path):
    usgs.store(tmp_path, "raw/x.json", b"{}", "https://example.invalid/x", licence="données")
    usgs.store(tmp_path, "raw/y.json", b"{}", "https://example.invalid/y", licence="données")
    raw = (tmp_path / "manifest.jsonl").read_bytes()
    assert b"\r" not in raw
    assert raw.count(b"\n") == 2
    assert [e["licence"] for e in usgs.load_manifest(tmp_path)] == ["données", "données"]
