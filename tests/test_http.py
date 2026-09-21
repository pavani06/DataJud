from fastapi.testclient import TestClient
import pytest

from app.main import create_app


def test_health_without_configuration(monkeypatch):
    monkeypatch.setenv('DATAJUD_TIMEOUT_SECONDS', 'invalid')
    with TestClient(create_app()) as client:
        assert client.get('/health').json() == {'status': 'ok', 'service': 'datajud-lite'}
        assert client.post('/search', json={'tribunal': 'TJSP'}).status_code == 503


def test_http_routes_share_service(service_factory, api_payload):
    service, calls = service_factory(api_payload)
    with TestClient(create_app(service=service)) as client:
        search = client.post('/search', json={'tribunal': 'TJSP', 'subject': 7791})
        assert search.status_code == 200
        assert calls[-1]['query']['match'] == {'assuntos.codigo': 7791}
        process = client.get('/process/00000018420208260001')
        assert process.status_code == 200
        assert process.json()['tribunal_resolution']['method'] == 'cnj_origin'
        discovery = client.post('/discover', json={'tribunal': 'TJSP', 'limit': 1})
        assert discovery.status_code == 200
        raw_path = search.json()['raw_path']
        before = len(calls)
        offline = client.post('/extract', json={'raw_file': raw_path})
        assert offline.status_code == 200 and offline.json()['mode'] == 'offline'
        assert len(calls) == before


@pytest.mark.parametrize('body', [{'tribunal':'BAD'}, {'tribunal':'TJSP','processo':'bad'}, {'tribunal':'TJSP','size':101}, {'tribunal':'TJSP','query':{'query':{'script':{}}}}, {'tribunal':'TJSP','company':'Example'}, {'tribunal':'TJSP','party':'Example'}])
def test_bad_and_unsupported_requests_do_not_call_network(body, service_factory, api_payload):
    service, calls = service_factory(api_payload)
    with TestClient(create_app(service=service)) as client:
        response = client.post('/search', json=body)
        assert response.status_code == 422
        assert response.json()['query_status'] == 'error'
        assert not calls


def test_validation_does_not_echo_arbitrary_payload(service_factory, api_payload):
    service, _ = service_factory(api_payload)
    with TestClient(create_app(service=service)) as client:
        response = client.post('/search', json={'tribunal':'TJSP','secret':'do-not-echo'})
        assert response.status_code == 422 and 'do-not-echo' not in response.text


def test_deep_upstream_json_gets_structured_error_and_raw(service_factory):
    import httpx
    from pathlib import Path
    raw = ('{"timed_out":false,"_shards":{"failed":0},"hits":{"total":{"value":1,"relation":"eq"},"hits":[{"_source":{"futureField":' + '[' * 600 + '0' + ']' * 600 + '}}]}}').encode()
    service, _ = service_factory(handler=lambda _: httpx.Response(200, content=raw))
    with TestClient(create_app(service=service)) as client:
        response = client.post('/search', json={'tribunal':'TJSP'})
    assert response.status_code == 502
    assert response.json()['error']['code'] == 'extraction_error'
    assert Path(response.json()['error']['raw_path']).read_bytes() == raw
