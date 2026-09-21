"""Independent authentication review: only synthetic keys and mock transports."""

import base64
import json
import logging
import traceback

from fastapi.testclient import TestClient
import httpx
import pytest
from typer.testing import CliRunner

from app.cli import app as cli_app
from app.config import Settings
from app.core import DataJudService, error_document
from app.datajud import DataJudClient, DataJudError
from app.main import create_app
from app.models import DiscoverRequest, SearchRequest
from app.storage import Storage


WIKI = "https://datajud-wiki.cnj.jus.br/api-publica/acesso/"
API = "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search"
KEY_A = base64.b64encode(b"independent-review-a:synthetic-key-a").decode()
KEY_B = base64.b64encode(b"independent-review-b:synthetic-key-b").decode()
STALE_KEY = "obsolete-environment-key-never-use-in-auto"
HTML_MARKER = "PRIVATE-HTML-MARKER-NOT-TO-PERSIST"


def _html(key):
    return (
        "<html><body><p>Inclua Authorization: APIKey [Chave Pública]</p>"
        f"<pre><code>Authorization: <span>APIKey</span> <span>{key}</span></code></pre>"
        "</body></html>"
    )


def _page(identity="1"):
    return {
        "timed_out": False,
        "_shards": {"failed": 0},
        "hits": {
            "total": {"value": 2, "relation": "eq"},
            "hits": [{
                "_id": identity, "_index": "synthetic-tjsp", "sort": [int(identity)],
                "_source": {"tribunal": "TJSP", "grau": "G1", "classe": {"codigo": 386, "nome": "Revisão"}},
            }],
        },
    }


