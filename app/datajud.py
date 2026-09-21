"""Synchronous DataJud HTTP client, independent of CLI, HTTP API and storage."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import time
from typing import Any

import httpx

from app.config import Settings
from app.public_key import (
    PublicKeyError, fetch_public_key, retry_delay as _retry_delay,
    RETRY_STATUSES as _RETRY_STATUSES, TRANSIENT_ERRORS as _TRANSIENT_ERRORS,
)
from app.queries import prepare_raw_query
from app.tribunals import resolve_tribunal

logger = logging.getLogger(__name__)


@dataclass
class Retrieval:
    raw_bytes: bytes
    payload: Any
    tribunal: str
    endpoint_alias: str
    endpoint: str
    query: dict
    retrieved_at: str


class DataJudError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 502,
        *,
        upstream_status: int | None = None,
        retrieval: Retrieval | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.upstream_status = upstream_status
        self.retrieval = retrieval


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _validate_response(payload: Any) -> int:
    """Return hit count; invalid or partial evidence never becomes an empty result."""
    if not isinstance(payload, dict) or not isinstance(payload.get("hits"), dict):
        raise ValueError("Resposta DataJud não contém hits válidos.")
    hits = payload["hits"]
    records = hits.get("hits")
    if not isinstance(records, list) or any(
        not isinstance(hit, dict) or not isinstance(hit.get("_source"), dict)
        for hit in records
    ):
        raise ValueError("Resposta DataJud contém registros inválidos.")
    total = hits.get("total")
    if isinstance(total, dict):
        if not _nonnegative_int(total.get("value")) or total.get("relation") not in ("eq", "gte"):
            raise ValueError("Resposta DataJud contém total inválido.")
    elif not _nonnegative_int(total):
        raise ValueError("Resposta DataJud não contém total válido.")
    if type(payload.get("timed_out")) is not bool:
        raise ValueError("Resposta DataJud não contém timed_out válido.")
    shards = payload.get("_shards")
    if not isinstance(shards, dict) or not _nonnegative_int(shards.get("failed")):
        raise ValueError("Resposta DataJud não contém estado válido dos shards.")
    return len(records)


class _PartialResponseError(ValueError):
    """Internal distinction so the HTTP client can retain its stable error code."""


def validate_response(payload: Any) -> int:
    """Validate both response shape and completeness, also for offline extraction."""
    count = _validate_response(payload)
    if payload["timed_out"] or payload["_shards"]["failed"]:
        raise _PartialResponseError("DataJud retornou uma resposta parcial; a consulta não foi concluída.")
    return count


def _reject_constant(_value: str) -> None:
    raise ValueError("JSON não finito.")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON contém chaves duplicadas.")
        result[key] = value
    return result


class DataJudClient:
    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = settings
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        self._client = httpx.Client(
            headers=headers,
            timeout=settings.timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "DataJudClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    @staticmethod
    def _log(tribunal: str, status: int | None, started: float, hits: int | None) -> None:
        logger.info(
            "tribunal=%s operation=search status=%s duration_ms=%.1f hits=%s",
            tribunal, status, (time.monotonic() - started) * 1000, hits,
        )

    def search(self, tribunal: str, query: dict) -> Retrieval:
        normalized, alias, endpoint = resolve_tribunal(tribunal)
        prepared = prepare_raw_query(query)
        key = self._resolve_key()
        # The POST retry budget is shared across the initial and refreshed key.
        # Auto: <= max_retries+2 POSTs and <= 2*(max_retries+1) GETs per search.
        # Manual: <= max_retries+1 POSTs, no GET, no auth refresh.
        transient_retries = 0
        refreshed = False
        while True:
            started = time.monotonic()
            try:
                response = self._client.post(endpoint, json=prepared, headers={"Authorization": f"APIKey {key}"})
            except httpx.RequestError as exc:
                self._log(normalized, None, started, None)
                if isinstance(exc, _TRANSIENT_ERRORS) and transient_retries < self.settings.max_retries:
                    time.sleep(_retry_delay(transient_retries))
                    transient_retries += 1
                    continue
                if isinstance(exc, httpx.TimeoutException):
                    raise DataJudError("timeout", "DataJud excedeu o tempo limite da consulta.", 504) from None
                raise DataJudError("connection_error", "Não foi possível conectar ao DataJud.", 503) from None
            status = response.status_code
            if not 200 <= status < 300:
                self._log(normalized, status, started, None)
                if status in _RETRY_STATUSES and transient_retries < self.settings.max_retries:
                    time.sleep(_retry_delay(transient_retries, response.headers.get("Retry-After")))
                    transient_retries += 1
                    continue
                if status in (401, 403):
                    if self.settings.auth_mode == "auto" and not refreshed:
                        refreshed = True
                        key = self._resolve_key()
                        continue
                    raise DataJudError(
                        "authentication_error", "DataJud recusou a credencial configurada.",
                        upstream_status=status,
                    )
                raise DataJudError("upstream_error", "DataJud retornou erro HTTP.", upstream_status=status)
            retrieval = Retrieval(
                raw_bytes=response.content,
                payload=None,
                tribunal=normalized,
                endpoint_alias=alias,
                endpoint=endpoint,
                query=prepared,
                retrieved_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
            try:
                retrieval.payload = json.loads(
                    retrieval.raw_bytes,
                    parse_constant=_reject_constant,
                    object_pairs_hook=_unique_object,
                )
            except (ValueError, UnicodeError, RecursionError):
                self._log(normalized, status, started, None)
                raise DataJudError(
                    "invalid_json", "DataJud retornou JSON inválido.",
                    upstream_status=status, retrieval=retrieval,
                ) from None
            try:
                count = validate_response(retrieval.payload)
            except _PartialResponseError:
                self._log(normalized, status, started, len(retrieval.payload["hits"]["hits"]))
                raise DataJudError(
                    "partial_response", "DataJud retornou uma resposta parcial; a consulta não foi concluída.",
                    upstream_status=status, retrieval=retrieval,
                ) from None
            except ValueError:
                self._log(normalized, status, started, None)
                raise DataJudError(
                    "invalid_response", "DataJud retornou uma resposta com formato inesperado.",
                    upstream_status=status, retrieval=retrieval,
                ) from None
            self._log(normalized, status, started, count)
            return retrieval

    def _resolve_key(self) -> str:
        if self.settings.auth_mode == "manual":
            if not self.settings.api_key:
                raise DataJudError("configuration_error", "Configure DATAJUD_API_KEY no modo manual.", 503)
            return self.settings.api_key
        try:
            return fetch_public_key(self._client, max_retries=self.settings.max_retries)
        except PublicKeyError as exc:
            raise DataJudError(exc.code, str(exc), exc.status_code, upstream_status=exc.upstream_status) from None
