from copy import deepcopy
from datetime import datetime, timezone
import json
import logging

import httpx
import pytest

from app.config import Settings
from app.datajud import DataJudClient, DataJudError, _retry_delay, validate_response


def valid_payload(hits=None, total=None):
    records = [] if hits is None else hits
    return {
        "timed_out": False, "_shards": {"failed": 0},
        "hits": {"total": total if total is not None else {"value": len(records), "relation": "eq"}, "hits": records},
    }


def make_client(handler, **settings):
    return DataJudClient(Settings(api_key="test-only-key", max_retries=settings.pop("max_retries", 0), **settings), transport=httpx.MockTransport(handler))


def test_request_auth_endpoint_raw_query_provenance_and_logging(caplog):
    source = {"numeroProcesso": "00012345620248260001", "unknown": "ação"}
    raw = json.dumps(valid_payload([{"_source": source, "sort": [123]}]), ensure_ascii=False, indent=2).encode("utf-8")
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, content=raw)

    query = {"query": {"match_all": {}}, "size": 1}
    with caplog.at_level(logging.INFO), make_client(handler) as client:
        result = client.search(" tjsp ", query)
    request = sent[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search"
    assert request.headers["Authorization"] == "APIKey test-only-key"
    assert request.headers["Content-Type"] == "application/json"
    assert json.loads(request.content) == result.query
    assert result.raw_bytes == raw
    assert result.payload["hits"]["hits"][0]["_source"] == source
    assert result.tribunal == "TJSP" and result.endpoint_alias == "api_publica_tjsp"
    assert result.retrieved_at.endswith("Z")
    assert datetime.fromisoformat(result.retrieved_at).tzinfo == timezone.utc
    query["size"] = 100
    assert result.query["size"] == 1
    assert "operation=search" in caplog.text and "hits=1" in caplog.text
    assert "status=200" in caplog.text and "duration_ms=" in caplog.text
    assert "test-only-key" not in caplog.text and "numeroProcesso" not in caplog.text
    assert client._client.is_closed


@pytest.mark.parametrize("total", [{"value": 0, "relation": "eq"}, 0])
def test_zero_hits_is_a_valid_retrieval(total):
    with make_client(lambda request: httpx.Response(200, json=valid_payload(total=total))) as client:
        result = client.search("TJSP", {})
    assert result.payload["hits"]["hits"] == []
    assert result.payload["hits"]["total"] == total


def test_missing_key_fails_without_network():
    requests = []
    with DataJudClient(Settings(), transport=httpx.MockTransport(lambda request: requests.append(request))) as client:
        with pytest.raises(DataJudError) as caught:
            client.search("TJSP", {})
    assert caught.value.code == "configuration_error"
    assert caught.value.status_code == 503 and not requests


@pytest.mark.parametrize("tribunal,query", [("missing", {}), ("TJSP", {"size": 101}), ("TJSP", {"query": {"script": {}}})])
def test_client_itself_enforces_limits_before_network(tribunal, query):
    requests = []
    with make_client(lambda request: requests.append(request)) as client:
        with pytest.raises(ValueError):
            client.search(tribunal, query)
    assert not requests


@pytest.mark.parametrize("status,retries,code", [
    (401, 0, "authentication_error"), (403, 0, "authentication_error"),
    (404, 0, "upstream_error"), (500, 0, "upstream_error"),
    (429, 2, "upstream_error"), (502, 2, "upstream_error"),
    (503, 2, "upstream_error"), (504, 2, "upstream_error"),
    (302, 0, "upstream_error"),
])
def test_http_failures_never_become_empty_results_or_leak_body(status, retries, code, monkeypatch, caplog):
    calls, sleeps = [], []
    monkeypatch.setattr("app.datajud.time.sleep", sleeps.append)

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="DO-NOT-LOG upstream secret", headers={"Retry-After": "99999", "Location": "https://example.org"})

    with caplog.at_level(logging.INFO), make_client(handler, max_retries=2) as client:
        with pytest.raises(DataJudError) as caught:
            client.search("TJSP", {})
    assert caught.value.code == code and caught.value.upstream_status == status
    assert caught.value.status_code == 502 and caught.value.retrieval is None
    assert len(calls) == retries + 1 and len(sleeps) == retries
    assert all(0 <= delay <= 2 for delay in sleeps)
    assert "DO-NOT-LOG" not in str(caught.value) + caplog.text
    assert "test-only-key" not in str(caught.value) + caplog.text


def test_transient_http_error_can_recover(monkeypatch):
    responses = iter([httpx.Response(503), httpx.Response(200, json=valid_payload())])
    sleeps = []
    monkeypatch.setattr("app.datajud.time.sleep", sleeps.append)
    with make_client(lambda request: next(responses), max_retries=1) as client:
        assert client.search("TJSP", {}).payload["hits"]["hits"] == []
    assert sleeps == [0.25]