@pytest.fixture(autouse=True)
def _forbid_real_network(monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Independent authentication tests must never use real network.")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr("app.datajud.time.sleep", lambda _: None)
    monkeypatch.setattr("app.discover.time.sleep", lambda _: None)


def _settings(tmp_path, **options):
    return Settings(data_dir=tmp_path / "evidence", max_retries=options.pop("max_retries", 0), **options)


def _rotating_transport():
    events = []
    current_key = None
    gets = 0

    def handler(request):
        nonlocal current_key, gets
        events.append((request.method, str(request.url), request.headers.get("Authorization")))
        if request.method == "GET":
            assert str(request.url) == WIKI
            assert "Authorization" not in request.headers
            gets += 1
            current_key = KEY_A if gets % 2 else KEY_B
            return httpx.Response(200, text=_html(current_key), headers={"Content-Type": "text/html"})
        assert request.method == "POST" and str(request.url) == API
        assert request.headers["Authorization"] == f"APIKey {current_key}"
        return httpx.Response(200, json=_page(str(gets)))

    return httpx.MockTransport(handler), events


def test_same_client_resolves_current_key_again_and_never_reuses_environment_key(tmp_path):
    transport, events = _rotating_transport()
    settings = _settings(tmp_path, api_key=STALE_KEY)
    assert settings.auth_mode == "auto"
    with DataJudClient(settings, transport=transport) as client:
        first = client.search("TJSP", {"size": 1})
        second = client.search("TJSP", {"size": 1})
        assert "Authorization" not in client._client.headers
    assert [event[0] for event in events] == ["GET", "POST", "GET", "POST"]
    assert [events[1][2], events[3][2]] == [f"APIKey {KEY_A}", f"APIKey {KEY_B}"]
    assert first.payload["hits"]["hits"][0]["_id"] != second.payload["hits"]["hits"][0]["_id"]


def test_two_http_requests_with_persistent_service_each_fetch_the_current_key(tmp_path):
    transport, events = _rotating_transport()
    settings = _settings(tmp_path, api_key=STALE_KEY)
    with DataJudClient(settings, transport=transport) as upstream:
        service = DataJudService(settings, upstream)
        with TestClient(create_app(service=service)) as http:
            first = http.post("/search", json={"tribunal": "TJSP", "size": 1})
            second = http.post("/search", json={"tribunal": "TJSP", "size": 1})
    assert first.status_code == second.status_code == 200
    assert first.json()["raw_path"] != second.json()["raw_path"]
    assert [event[0] for event in events] == ["GET", "POST", "GET", "POST"]
    assert [events[1][2], events[3][2]] == [f"APIKey {KEY_A}", f"APIKey {KEY_B}"]


def test_discovery_resolves_key_for_each_page_and_keeps_it_out_of_evidence(tmp_path, caplog):
    transport, events = _rotating_transport()
    settings = _settings(tmp_path, api_key=STALE_KEY)
    with caplog.at_level(logging.DEBUG), DataJudClient(settings, transport=transport) as client:
        result = DataJudService(settings, client).discover(DiscoverRequest(tribunal="TJSP", limit=2, page_size=1))
    assert result["count"] == 2 and len(result["pages"]) == 2
    assert [event[0] for event in events] == ["GET", "POST", "GET", "POST"]
    assert len(list((settings.data_dir / "raw").glob("*.provenance.json"))) == 2
    inspected = [repr(settings), caplog.text, json.dumps(result)]
    inspected.extend(path.read_text(encoding="utf-8") for path in settings.data_dir.rglob("*") if path.is_file())
    for text in inspected:
        assert KEY_A not in text and KEY_B not in text and STALE_KEY not in text
        assert "Authorization:" not in text and "<html>" not in text


def test_cli_and_default_fastapi_adopt_auto_without_static_key(tmp_path, monkeypatch):
    transport, events = _rotating_transport()
    created_modes = []

    def factory(settings):
        created_modes.append(settings.auth_mode)
        return DataJudClient(settings, transport=transport)

    monkeypatch.setattr("app.core.DataJudClient", factory)
    monkeypatch.delenv("DATAJUD_AUTH_MODE", raising=False)
    monkeypatch.delenv("DATAJUD_API_KEY", raising=False)
    monkeypatch.setenv("DATAJUD_DATA_DIR", str(tmp_path / "evidence"))
    monkeypatch.setenv("DATAJUD_MAX_RETRIES", "0")
    result = CliRunner().invoke(cli_app, ["search", "--tribunal", "TJSP", "--size", "1", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["query_status"] == "success"
    with TestClient(create_app()) as http:
        response = http.post("/search", json={"tribunal": "TJSP", "size": 1})
    assert response.status_code == 200 and response.json()["query_status"] == "success"
    assert created_modes == ["auto", "auto"]
    assert [event[0] for event in events] == ["GET", "POST", "GET", "POST"]


@pytest.mark.parametrize("status", [401, 403])
def test_auto_refreshes_once_after_rejected_key_even_with_zero_transport_retries(tmp_path, status):
    events = []

    def handler(request):
        events.append((request.method, request.headers.get("Authorization")))
        if request.method == "GET":
            assert str(request.url) == WIKI and "Authorization" not in request.headers
            key = KEY_A if len(events) == 1 else KEY_B
            return httpx.Response(200, text=_html(key))
        if len(events) == 2:
            return httpx.Response(status, text=HTML_MARKER)
        assert request.headers["Authorization"] == f"APIKey {KEY_B}"
        return httpx.Response(200, json=_page())

    with DataJudClient(_settings(tmp_path), transport=httpx.MockTransport(handler)) as client:
        result = client.search("TJSP", {"size": 1})
    assert result.payload["hits"]["hits"]
    assert [method for method, _ in events] == ["GET", "POST", "GET", "POST"]


def test_rejected_refreshed_key_stops_without_loop_or_leaking(tmp_path, caplog):
    events = []

    def handler(request):
        events.append(request.method)
        if request.method == "GET":
            assert "Authorization" not in request.headers
            return httpx.Response(200, text=_html(KEY_A if len(events) == 1 else KEY_B))
        return httpx.Response(403, text=HTML_MARKER + KEY_B)

    with caplog.at_level(logging.DEBUG), DataJudClient(_settings(tmp_path, max_retries=3), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DataJudError) as caught:
            client.search("TJSP", {})
    assert events == ["GET", "POST", "GET", "POST"]
    assert caught.value.code == "authentication_error"
    assert caught.value.retrieval is None
    rendered = caplog.text + json.dumps(error_document(caught.value)) + "".join(traceback.format_exception(caught.value))
    assert KEY_A not in rendered and KEY_B not in rendered and HTML_MARKER not in rendered


def test_transient_api_retry_does_not_refetch_key(tmp_path):
    methods = []

    def handler(request):
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, text=_html(KEY_A))
        assert request.headers["Authorization"] == f"APIKey {KEY_A}"
        return httpx.Response(503) if methods.count("POST") == 1 else httpx.Response(200, json=_page())

    with DataJudClient(_settings(tmp_path, max_retries=1), transport=httpx.MockTransport(handler)) as client:
        client.search("TJSP", {})
    assert methods == ["GET", "POST", "POST"]


def test_auth_refresh_does_not_reset_consumed_transient_retry_budget(tmp_path):
    methods = []
    statuses = iter([503, 401, 503])

    def handler(request):
        methods.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, text=_html(KEY_A))
        return httpx.Response(next(statuses))

    with DataJudClient(_settings(tmp_path, max_retries=1), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DataJudError):
            client.search("TJSP", {})
    assert methods == ["GET", "POST", "POST", "GET", "POST"]


@pytest.mark.parametrize("problem", ["missing", "ambiguous", "oversized", "redirect", "http", "timeout"])
def test_key_source_failure_has_no_stale_fallback_no_post_and_no_html_evidence(tmp_path, caplog, problem):
    methods = []
    settings = _settings(tmp_path, api_key=STALE_KEY)

    def handler(request):
        methods.append(request.method)
        assert request.method == "GET" and str(request.url) == WIKI
        assert "Authorization" not in request.headers
        if problem == "timeout":
            raise httpx.ReadTimeout(HTML_MARKER + KEY_A, request=request)
        if problem == "redirect":
            return httpx.Response(302, headers={"Location": "https://untrusted.invalid/"}, text=HTML_MARKER)
        if problem == "http":
            return httpx.Response(503, text=HTML_MARKER + KEY_A)
        if problem == "missing":
            content = f"<html>{HTML_MARKER} but no credential here</html>"
        elif problem == "ambiguous":
            content = _html(KEY_A) + _html(KEY_B) + HTML_MARKER
        else:
            content = _html(KEY_A) + HTML_MARKER + "x" * 262145
        return httpx.Response(200, text=content)

    with caplog.at_level(logging.DEBUG), DataJudClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DataJudError) as caught:
            DataJudService(settings, client).search(SearchRequest(tribunal="TJSP", size=1))
    assert methods == ["GET"]
    assert caught.value.retrieval is None
    assert not list(settings.data_dir.rglob("*"))
    visible = caplog.text + json.dumps(error_document(caught.value)) + "".join(traceback.format_exception(caught.value))
    assert KEY_A not in visible and KEY_B not in visible and STALE_KEY not in visible
    assert HTML_MARKER not in visible


