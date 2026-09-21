"""Local evidence files: original bytes, explicit provenance, no overwrites."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from app.tribunals import resolve_tribunal


_PROVENANCE_FIELDS = {
    "source", "tribunal", "endpoint_alias", "endpoint", "retrieved_at", "query",
    "raw_sha256", "raw_file",
}


def _instant(value: str) -> datetime:
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        raise ValueError("retrieved_at must be an ISO timestamp with timezone.") from None
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("retrieved_at must include a timezone.")
    return instant


def _json_bytes(document: dict) -> bytes:
    if not isinstance(document, dict):
        raise ValueError("The evidence document must be an object.")
    return (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _sidecar_path(raw_path: Path) -> Path:
    return raw_path.with_name(raw_path.name + ".provenance.json")


def _read_provenance(path: Path) -> dict:
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("Duplicate provenance field.")
            value[key] = item
        return value

    def invalid_constant(_value):
        raise ValueError("Non-finite provenance value.")

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=invalid_constant,
        )
    except FileNotFoundError:
        raise ValueError("Original provenance sidecar is required for offline extraction.") from None
    except (ValueError, UnicodeError):
        raise ValueError("Invalid original provenance sidecar.") from None
    if not isinstance(value, dict) or set(value) != _PROVENANCE_FIELDS:
        raise ValueError("Original provenance must contain exactly the expected metadata fields.")
    return value


@dataclass(frozen=True)
class StoredRaw:
    raw_path: Path
    extracted_path: Path
    provenance: dict


class Storage:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir).resolve()

    def _directory(self, name: str) -> Path:
        directory = self.data_dir / name
        if not directory.resolve().is_relative_to(self.data_dir):
            raise ValueError("Evidence directory must remain inside data_dir.")
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def save_raw(
        self,
        raw_bytes: bytes,
        *,
        tribunal: str,
        endpoint_alias: str,
        endpoint: str,
        query: dict,
        retrieved_at: str,
    ) -> StoredRaw:
        if not isinstance(raw_bytes, bytes):
            raise TypeError("Raw evidence must be bytes.")
        normalized, expected_alias, expected_endpoint = resolve_tribunal(tribunal)
        if endpoint_alias != expected_alias or endpoint != expected_endpoint:
            raise ValueError("Evidence endpoint and alias must match the tribunal registry.")
        if not isinstance(query, dict):
            raise ValueError("The recorded query must be an object.")
        instant = _instant(retrieved_at).astimezone(timezone.utc)
        timestamp = instant.isoformat().replace("+00:00", "Z")
        digest = hashlib.sha256(raw_bytes).hexdigest()
        provenance = {
            "source": "CNJ/DataJud",
            "tribunal": normalized,
            "endpoint_alias": endpoint_alias,
            "endpoint": endpoint,
            "retrieved_at": timestamp,
            "query": deepcopy(query),
            "raw_sha256": digest,
        }
        # Validate serializability before writing any evidence files.
        _json_bytes(provenance)
        raw_directory = self._directory("raw")
        extracted_directory = self._directory("extracted")
        prefix = f"{normalized}_{instant:%Y%m%dT%H%M%S%fZ}_{digest}"

        # Exclusive creation is authoritative even if a nonce ever collides.
        for _ in range(10):
            filename = f"{prefix}_{uuid4().hex}.json"
            raw_path = raw_directory / filename
            sidecar = _sidecar_path(raw_path)
            if sidecar.exists():
                continue
            try:
                with raw_path.open("xb") as output:
                    output.write(raw_bytes)
            except FileExistsError:
                continue
            provenance["raw_file"] = raw_path.relative_to(self.data_dir).as_posix()
            try:
                with sidecar.open("xb") as output:
                    output.write(_json_bytes(provenance))
            except FileExistsError:
                # This raw was created by this invocation; a concurrent sidecar
                # must never be attached to it or overwritten.
                raw_path.unlink()
                continue
            break
        else:
            raise FileExistsError("Could not allocate a unique evidence filename.")

        return StoredRaw(raw_path, extracted_directory / filename, provenance)

    def load_raw(self, raw_file: Path) -> tuple[bytes, StoredRaw]:
        """Verify a saved retrieval and allocate a new output path, without network I/O."""
        supplied = Path(raw_file)
        raw_path = supplied.resolve()
        raw_directory = (self.data_dir / "raw").resolve()
        if (
            supplied.is_symlink()
            or not raw_directory.is_relative_to(self.data_dir)
            or raw_path.parent != raw_directory
            or raw_path.suffix != ".json"
            or raw_path.name.endswith(".provenance.json")
        ):
            raise ValueError("Raw evidence must be a JSON file in data_dir/raw.")
        sidecar = _sidecar_path(raw_path)
        if sidecar.is_symlink() or sidecar.resolve().parent != raw_directory:
            raise ValueError("Provenance sidecar must remain beside its raw evidence.")
        provenance = _read_provenance(sidecar)
        normalized, alias, endpoint = resolve_tribunal(provenance["tribunal"])
        if (
            provenance["source"] != "CNJ/DataJud"
            or provenance["tribunal"] != normalized
            or provenance["endpoint_alias"] != alias
            or provenance["endpoint"] != endpoint
            or not isinstance(provenance["query"], dict)
            or provenance["raw_file"] != raw_path.relative_to(self.data_dir).as_posix()
            or not isinstance(provenance["raw_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", provenance["raw_sha256"])
        ):
            raise ValueError("Original provenance metadata does not match this DataJud retrieval.")
        instant = _instant(provenance["retrieved_at"])
        if instant.utcoffset().total_seconds() != 0:
            raise ValueError("Original provenance timestamp must be UTC.")
        raw_bytes = raw_path.read_bytes()
        if hashlib.sha256(raw_bytes).hexdigest() != provenance["raw_sha256"]:
            raise ValueError("Raw evidence SHA256 does not match its original provenance.")
        directory = self._directory("extracted")
        prefix = f"{normalized}_{instant:%Y%m%dT%H%M%S%fZ}_{provenance['raw_sha256']}_extract"
        for _ in range(10):
            extracted_path = directory / f"{prefix}_{uuid4().hex}.json"
            if not extracted_path.exists():
                return raw_bytes, StoredRaw(raw_path, extracted_path, provenance)
        raise FileExistsError("Could not allocate a unique extraction filename.")

    def save_extracted(self, stored: StoredRaw, document: dict) -> Path:
        directory = self._directory("extracted").resolve()
        path = stored.extracted_path
        if path.parent.resolve() != directory or path.is_symlink():
            raise ValueError("Extracted evidence must remain in data_dir/extracted.")
        content = _json_bytes(document)
        with path.open("xb") as output:
            output.write(content)
        return path

    def save_manifest(self, document: dict, *, prefix: str) -> Path:
        if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,47}", prefix):
            raise ValueError("Manifest prefix must be 1..48 safe letters, digits, underscores or hyphens.")
        content = _json_bytes(document)
        directory = self._directory("extracted")
        instant = datetime.now(timezone.utc)
        for _ in range(10):
            path = directory / f"{prefix}_{instant:%Y%m%dT%H%M%S%fZ}_{uuid4().hex}.json"
            try:
                with path.open("xb") as output:
                    output.write(content)
            except FileExistsError:
                continue
            return path
        raise FileExistsError("Could not allocate a unique manifest filename.")