@pytest.mark.parametrize("error,expected,local_status,retry", [
    (httpx.ReadTimeout, "timeout", 504, True),
    (httpx.ConnectTimeout, "timeout", 504, True),
    (httpx.ConnectError, "connection_error", 503, True),
    (httpx.ReadError, "connection_error", 503, True),
    (httpx.RemoteProtocolError, "connection_error", 503, True),
    (httpx.UnsupportedProtocol, "connection_error", 503, False),
])
def test_transport_errors_have_bounded_retries_and_safe_messages(error, expected, local_status, retry, monkeypatch):
    calls, sleeps = [], []
    monkeypatch.setattr("app.datajud.time.sleep", sleeps.append)

    def handler(request):
        calls.append(request)
        raise error("DO-NOT-LOG transport secret", request=request)

    with make_client(handler, max_retries=3) as client:
        with pytest.raises(DataJudError) as caught:
            client.search("TJSP", {})
    assert caught.value.code == expected and caught.value.status_code == local_status
    assert len(calls) == (4 if retry else 1)
    assert len(sleeps) == (3 if retry else 0)
    assert "DO-NOT-LOG" not in str(caught.value)


@pytest.mark.parametrize("raw", [b"not JSON", b"\xff", b'{"x": NaN}', b'{"x":1,"x":2}', b"{" * 2000])
def test_invalid_json_preserves_exact_bytes_for_core(raw):
    with make_client(lambda request: httpx.Response(200, content=raw)) as client:
        with pytest.raises(DataJudError) as caught:
            client.search("TJSP", {})
    assert caught.value.code == "invalid_json"
    assert caught.value.retrieval.raw_bytes == raw
    assert caught.value.retrieval.payload is None


@pytest.mark.parametrize("change", [
    lambda p: p.clear(), lambda p: p.update(hits=[]),
    lambda p: p["hits"].update(hits={}), lambda p: p["hits"].update(hits=[{}]),
    lambda p: p["hits"].update(hits=[{"_source": None}]),
    lambda p: p["hits"].update(total=None), lambda p: p["hits"].update(total=True),
    lambda p: p["hits"].update(total={"value": -1, "relation": "eq"}),
    lambda p: p["hits"].update(total={"value": 0, "relation": "unknown"}),
    lambda p: p.pop("timed_out"), lambda p: p.update(timed_out=0),
    lambda p: p.pop("_shards"), lambda p: p["_shards"].update(failed=-1),
    lambda p: p["_shards"].update(failed=False),
])
def test_malformed_schema_is_not_mistaken_for_zero_hits(change):
    payload = deepcopy(valid_payload())
    change(payload)
    raw = json.dumps(payload).encode()
    with make_client(lambda request: httpx.Response(200, content=raw)) as client:
        with pytest.raises(DataJudError) as caught:
            client.search("TJSP", {})
    assert caught.value.code == "invalid_response"
    assert caught.value.retrieval.raw_bytes == raw


@pytest.mark.parametrize("timed_out,failed", [(True, 0), (False, 1), (True, 3)])
def test_partial_response_preserves_raw_and_is_never_success(timed_out, failed, monkeypatch):
    payload = valid_payload()
    payload["timed_out"] = timed_out
    payload["_shards"]["failed"] = failed
    calls = []
    monkeypatch.setattr("app.datajud.time.sleep", lambda delay: pytest.fail("partial response must not retry"))

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    with make_client(handler, max_retries=3) as client:
        with pytest.raises(DataJudError) as caught:
            client.search("TJSP", {})
    assert caught.value.code == "partial_response" and len(calls) == 1
    assert caught.value.retrieval.payload == payload


@pytest.mark.parametrize("header", ["999999", "-2", "NaN", "Infinity", "invalid", "Wed, 01 Jan 2099 00:00:00 GMT"])
def test_retry_after_is_always_bounded(header):
    assert 0 <= _retry_delay(0, header) <= 2


def test_public_validation_is_offline_and_preserves_the_input():
    payload = valid_payload([{"_source": {"unknown": "preserved"}}])
    before = deepcopy(payload)
    assert validate_response(payload) == 1
    assert payload == before
    assert validate_response(valid_payload()) == 0


@pytest.mark.parametrize("invalid", [{}, [], None, {"hits": {"hits": []}}])
def test_public_validation_rejects_bad_schema(invalid):
    with pytest.raises(ValueError):
        validate_response(invalid)


@pytest.mark.parametrize("timed_out,failed", [(True, 0), (False, 1)])
def test_public_validation_rejects_partial_evidence(timed_out, failed):
    payload = valid_payload()
    payload["timed_out"] = timed_out
    payload["_shards"]["failed"] = failed
    with pytest.raises(ValueError, match="parcial"):
        validate_response(payload)