@pytest.mark.parametrize("fields", [
    {"tribunal": "INVALID"}, {"tribunal": "TJSP", "processo": "123"},
    {"tribunal": "TJSP", "query": {"size": 101}},
    {"tribunal": "TJSP", "query": {"query": {"script": {"script": "bad"}}}},
    {"tribunal": "TJSP", "company": "Synthetic company"},
    {"tribunal": "TJSP", "party": "Synthetic person"},
])
def test_invalid_and_unsupported_input_fails_before_wiki_get(tmp_path, fields):
    calls = []

    def handler(request):
        calls.append(request)
        pytest.fail("Invalid request must fail before every network operation.")

    settings = _settings(tmp_path)
    with DataJudClient(settings, transport=httpx.MockTransport(handler)) as client:
        with pytest.raises((ValueError, DataJudError)):
            DataJudService(settings, client).search(SearchRequest(**fields))
    assert calls == []


def test_manual_override_sends_only_configured_key_and_never_gets_wiki(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.method)
        assert request.method == "POST" and str(request.url) == API
        assert request.headers["Authorization"] == f"APIKey {STALE_KEY}"
        return httpx.Response(200, json=_page())

    with DataJudClient(_settings(tmp_path, auth_mode="manual", api_key=STALE_KEY), transport=httpx.MockTransport(handler)) as client:
        client.search("TJSP", {})
    assert calls == ["POST"]


def test_auto_health_and_offline_extract_use_no_client_and_no_network(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    payload = _page()
    stored = Storage(settings.data_dir).save_raw(
        json.dumps(payload).encode(), tribunal="TJSP", endpoint_alias="api_publica_tjsp",
        endpoint=API, query={"query": {"match_all": {}}, "size": 1},
        retrieved_at="2026-09-21T12:00:00Z",
    )

    def forbidden_client(*_args, **_kwargs):
        pytest.fail("Health and offline extraction must not even construct a network client.")

    monkeypatch.setattr("app.core.DataJudClient", forbidden_client)
    monkeypatch.setenv("DATAJUD_AUTH_MODE", "auto")
    monkeypatch.setenv("DATAJUD_DATA_DIR", str(settings.data_dir))
    monkeypatch.delenv("DATAJUD_API_KEY", raising=False)
    runner = CliRunner()
    assert runner.invoke(cli_app, ["health"]).exit_code == 0
    offline = runner.invoke(cli_app, ["extract", str(stored.raw_path), "--json"])
    assert offline.exit_code == 0, offline.output
    assert json.loads(offline.stdout)["mode"] == "offline"
    with TestClient(create_app(settings=settings)) as http:
        assert http.get("/health").status_code == 200
        response = http.post("/extract", json={"raw_file": str(stored.raw_path)})
    assert response.status_code == 200 and response.json()["mode"] == "offline"
    assert response.json()["provenance"] == stored.provenance


def test_oversized_chunked_wiki_body_stops_reading_and_closes_response(tmp_path):
    class OversizedStream(httpx.SyncByteStream):
        chunks = 0
        closed = False

        def __iter__(self):
            for _ in range(100):
                self.chunks += 1
                yield b"x" * 8192

        def close(self):
            self.closed = True

    stream = OversizedStream()
    methods = []

    def handler(request):
        methods.append(request.method)
        assert request.method == "GET"
        return httpx.Response(200, headers={"Content-Type": "text/html"}, stream=stream)

    with DataJudClient(_settings(tmp_path), transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(DataJudError) as caught:
            client.search("TJSP", {})
    assert caught.value.code == "public_key_response_too_large"
    assert stream.closed
    assert stream.chunks <= 33  # 256 KiB plus the first chunk that crosses the bound.
    assert methods == ["GET"]
