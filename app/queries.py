"""Small query builder and bounded, read-only Query DSL envelope."""

from copy import deepcopy
from datetime import date, datetime, timedelta
import json
import math
import re
from typing import Any

from app.cnj import normalize_cnj

MAX_QUERY_BYTES = 64 * 1024
DEFAULT_SORT = [{"@timestamp": {"order": "asc"}}]
_ALLOWED_KEYS = {"query", "size", "sort", "search_after", "from", "track_total_hits"}
_FORBIDDEN_KEYS = {"script", "script_fields", "runtime_mappings", "_script"}


def _validate_json(value: Any, *, depth: int = 0) -> None:
    # Also bounds recursive or cyclic Python objects before deepcopy/serialization.
    if depth > 64:
        raise ValueError("Query excede a profundidade máxima de 64 níveis.")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("Chaves da query devem ser texto.")
            if key in _FORBIDDEN_KEYS:
                raise ValueError("Scripts e campos calculados não são permitidos.")
            _validate_json(child, depth=depth + 1)
    elif isinstance(value, list):
        for child in value:
            _validate_json(child, depth=depth + 1)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NaN e Infinity não são permitidos na query.")
    elif value is not None and not isinstance(value, (str, int, bool)):
        raise ValueError("Query deve conter apenas valores JSON.")


def _check_bytes(query: dict) -> None:
    try:
        size = len(json.dumps(query, allow_nan=False, separators=(",", ":")).encode("utf-8"))
    except (ValueError, TypeError, OverflowError, RecursionError):
        raise ValueError("Query não é JSON válido.") from None
    if size > MAX_QUERY_BYTES:
        raise ValueError("Query excede o limite de 64 KiB.")


def prepare_raw_query(query: dict) -> dict:
    """Copy and validate every outgoing query without executing arbitrary scripts."""
    if not isinstance(query, dict):
        raise ValueError("Query DSL deve ser um objeto JSON.")
    _validate_json(query)
    _check_bytes(query)
    if set(query) - _ALLOWED_KEYS:
        raise ValueError("Campo de envelope não permitido na query DSL.")
    prepared = deepcopy(query)
    prepared.setdefault("query", {"match_all": {}})
    prepared.setdefault("size", 10)
    prepared.setdefault("sort", deepcopy(DEFAULT_SORT))
    if not isinstance(prepared["query"], dict) or not prepared["query"]:
        raise ValueError("query deve ser um objeto DSL não vazio.")
    size = prepared["size"]
    if type(size) is not int or not 1 <= size <= 100:
        raise ValueError("size deve ser um inteiro entre 1 e 100.")
    offset = prepared.get("from", 0)
    if type(offset) is not int or not 0 <= offset <= 9900 or offset + size > 10000:
        raise ValueError("from deve estar entre 0 e 9900, com from + size <= 10000.")
    sort = prepared["sort"]
    sort_items = sort if isinstance(sort, list) else [sort]
    if not sort_items or any(
        not isinstance(item, (str, dict)) or not item or item == "_script" for item in sort_items
    ):
        raise ValueError("sort deve conter campos de ordenação não vazios.")
    if "search_after" in prepared:
        cursor = prepared["search_after"]
        if (
            not isinstance(cursor, list)
            or not cursor
            or any(isinstance(item, (dict, list)) for item in cursor)
        ):
            raise ValueError("search_after deve ser um array não vazio de valores escalares.")
        if offset != 0:
            raise ValueError("search_after não pode ser combinado com from diferente de zero.")
    if "track_total_hits" in prepared:
        total = prepared["track_total_hits"]
        if total is False:
            raise ValueError("track_total_hits=false não é suportado: o total deve acompanhar a evidência.")
        if type(total) is not bool and (type(total) is not int or total < 0):
            raise ValueError("track_total_hits deve ser booleano ou inteiro não negativo.")
    _check_bytes(prepared)
    return prepared


def _parse_date(value: date | str, name: str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError(f"{name} deve ser uma data ISO válida (YYYY-MM-DD).")


def _code(value: int | str, name: str) -> int:
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        try:
            parsed = int(value)
        except ValueError:
            raise ValueError(f"{name} deve ser um código inteiro positivo.") from None
        if parsed > 0:
            return parsed
    raise ValueError(f"{name} deve ser um código inteiro positivo.")


def build_query(
    *,
    processo: str | None = None,
    classe: int | str | None = None,
    assunto: int | str | None = None,
    movimento: int | str | None = None,
    date_from: date | str | None = None,
    date_to: date | str | None = None,
    size: int = 10,
    search_after: list | None = None,
) -> dict:
    filters: list[dict] = []
    if processo is not None:
        filters.append({"match": {"numeroProcesso": normalize_cnj(processo)}})
    if classe is not None:
        filters.append({"match": {"classe.codigo": _code(classe, "classe")}})
    if assunto is not None:
        filters.append({"match": {"assuntos.codigo": _code(assunto, "assunto")}})
    if movimento is not None:
        filters.append({"match": {"movimentos.codigo": _code(movimento, "movimento")}})
    start = _parse_date(date_from, "date_from") if date_from is not None else None
    end = _parse_date(date_to, "date_to") if date_to is not None else None
    if start is not None and end is not None and start > end:
        raise ValueError("date_from não pode ser posterior a date_to.")
    if start is not None or end is not None:
        bounds = {}
        if start is not None:
            bounds["gte"] = f"{start.isoformat()}T00:00:00Z"
        if end is not None:
            try:
                next_day = end + timedelta(days=1)
            except OverflowError:
                raise ValueError("date_to deve permitir calcular o dia seguinte.") from None
            bounds["lt"] = f"{next_day.isoformat()}T00:00:00Z"
        filters.append({"range": {"dataAjuizamento": bounds}})
    clause = {"match_all": {}} if not filters else filters[0]
    if len(filters) > 1:
        clause = {"bool": {"filter": filters}}
    query: dict = {"query": clause, "size": size}
    if search_after is not None:
        query["search_after"] = search_after
    return prepare_raw_query(query)
