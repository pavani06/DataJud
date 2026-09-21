"""CNJ number validation and conservative inference of its court of origin.

Sources checked 2026-09-21:
https://atos.cnj.jus.br/atos/detalhar/119 (art. 1, including TRF6 amendment)
https://libra.tjpa.jus.br/libra/pages/downloads/rescnj_65.pdf (annexes I–VIII)

Origin does not establish the current court or every court handling an appeal.
"""

import re

from app.tribunals import TRIBUNALS

# This is the order in annexes IV/VI, not alphabetical order of the abbreviations.
_STATE_CODES = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SE", "SP", "TO",
)
_ORIGIN_COURTS = {
    **{("8", f"{n:02d}"): "TJDFT" if state == "DF" else f"TJ{state}"
       for n, state in enumerate(_STATE_CODES, start=1)},
    **{("6", f"{n:02d}"): f"TRE-{state}"
       for n, state in enumerate(_STATE_CODES, start=1)},
    **{("4", f"{n:02d}"): f"TRF{n}" for n in range(1, 7)},
    **{("5", f"{n:02d}"): f"TRT{n}" for n in range(1, 25)},
    ("3", "00"): "STJ", ("5", "00"): "TST", ("6", "00"): "TSE",
    ("7", "00"): "STM", ("9", "13"): "TJMMG", ("9", "21"): "TJMRS",
    ("9", "26"): "TJMSP",
}


def normalize_cnj(numero: str) -> str:
    """Accept the full ASCII number or exact CNJ mask, and validate MOD97 digits."""
    if not isinstance(numero, str) or not re.fullmatch(
        r"(?:[0-9]{20}|[0-9]{7}-[0-9]{2}\.[0-9]{4}\.[0-9]\.[0-9]{2}\.[0-9]{4})",
        numero,
    ):
        raise ValueError("Número CNJ deve ter 20 dígitos ou a máscara NNNNNNN-DD.AAAA.J.TR.OOOO.")
    normalized = re.sub(r"[^0-9]", "", numero)
    # Annex VIII III–IV: move DD to the end as 00, calculate 98 - remainder.
    expected = 98 - int(normalized[:7] + normalized[9:] + "00") % 97
    if int(normalized[7:9]) != expected:
        raise ValueError("Número CNJ possui dígito verificador inválido (Módulo 97).")
    return normalized


def infer_tribunal(numero: str) -> str:
    """Resolve only a documented, registered court of origin; never fan out."""
    number = normalize_cnj(numero)
    segment, court_code = number[13], number[14:16]
    tribunal = _ORIGIN_COURTS.get((segment, court_code))
    # Superior-court origin requires OOOO=0000 (art. 1 §6 III).
    if court_code == "00" and number[16:] != "0000":
        tribunal = None
    if tribunal is None or tribunal not in TRIBUNALS:
        raise ValueError("Não foi possível inferir um tribunal DataJud seguro; informe tribunal explicitamente.")
    return tribunal
