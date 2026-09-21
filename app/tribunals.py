"""Registry checked against the CNJ endpoint documentation on 2026-09-21.

Source: https://datajud-wiki.cnj.jus.br/api-publica/endpoints/
"""

BASE_URL = "https://api-publica.datajud.cnj.jus.br"

_STATES = (
    "AC", "AL", "AM", "AP", "BA", "CE", "ES", "GO", "MA", "MG", "MS", "MT",
    "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE",
    "SP", "TO",
)

TRIBUNALS: dict[str, str] = {
    **{name: f"api_publica_{name.lower()}" for name in ("TST", "TSE", "STJ", "STM")},
    **{f"TRF{n}": f"api_publica_trf{n}" for n in range(1, 7)},
    **{f"TJ{state}": f"api_publica_tj{state.lower()}" for state in _STATES},
    "TJDFT": "api_publica_tjdft",
    **{f"TRT{n}": f"api_publica_trt{n}" for n in range(1, 25)},
    **{f"TRE-{state}": f"api_publica_tre-{state.lower()}" for state in _STATES},
    # CNJ documents the Distrito Federal alias with a trailing 't'.
    "TRE-DF": "api_publica_tre-dft",
    **{f"TJM{state}": f"api_publica_tjm{state.lower()}" for state in ("MG", "RS", "SP")},
}


def resolve_tribunal(tribunal: str) -> tuple[str, str, str]:
    if not isinstance(tribunal, str):
        raise ValueError("Tribunal deve ser uma sigla do registry.")
    normalized = tribunal.strip().upper()
    if normalized not in TRIBUNALS:
        raise ValueError("Tribunal desconhecido; consulte as siglas disponíveis no registry.")
    alias = TRIBUNALS[normalized]
    return normalized, alias, f"{BASE_URL}/{alias}/_search"
