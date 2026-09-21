from copy import deepcopy
from datetime import date, datetime

import pytest

from app.queries import build_query, prepare_raw_query


@pytest.mark.parametrize("number", ["00409435319968260114", "0040943-53.1996.8.26.0114"])
def test_cnj_number_is_preserved_as_twenty_ascii_digits(number):
    query = build_query(processo=number)
    assert query["query"] == {"match": {"numeroProcesso": "00409435319968260114"}}
    assert query["size"] == 10
    assert query["sort"] == [{"@timestamp": {"order": "asc"}}]


@pytest.mark.parametrize("number", [
    "", "123", "00012345620248260001 ", "0001234/56.2024.8.26.0001",
    "٠" * 20, "１" * 20, 12345678901234567890,
])
def test_malformed_numbers_are_not_silently_repaired(number):
    with pytest.raises(ValueError, match="CNJ"):
        build_query(processo=number)


def test_combined_filters_and_inclusive_end_date():
    query = build_query(
        classe="436", assunto=123, date_from=date(2024, 2, 1), date_to="2024-02-29",
        size=2, search_after=[1712345678901],
    )
    assert query["query"]["bool"]["filter"] == [
        {"match": {"classe.codigo": 436}}, {"match": {"assuntos.codigo": 123}},
        {"range": {"dataAjuizamento": {"gte": "2024-02-01T00:00:00Z", "lt": "2024-03-01T00:00:00Z"}}},
    ]
    assert query["search_after"] == [1712345678901]
    assert query["size"] == 2


@pytest.mark.parametrize("kwargs", [
    {"date_from": "2024-02-30"}, {"date_from": "20240201"},
    {"date_from": "2024-01-01T00:00:00Z"}, {"date_from": datetime(2024, 1, 1)},
    {"date_from": "2024-02-02", "date_to": "2024-02-01"},
    {"date_to": "9999-12-31"}, {"classe": 0}, {"classe": True},
    {"assunto": "abc"}, {"assunto": -2}, {"assunto": 1.5},
])
def test_invalid_filters_are_rejected_before_network(kwargs):
    with pytest.raises(ValueError):
        build_query(**kwargs)


def test_queries_are_independent_copies_and_receive_defaults():
    original = {"query": {"bool": {"filter": [{"term": {"grau": "G1"}}]}}, "search_after": [1]}
    before = deepcopy(original)
    prepared = prepare_raw_query(original)
    prepared["query"]["bool"]["filter"][0]["term"]["grau"] = "G2"
    prepared["search_after"][0] = 2
    assert original == before
    assert build_query()["query"] == {"match_all": {}}
    prepared["sort"][0]["@timestamp"]["order"] = "desc"
    assert build_query()["sort"][0]["@timestamp"]["order"] == "asc"


@pytest.mark.parametrize("query", [
    [], {"size": 0}, {"size": 101}, {"size": True}, {"size": "10"},
    {"from": -1}, {"from": 9901}, {"from": True}, {"from": 1, "search_after": [1]},
    {"search_after": []}, {"search_after": "1"}, {"search_after": [[1]]},
    {"search_after": [{"x": 1}]}, {"search_after": [float("nan")]},
    {"query": {"term": {"value": float("inf")}}},
    {"query": None}, {"query": []}, {"query": {}}, {"sort": []}, {"sort": 2},
    {"track_total_hits": -1}, {"track_total_hits": "true"},
    {"track_total_hits": False},
    {"aggs": {"all": {"terms": {"field": "grau"}}}}, {"scroll": "1m"},
    {"query": {"match": {1: "value"}}}, {"query": {"term": {"a": (1, 2)}}},
])
def test_raw_limits_and_shapes(query):
    with pytest.raises(ValueError):
        prepare_raw_query(query)


@pytest.mark.parametrize("query", [
    {"query": {"bool": {"filter": [{"script": {"script": "return true"}}]}}},
    {"script_fields": {"x": {"script": "1"}}},
    {"runtime_mappings": {"x": {"type": "long"}}},
    {"sort": [{"_script": {"type": "number", "script": "1"}}]},
    {"sort": ["_script"]},
])
def test_scripts_are_rejected_even_inside_nested_dsl(query):
    with pytest.raises(ValueError):
        prepare_raw_query(query)


def test_raw_size_and_recursion_are_bounded():
    with pytest.raises(ValueError, match="64 KiB"):
        prepare_raw_query({"query": {"term": {"x": "x" * 65536}}})
    cycle = {}
    cycle["query"] = cycle
    with pytest.raises(ValueError, match="profundidade"):
        prepare_raw_query(cycle)


def test_pagination_boundaries_are_permitted():
    assert prepare_raw_query({"size": 100, "from": 9900})["from"] == 9900
    query = prepare_raw_query({"from": 0, "search_after": [None, "id", 1.2, True]})
    assert query["search_after"] == [None, "id", 1.2, True]


def test_movement_uses_documented_tpu_field_and_combines_with_subject():
    assert build_query(movimento=26)["query"] == {"match": {"movimentos.codigo": 26}}
    assert build_query(movimento="26", assunto=123)["query"]["bool"]["filter"] == [
        {"match": {"assuntos.codigo": 123}}, {"match": {"movimentos.codigo": 26}},
    ]


@pytest.mark.parametrize("movement", [True, 0, -1, 1.5, "text", "٢٦"])
def test_movement_rejects_invalid_tpu_codes(movement):
    with pytest.raises(ValueError, match="movimento"):
        build_query(movimento=movement)


def test_builder_also_enforces_cnj_checksum():
    with pytest.raises(ValueError, match="verificador"):
        build_query(processo="0040943-54.1996.8.26.0114")
