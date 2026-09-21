import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app

runner = CliRunner()


def test_health_and_help_offline(monkeypatch):
    monkeypatch.delenv('DATAJUD_API_KEY', raising=False)
    assert runner.invoke(app, ['health']).exit_code == 0
    assert json.loads(runner.invoke(app, ['health']).stdout)['status'] == 'ok'
    for args in [['--help'], ['search','--help'], ['discover','--help'], ['process','--help'], ['extract','--help']]:
        assert runner.invoke(app, args).exit_code == 0


def test_cli_json_raw_and_offline(service_factory, api_payload, monkeypatch):
    service, calls = service_factory(api_payload)
    monkeypatch.setattr('app.cli.DataJudService', lambda _: service)
    result = runner.invoke(app, ['search','--tribunal','TJSP','--json'])
    assert result.exit_code == 0, result.output
    body = json.loads(result.stdout)
    raw = runner.invoke(app, ['search','--tribunal','TJSP','--raw'])
    assert raw.exit_code == 0, raw.output
    assert json.loads(raw.stdout) == api_payload
    assert 'provenance' not in json.loads(raw.stdout)
    before = len(calls)
    offline = runner.invoke(app, ['extract', body['raw_path'], '--json'])
    assert offline.exit_code == 0, offline.output
    assert json.loads(offline.stdout)['mode'] == 'offline'
    assert len(calls) == before


def test_cli_process_and_discover(service_factory, api_payload, monkeypatch):
    service, _ = service_factory(api_payload)
    monkeypatch.setattr('app.cli.DataJudService', lambda _: service)
    process = runner.invoke(app, ['process','00000018420208260001','--json'])
    assert process.exit_code == 0, process.output
    assert json.loads(process.stdout)['tribunal'] == 'TJSP'
    discovery = runner.invoke(app, ['discover','--tribunal','TJSP','--subject','7791','--class','386','--movement','982','--from','2020-01-01','--to','2020-12-31','--limit','1','--json'])
    assert discovery.exit_code == 0, discovery.output
    assert json.loads(discovery.stdout)['discovery']['returned_hits'] >= 1


def test_cli_missing_key_invalid_input_and_unsupported(monkeypatch):
    monkeypatch.delenv('DATAJUD_API_KEY', raising=False)
    for args, code in [(['search','--tribunal','TJSP'], 'configuration_error'), (['search','--tribunal','BAD'], 'invalid_request'), (['search','--tribunal','TJSP','--company','Example'], 'unsupported_filter'), (['process','bad'], 'invalid_request')]:
        result = runner.invoke(app, args)
        assert result.exit_code != 0
        assert code in result.output
        assert 'Traceback' not in result.output


def test_query_file_and_conflicting_flags(service_factory, api_payload, monkeypatch, tmp_path):
    service, calls = service_factory(api_payload)
    monkeypatch.setattr('app.cli.DataJudService', lambda _: service)
    file = tmp_path / 'query.json'
    file.write_text('{"query":{"match_all":{}},"size":1}', encoding='utf-8')
    result = runner.invoke(app, ['search','--tribunal','TJSP','--query-file',str(file),'--json'])
    assert result.exit_code == 0, result.output
    assert calls[-1]['size'] == 1
    before = len(calls)
    result = runner.invoke(app, ['search','--tribunal','TJSP','--query-file',str(file),'--subject','1'])
    assert result.exit_code != 0 and len(calls) == before


def test_deep_upstream_json_cli_has_safe_error(service_factory, monkeypatch):
    import httpx
    raw = ('{"timed_out":false,"_shards":{"failed":0},"hits":{"total":{"value":1,"relation":"eq"},"hits":[{"_source":{"futureField":' + '[' * 600 + '0' + ']' * 600 + '}}]}}').encode()
    service, _ = service_factory(handler=lambda _: httpx.Response(200, content=raw))
    monkeypatch.setattr('app.cli.DataJudService', lambda _: service)
    result = runner.invoke(app, ['search','--tribunal','TJSP','--json'])
    assert result.exit_code == 1
    body = json.loads(result.stderr)
    assert body['error']['code'] == 'extraction_error'
    assert Path(body['error']['raw_path']).read_bytes() == raw
