import pytest

from app.tribunals import BASE_URL, TRIBUNALS, resolve_tribunal


@pytest.mark.parametrize("tribunal,alias", [
    (" tjsp ", "api_publica_tjsp"), ("STJ", "api_publica_stj"),
    ("TST", "api_publica_tst"), ("TSE", "api_publica_tse"),
    ("STM", "api_publica_stm"), ("TRE-DF", "api_publica_tre-dft"),
    ("TRF6", "api_publica_trf6"), ("TRT24", "api_publica_trt24"),
    ("TJDFT", "api_publica_tjdft"), ("TJMRS", "api_publica_tjmrs"),
])
def test_documented_aliases_and_case_normalization(tribunal, alias):
    assert resolve_tribunal(tribunal) == (
        tribunal.strip().upper(), alias, f"{BASE_URL}/{alias}/_search",
    )


def test_registry_has_only_fixed_search_endpoints():
    assert len(TRIBUNALS) == 91
    assert len(set(TRIBUNALS.values())) == len(TRIBUNALS)
    for tribunal in TRIBUNALS:
        _, alias, url = resolve_tribunal(tribunal)
        assert alias.startswith("api_publica_")
        assert url.startswith("https://api-publica.datajud.cnj.jus.br/api_publica_")
        assert url.endswith("/_search")


@pytest.mark.parametrize("tribunal", [
    "", "UNKNOWN", "TRF7", "TRT25", "TJSP/_delete", "../TJSP",
    "https://example.org", None, 12,
])
def test_unknown_tribunal_cannot_override_endpoint(tribunal):
    with pytest.raises(ValueError):
        resolve_tribunal(tribunal)
