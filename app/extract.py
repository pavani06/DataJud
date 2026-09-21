"""Normalize DataJud hits without changing or discarding their source fields."""

from __future__ import annotations

from copy import deepcopy


_FIELDS = {
    "numeroProcesso": "numero_processo",
    "orgaoJulgador": "orgao_julgador",
    "dataAjuizamento": "data_ajuizamento",
    "dataHoraUltimaAtualizacao": "data_hora_ultima_atualizacao",
    "@timestamp": "timestamp",
    "nivelSigilo": "nivel_sigilo",
    **{name: name for name in (
        "classe", "assuntos", "movimentos", "grau", "tribunal", "sistema", "formato", "id"
    )},
}


def _flatten_subjects(value: list) -> list:
    # An explicit stack also handles deeply nested API arrays without recursion.
    flattened = []
    pending = list(reversed(value))
    while pending:
        item = pending.pop()
        if isinstance(item, list):
            pending.extend(reversed(item))
        else:
            flattened.append(deepcopy(item))
    return flattened


def extract_response(payload: dict, provenance: dict) -> list[dict]:
    """Return one independent normalized object per hit; malformed hits raise."""
    if not isinstance(payload, dict) or not isinstance(payload.get("hits"), dict):
        raise ValueError("DataJud response must contain a hits object.")
    hits = payload["hits"].get("hits")
    if not isinstance(hits, list):
        raise ValueError("DataJud response must contain a hits.hits array.")
    if not isinstance(provenance, dict):
        raise ValueError("Provenance must be an object.")

    results = []
    for hit in hits:
        if not isinstance(hit, dict) or not isinstance(hit.get("_source"), dict):
            raise ValueError("Each DataJud hit must contain a _source object.")
        record = {}
        extra_fields = {}
        for key, value in hit["_source"].items():
            if key not in _FIELDS:
                extra_fields[key] = deepcopy(value)
            elif key == "assuntos" and isinstance(value, list):
                record["assuntos"] = _flatten_subjects(value)
            else:
                record[_FIELDS[key]] = deepcopy(value)
        if extra_fields:
            record["extra_fields"] = extra_fields
        record_provenance = deepcopy(provenance)
        for source_key, destination_key in (
            ("_id", "datajud_id"), ("_index", "datajud_index")
        ):
            if source_key in hit:
                record_provenance[destination_key] = deepcopy(hit[source_key])
        record["provenance"] = record_provenance
        results.append(record)
    return results
