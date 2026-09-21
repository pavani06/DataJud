import copy
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.datajud import DataJudError
from app.models import DiscoverRequest


def make_page(payload, identities, cursor=True):
    result = copy.deepcopy(payload)
    source = result['hits']['hits'][0]
    hits = []
    for identity in identities:
        hit = copy.deepcopy(source)
        hit['_id'] = identity
        if cursor:
            hit['sort'] = [int(identity)]
        else:
            hit.pop('sort', None)
        hits.append(hit)
    result['hits'].update(hits=hits, total={'value': 100, 'relation': 'gte'})
    return result


def test_bounded_pages_distinct_candidates(service_factory, api_payload, monkeypatch):
    monkeypatch.setattr('app.discover.time.sleep', lambda _: None)
    responses = iter([make_page(api_payload, ['1', '2']), make_page(api_payload, ['3'])])
    service, calls = service_factory(handler=lambda _: httpx.Response(200, json=next(responses)))
    result = service.discover(DiscoverRequest(tribunal='TJSP', classe=386, movimento=982, limit=3, page_size=2))
    assert result['count'] == 3
    assert [query['size'] for query in calls] == [2, 1]
    assert calls[1]['search_after'] == [2]
    assert result['discovery']['pagination']['stop_reason'] == 'limit'
    assert result['discovery']['returned_hits'] == 3
    assert len(result['pages']) == 2
    manifest = json.loads(Path(result['manifest_path']).read_text(encoding='utf-8'))
    assert manifest['results'] == result['results']
    assert all(Path(page['raw_path']).exists() for page in result['pages'])


def test_duplicates_do_not_erase_different_ids(service_factory, api_payload, monkeypatch):
    monkeypatch.setattr('app.discover.time.sleep', lambda _: None)
    responses = iter([make_page(api_payload, ['1', '2']), make_page(api_payload, ['2']), make_page(api_payload, [])])
    service, calls = service_factory(handler=lambda _: httpx.Response(200, json=next(responses)))
    result = service.discover(DiscoverRequest(tribunal='TJSP', limit=3, page_size=2))
    assert result['count'] == 2
    assert len(calls) <= 3
    assert result['discovery']['pagination']['duplicates_removed'] == 1
    assert result['discovery']['pagination']['stop_reason'] in {'missing_cursor', 'repeated_cursor'}


def test_missing_cursor_stops(service_factory, api_payload):
    service, calls = service_factory(make_page(api_payload, ['1'], cursor=False))
    result = service.discover(DiscoverRequest(tribunal='TJSP', limit=3, page_size=1))
    assert len(calls) == 1
    assert result['discovery']['pagination']['stop_reason'] == 'missing_cursor'
    assert result['discovery']['pagination']['complete_snapshot'] is False


def test_later_upstream_error_never_becomes_success(service_factory, api_payload, monkeypatch):
    monkeypatch.setattr('app.discover.time.sleep', lambda _: None)
    responses = iter([httpx.Response(200, json=make_page(api_payload, ['1'])), httpx.Response(503)])
    service, calls = service_factory(handler=lambda _: next(responses))
    with pytest.raises(DataJudError):
        service.discover(DiscoverRequest(tribunal='TJSP', limit=2, page_size=1))
    assert len(calls) == 2
    assert list((service.settings.data_dir / 'raw').glob('*.json'))
    assert not list((service.settings.data_dir / 'extracted').glob('discovery*'))


@pytest.mark.parametrize('fields', [{'limit': 1001}, {'limit': 0}, {'page_size': 101}, {'size': 5}, {'query': {'size': 500}}, {'query': {'from': 10}}])
def test_discovery_limits_cannot_be_bypassed(fields):
    with pytest.raises(ValidationError):
        DiscoverRequest(tribunal='TJSP', **fields)


def test_upstream_oversized_page_is_error_with_raw_preserved(service_factory, api_payload):
    service, _ = service_factory(make_page(api_payload, ['1', '2']))
    with pytest.raises(DataJudError) as caught:
        service.discover(DiscoverRequest(tribunal='TJSP', limit=1, page_size=1))
    assert caught.value.code == 'unexpected_page_size'
    assert len(json.loads(Path(caught.value.raw_path).read_bytes())['hits']['hits']) == 2
    assert not list((service.settings.data_dir / 'extracted').glob('discovery*'))


def test_incomplete_hit_identity_preserves_different_degrees(service_factory, api_payload):
    payload = make_page(api_payload, ['1', '2'])
    for hit, degree in zip(payload['hits']['hits'], ['G1', 'G2']):
        hit.pop('_index', None)
        hit['_id'] = 'same'
        hit['_source']['grau'] = degree
    service, calls = service_factory(payload)
    result = service.discover(DiscoverRequest(tribunal='TJSP', limit=2, page_size=2))
    assert result['count'] == 2 and len(calls) == 1
    assert [record['grau'] for record in result['results']] == ['G1', 'G2']
