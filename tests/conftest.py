import copy
import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.core import DataJudService
from app.datajud import DataJudClient


@pytest.fixture
def api_payload():
    payload = json.loads((Path(__file__).parent / 'fixtures/datajud_anonymized.json').read_text(encoding='utf-8'))
    payload.pop('_fixture', None)
    return payload


@pytest.fixture
def service_factory(tmp_path):
    clients = []

    def factory(payload=None, handler=None):
        calls = []
        def request_handler(request):
            calls.append(json.loads(request.content))
            return handler(request) if handler else httpx.Response(200, json=copy.deepcopy(payload))
        settings = Settings(api_key='local-test-key', data_dir=tmp_path / 'evidence', max_retries=0)
        client = DataJudClient(settings, transport=httpx.MockTransport(request_handler))
        clients.append(client)
        return DataJudService(settings, client), calls
    yield factory
    for client in clients:
        client.close()
