import copy
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.core import DataJudService
from app.datajud import DataJudClient, DataJudError
from app.models import SearchRequest


def test_raw_hash_and_offline_determinism(service_factory, api_payload, monkeypatch):
    service, calls = service_factory(api_payload)
    result = service.search(SearchRequest(tribunal='TJSP', size=1))
    original = Path(result['raw_path']).read_bytes()
    assert result['provenance']['raw_sha256'] == hashlib.sha256(original).hexdigest()
    assert json.loads(Path(result['extracted_path']).read_text(encoding='utf-8')) == result
    monkeypatch.setattr(DataJudClient, 'search', lambda *_a, **_k: pytest.fail('Offline called CNJ'))
    offline = DataJudService(Settings(data_dir=service.settings.data_dir)).extract_file(Path(result['raw_path']))
    assert offline['results'] == result['results']
    assert offline['provenance'] == result['provenance']
    assert offline['mode'] == 'offline'
    assert offline['extracted_path'] != result['extracted_path']
    assert Path(result['raw_path']).read_bytes() == original
    assert len(calls) == 1


def test_empty_success_has_provenance(service_factory, api_payload):
    api_payload['hits'].update(hits=[], total={'value': 0, 'relation': 'eq'})
    service, _ = service_factory(api_payload)
    result = service.search(SearchRequest(tribunal='TJSP'))
    assert result['found'] is False and result['count'] == 0
    assert result['query_status'] == 'success'
    assert result['provenance']['raw_sha256']
    assert any('não retornou hits' in w for w in result['warnings'])


@pytest.mark.parametrize('failure', ['timed_out', 'shards', 'malformed', 'json'])
def test_failed_200_preserved_and_cannot_reextract(failure, service_factory, api_payload):
    if failure == 'timed_out':
        api_payload['timed_out'] = True
    elif failure == 'shards':
        api_payload['_shards']['failed'] = 1
    elif failure == 'malformed':
        api_payload = {'message': 'unexpected'}
    raw = b'not json' if failure == 'json' else json.dumps(api_payload).encode()
    service, _ = service_factory(handler=lambda _: httpx.Response(200, content=raw))
    with pytest.raises(DataJudError) as caught:
        service.search(SearchRequest(tribunal='TJSP'))
    path = Path(caught.value.raw_path)
    assert path.read_bytes() == raw
    with pytest.raises(DataJudError, match='reprocessamento recusado'):
        service.extract_file(path)


@pytest.mark.parametrize('field', ['company', 'party'])
def test_unsupported_no_network(field, service_factory, api_payload):
    service, calls = service_factory(api_payload)
    with pytest.raises(DataJudError) as caught:
        service.search(SearchRequest(tribunal='TJSP', **{field: 'Example'}))
    assert caught.value.code == 'unsupported_filter'
    assert not calls


def test_process_inferred_and_override_explicit(service_factory, api_payload):
    service, calls = service_factory(api_payload)
    result = service.process('0000001-84.2020.8.26.0001')
    assert result['tribunal_resolution']['method'] == 'cnj_origin'
    assert result['tribunal'] == 'TJSP'
    assert calls[-1]['query']['match']['numeroProcesso'] == '00000018420208260001'
    overridden = service.process('00000018420208260001', 'STJ')
    assert overridden['tribunal_resolution']['method'] == 'provided'
    assert overridden['tribunal'] == 'STJ'


def test_repeat_preserves_both_retrievals(service_factory, api_payload):
    service, _ = service_factory(api_payload)
    one = service.search(SearchRequest(tribunal='TJSP'))
    two = service.search(SearchRequest(tribunal='TJSP'))
    assert one['raw_path'] != two['raw_path']
    assert Path(one['raw_path']).read_bytes() == Path(two['raw_path']).read_bytes()


def test_io_failure_explicit(service_factory, api_payload, monkeypatch):
    service, _ = service_factory(api_payload)
    def fail(*_a, **_k):
        raise OSError('disk full')
    monkeypatch.setattr(service.storage, 'save_raw', fail)
    with pytest.raises(DataJudError) as caught:
        service.search(SearchRequest(tribunal='TJSP'))
    assert caught.value.code == 'storage_error'


def test_tampered_raw_rejected(service_factory, api_payload):
    service, _ = service_factory(api_payload)
    result = service.search(SearchRequest(tribunal='TJSP'))
    Path(result['raw_path']).write_bytes(b'{}')
    with pytest.raises(DataJudError) as caught:
        service.extract_file(Path(result['raw_path']))
    assert caught.value.code == 'invalid_raw_evidence'
