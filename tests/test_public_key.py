import httpx
import pytest

from app.public_key import (
    MAX_PUBLIC_KEY_PAGE_BYTES, PUBLIC_KEY_URL, PublicKeyError,
    fetch_public_key, parse_public_key,
)

TOKEN = "c3ludGhldGljLXJlZ3Jlc3Npb24ta2V5=="


@pytest.mark.parametrize("html", [
    f"<pre>Authorization: APIKey {TOKEN}</pre>",
    f"<pre><span>Authorization</span><span>:</span> <span>APIKey</span> <span>{TOKEN}</span></pre>",
    f"<p>Authorization: APIKey [Chave Pública]</p><pre>Authorization: APIKey {TOKEN}</pre>",
    f"<pre>Authorization:&#32;APIKey&#160;{TOKEN.replace('=', '&#61;')}</pre>",
    f"<pre>Authorization: APIKey {TOKEN[:12]}<span>{TOKEN[12:]}</span></pre>",
    f"<pre>Authorization: APIKey {TOKEN}</pre><pre>Authorization: APIKey {TOKEN}</pre>",
    f"<script>Authorization: APIKey fake-script-key</script><style>Authorization: APIKey fake-style-key</style><pre>Authorization: APIKey {TOKEN}</pre>",
])
def test_parser_handles_documented_placeholder_entities_and_inline_spans(html):
    assert parse_public_key(html) == TOKEN


@pytest.mark.parametrize("html,code", [
    ("<p>Missing key</p>", "public_key_not_found"),
    ("Authorization: APIKey [Chave Pública]", "public_key_not_found"),
    ("<script>Authorization: APIKey fake-key</script>", "public_key_not_found"),
    ("<!-- Authorization: APIKey fake-key -->", "public_key_not_found"),
    ("<pre>Authorization: APIKey first-key</pre><pre>Authorization: APIKey second-key</pre>", "public_key_ambiguous"),
    ("Authorization: APIKey abc#truncated", "public_key_invalid_response"),
    ("Authorization: APIKey", "public_key_invalid_response"),
    ("Authorization: APIKey " + "a" * 4097, "public_key_invalid_response"),
])
def test_missing_ambiguous_or_invalid_key_is_explicit_and_safe(html, code):
    with pytest.raises(PublicKeyError) as caught:
        parse_public_key(html)
    assert caught.value.code == code
    assert html not in str(caught.value)
    assert "first-key" not in str(caught.value)


def test_get_is_fixed_https_without_authorization_even_if_client_has_default():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=f"<pre>Authorization: APIKey {TOKEN}</pre>")
    with httpx.Client(headers={"Authorization": "APIKey must-not-send", "Proxy-Authorization": "must-not-send"}, transport=httpx.MockTransport(handler)) as client:
        assert fetch_public_key(client, max_retries=0) == TOKEN
    assert len(requests) == 1 and str(requests[0].url) == PUBLIC_KEY_URL
    assert requests[0].method == "GET"
    assert "Authorization" not in requests[0].headers
    assert "Proxy-Authorization" not in requests[0].headers
    assert requests[0].headers["Accept-Encoding"] == "identity"
    assert requests[0].headers["Cache-Control"] == "no-cache"


@pytest.mark.parametrize("status,retries,code", [
    (301, 0, "public_key_redirect"), (302, 0, "public_key_redirect"),
    (307, 0, "public_key_redirect"), (401, 0, "public_key_http_error"),
    (404, 0, "public_key_http_error"), (500, 0, "public_key_http_error"),
    (429, 2, "public_key_http_error"), (503, 2, "public_key_http_error"),
])
def test_http_failures_are_bounded_and_do_not_follow_redirects(status, retries, code, monkeypatch):
    requests, sleeps = [], []
    monkeypatch.setattr("app.public_key.time.sleep", sleeps.append)
    def handler(request):
        requests.append(request)
        return httpx.Response(status, text="do-not-log-body", headers={"Location": "https://example.invalid/", "Retry-After": "999999"})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PublicKeyError) as caught:
            fetch_public_key(client, max_retries=2)
    assert caught.value.code == code and caught.value.upstream_status == status
    assert len(requests) == retries + 1 and len(sleeps) == retries
    assert all(delay <= 2 for delay in sleeps)
    assert "do-not-log-body" not in str(caught.value)


@pytest.mark.parametrize("error,code,status", [
    (httpx.ReadTimeout, "public_key_timeout", 504),
    (httpx.ConnectError, "public_key_connection_error", 503),
])
def test_transport_failure_has_safe_message_and_limited_retries(error, code, status, monkeypatch):
    calls = []
    monkeypatch.setattr("app.public_key.time.sleep", lambda delay: None)
    def handler(request):
        calls.append(request)
        raise error("do-not-log-key", request=request)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(PublicKeyError) as caught:
            fetch_public_key(client, max_retries=1)
    assert len(calls) == 2
    assert caught.value.code == code and caught.value.status_code == status
    assert "do-not-log-key" not in str(caught.value)


class CountedStream(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.read = 0
        self.closed = False

    def __iter__(self):
        for chunk in self.chunks:
            self.read += 1
            yield chunk

    def close(self):
        self.closed = True


def test_streaming_stops_at_limit_and_closes_without_reading_all():
    stream = CountedStream([b"x" * 8192] * 100)
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream))) as client:
        with pytest.raises(PublicKeyError) as caught:
            fetch_public_key(client, max_retries=0)
    assert caught.value.code == "public_key_response_too_large"
    assert stream.closed and stream.read <= MAX_PUBLIC_KEY_PAGE_BYTES // 8192 + 1


def test_large_content_length_is_rejected_before_reading_stream():
    stream = CountedStream([b"not-read"])
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream, headers={"Content-Length": str(MAX_PUBLIC_KEY_PAGE_BYTES + 1)}))) as client:
        with pytest.raises(PublicKeyError, match="256 KiB"):
            fetch_public_key(client, max_retries=0)
    assert stream.read == 0 and stream.closed


def test_compressed_response_cannot_bypass_stream_limit():
    stream = CountedStream([b"not-read"])
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=stream, headers={"Content-Encoding": "gzip"}))) as client:
        with pytest.raises(PublicKeyError) as caught:
            fetch_public_key(client, max_retries=0)
    assert caught.value.code == "public_key_invalid_response"
    assert stream.read == 0 and stream.closed


def test_stream_timeout_retries_then_parses_complete_page(monkeypatch):
    class InterruptedStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"<pre>Authorization: APIKey partial-"
            raise httpx.ReadTimeout("do-not-log")
    calls = []
    monkeypatch.setattr("app.public_key.time.sleep", lambda delay: None)
    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, stream=InterruptedStream())
        return httpx.Response(200, text=f"Authorization: APIKey {TOKEN}")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert fetch_public_key(client, max_retries=1) == TOKEN
    assert len(calls) == 2
