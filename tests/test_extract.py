from copy import deepcopy

import pytest

from app.extract import extract_response


def response(*sources):
    return {"hits": {"total": {"value": len(sources), "relation": "eq"}, "hits": [
        {"_id": f"id-{index}", "_index": "api_publica_tjsp", "_source": source}
        for index, source in enumerate(sources)
    ]}}


def test_normalization_preserves_all_documented_fields_and_unknown_details():
    source = {
        "numeroProcesso": "00000000020268260000",
        "orgaoJulgador": {"codigo": 123, "nome": "Vara", "codigoMunicipioIBGE": 3550308},
        "dataAjuizamento": "2026-01-02T00:00:00.000Z",
        "dataHoraUltimaAtualizacao": "2026-09-01T00:00:00Z",
        "@timestamp": "2026-09-20T00:00:00Z",
        "nivelSigilo": 0,
        "classe": {"codigo": 436, "nome": "Procedimento", "future": {"flag": True}},
        "assuntos": [{"codigo": 1, "nome": "Assunto"}],
        "movimentos": [{"codigo": 26, "complementosTabelados": [{"valor": 1}]}],
        "grau": "G1", "tribunal": "TJSP", "sistema": {"codigo": 1},
        "formato": {"codigo": 1}, "id": "source-id",
        "futureField": {"nested": [1, {"name": "Preservado"}]},
    }
    payload = response(source)
    before = deepcopy(payload)
    provenance = {"source": "CNJ/DataJud", "query": {"size": 1}, "raw_sha256": "digest"}
    record = extract_response(payload, provenance)[0]

    expected = deepcopy(source)
    for original, normalized in {
        "numeroProcesso": "numero_processo", "orgaoJulgador": "orgao_julgador",
        "dataAjuizamento": "data_ajuizamento",
        "dataHoraUltimaAtualizacao": "data_hora_ultima_atualizacao",
        "@timestamp": "timestamp", "nivelSigilo": "nivel_sigilo",
    }.items():
        expected[normalized] = expected.pop(original)
    expected["extra_fields"] = {"futureField": expected.pop("futureField")}
    expected["provenance"] = {**provenance, "datajud_id": "id-0", "datajud_index": "api_publica_tjsp"}
    assert record == expected
    assert payload == before


def test_nested_subject_arrays_flatten_without_losing_object_fields():
    first = {"codigo": 1, "nome": "Primeiro", "extra": ["x"]}
    second = {"codigo": 2, "nome": "Segundo"}
    subjects = [[first], [], [[[second]]], {"codigo": 3}]
    payload = response({"assuntos": subjects})
    record = extract_response(payload, {})[0]
    assert record["assuntos"] == [first, second, {"codigo": 3}]
    assert payload["hits"]["hits"][0]["_source"]["assuntos"] == subjects


def test_each_record_and_provenance_are_independent():
    shared = {"classe": {"codigo": 1}, "assuntos": [[{"codigo": 2}]], "unknown": {"x": 3}}
    payload = response(shared, shared)
    provenance = {"query": {"query": {"match_all": {}}}}
    records = extract_response(payload, provenance)
    records[0]["classe"]["codigo"] = 99
    records[0]["assuntos"][0]["codigo"] = 99
    records[0]["extra_fields"]["unknown"]["x"] = 99
    records[0]["provenance"]["query"]["query"]["match_all"]["changed"] = True
    assert records[1]["classe"]["codigo"] == 1
    assert records[1]["assuntos"][0]["codigo"] == 2
    assert records[1]["extra_fields"]["unknown"]["x"] == 3
    assert records[1]["provenance"]["query"] == provenance["query"]
    assert shared == {"classe": {"codigo": 1}, "assuntos": [[{"codigo": 2}]], "unknown": {"x": 3}}


def test_missing_fields_stay_absent_and_upstream_null_stays_present():
    records = extract_response(response({}, {"grau": None}), {})
    assert set(records[0]) == {"provenance"}
    assert records[1]["grau"] is None
    assert "tribunal" not in records[1]
    assert "numero_processo" not in records[1]


def test_upstream_provenance_cannot_replace_evidence_metadata():
    record = extract_response(response({"provenance": {"source": "fake"}}), {"source": "CNJ/DataJud"})[0]
    assert record["provenance"]["source"] == "CNJ/DataJud"
    assert record["extra_fields"]["provenance"] == {"source": "fake"}


def test_zero_hits_is_valid_without_inventing_records():
    assert extract_response(response(), {"source": "CNJ/DataJud"}) == []


@pytest.mark.parametrize("payload", [
    None, [], {}, {"error": "upstream"}, {"hits": []}, {"hits": {}},
    {"hits": {"hits": None}}, {"hits": {"hits": {}}},
    {"hits": {"hits": [None]}}, {"hits": {"hits": [{}]}},
    {"hits": {"hits": [{"_source": None}]}},
    {"hits": {"hits": [{"_source": []}]}},
])
def test_unexpected_schema_raises_instead_of_becoming_zero_hits(payload):
    with pytest.raises(ValueError):
        extract_response(payload, {})


def test_hit_identifiers_are_only_added_when_present():
    record = extract_response({"hits": {"hits": [{"_source": {}}]}}, {"source": "CNJ/DataJud"})[0]
    assert record == {"provenance": {"source": "CNJ/DataJud"}}


def test_unexpected_subject_leaves_are_preserved_instead_of_discarded():
    record = extract_response(response({"assuntos": [[{"codigo": 1}, "unknown", None]]}), {})[0]
    assert record["assuntos"] == [{"codigo": 1}, "unknown", None]
