from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace

import pytest

from app.storage import Storage


def save(storage, raw=b'{ "hits": {"hits": []} }\r\n', **overrides):
    args = {
        "tribunal": "TJSP",
        "endpoint_alias": "api_publica_tjsp",
        "endpoint": "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search",
        "query": {"query": {"match_all": {}}, "size": 1},
        "retrieved_at": "2026-09-21T12:30:45.123456Z",
    }
    args.update(overrides)
    return storage.save_raw(raw, **args)


def test_raw_preserves_exact_bytes_and_hash_with_provenance(tmp_path):
    directory = tmp_path / "new" / "data"
    raw = b'\xef\xbb\xbf{ "text": "a\\nb", "unknown": [ 1,2 ] }\r\n'
    query = {"query": {"match": {"classe.codigo": 436}}, "size": 1}
    stored = save(Storage(directory), raw, query=query)

    assert stored.raw_path.read_bytes() == raw
    assert stored.provenance["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert stored.provenance["source"] == "CNJ/DataJud"
    assert stored.provenance["tribunal"] == "TJSP"
    assert stored.provenance["endpoint_alias"] == "api_publica_tjsp"
    assert stored.provenance["endpoint"].endswith("/api_publica_tjsp/_search")
    assert stored.provenance["retrieved_at"] == "2026-09-21T12:30:45.123456Z"
    assert directory / stored.provenance["raw_file"] == stored.raw_path
    assert stored.extracted_path.parent.is_dir()
    assert not stored.extracted_path.exists()
    query["query"]["match"]["classe.codigo"] = 999
    assert stored.provenance["query"]["query"]["match"]["classe.codigo"] == 436


def test_repeated_retrieval_never_overwrites(tmp_path):
    storage = Storage(tmp_path)
    first, second = save(storage), save(storage)
    assert first.raw_path != second.raw_path
    assert first.extracted_path != second.extracted_path
    assert first.raw_path.read_bytes() == second.raw_path.read_bytes()
    assert first.provenance["raw_sha256"] == second.provenance["raw_sha256"]
    assert len(list((tmp_path / "raw").glob("*.json"))) == 4  # Raw files and their sidecars.


def test_nonce_collision_retries_without_overwriting(tmp_path, monkeypatch):
    nonces = iter([SimpleNamespace(hex="a"), SimpleNamespace(hex="a"), SimpleNamespace(hex="b")])
    monkeypatch.setattr("app.storage.uuid4", lambda: next(nonces))
    first = save(Storage(tmp_path))
    second = save(Storage(tmp_path))
    assert first.raw_path != second.raw_path
    assert first.raw_path.read_bytes() == second.raw_path.read_bytes()


def test_extracted_json_has_provenance_and_refuses_overwrite(tmp_path):
    storage = Storage(tmp_path)
    stored = save(storage)
    document = {"results": [{"classe": {"nome": "Execução"}}], "provenance": stored.provenance}
    result = storage.save_extracted(stored, document)
    assert result == stored.extracted_path
    assert json.loads(result.read_text(encoding="utf-8")) == document
    with pytest.raises(FileExistsError):
        storage.save_extracted(stored, {"changed": True})
    assert json.loads(result.read_text(encoding="utf-8")) == document


@pytest.mark.parametrize("tribunal", ["../TJSP", "..\\TJSP", "C:\\TJSP", "/TJSP", "TJSP/../../x", "TJSP:ads", "", "TJSP\x00"])
def test_unsafe_tribunal_cannot_be_used_as_path(tmp_path, tribunal):
    with pytest.raises(ValueError):
        save(Storage(tmp_path / "data"), tribunal=tribunal)
    assert not (tmp_path / "data").exists()


def test_extracted_path_must_stay_in_storage(tmp_path):
    storage = Storage(tmp_path / "data")
    stored = save(storage)
    outside = tmp_path / "escape.json"
    with pytest.raises(ValueError):
        storage.save_extracted(replace(stored, extracted_path=outside), {"test": True})
    assert not outside.exists()


def test_storage_rejects_directory_symlink_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    try:
        (data / "raw").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating directory symlinks is not permitted on this host.")
    with pytest.raises(ValueError):
        save(Storage(data))
    assert not list(outside.iterdir())


def test_timestamp_is_normalized_to_utc(tmp_path):
    stored = save(Storage(tmp_path), retrieved_at="2026-09-21T09:30:45-03:00")
    assert stored.provenance["retrieved_at"] == "2026-09-21T12:30:45Z"
    assert "20260921T123045000000Z" in stored.raw_path.name


@pytest.mark.parametrize("timestamp", ["2026-09-21", "2026-09-21T12:30:00", "../bad", None])
def test_timestamp_requires_valid_timezone(tmp_path, timestamp):
    with pytest.raises(ValueError):
        save(Storage(tmp_path), retrieved_at=timestamp)


def test_io_failure_is_explicit(tmp_path):
    occupied = tmp_path / "data"
    occupied.write_bytes(b"not a directory")
    with pytest.raises(OSError):
        save(Storage(occupied))


def test_invalid_extracted_json_does_not_create_a_file(tmp_path):
    storage = Storage(tmp_path)
    stored = save(storage)
    with pytest.raises(ValueError):
        storage.save_extracted(stored, {"value": float("nan")})
    assert not stored.extracted_path.exists()


def sidecar(stored):
    return stored.raw_path.with_name(stored.raw_path.name + ".provenance.json")


def test_raw_sidecar_persists_original_provenance_before_extraction(tmp_path):
    stored = save(Storage(tmp_path))
    assert json.loads(sidecar(stored).read_text(encoding="utf-8")) == stored.provenance
    assert not stored.extracted_path.exists()


def test_electoral_tribunal_uses_its_official_hyphenated_alias(tmp_path):
    stored = save(
        Storage(tmp_path), tribunal="TRE-SP", endpoint_alias="api_publica_tre-sp",
        endpoint="https://api-publica.datajud.cnj.jus.br/api_publica_tre-sp/_search",
    )
    assert stored.raw_path.name.startswith("TRE-SP_")
    assert stored.provenance["tribunal"] == "TRE-SP"
    assert Storage(tmp_path).load_raw(stored.raw_path)[1].provenance == stored.provenance


def test_offline_load_preserves_raw_original_metadata_and_previous_extractions(tmp_path):
    storage = Storage(tmp_path)
    original = save(storage)
    storage.save_extracted(original, {"first": True})
    raw_before, provenance_before = original.raw_path.read_bytes(), sidecar(original).read_bytes()

    raw, loaded = storage.load_raw(original.raw_path)
    assert raw == raw_before
    assert loaded.raw_path == original.raw_path
    assert loaded.provenance == original.provenance
    assert loaded.extracted_path != original.extracted_path
    storage.save_extracted(loaded, {"reextracted": True})
    _, again = storage.load_raw(original.raw_path)
    assert again.extracted_path not in (original.extracted_path, loaded.extracted_path)
    assert not again.extracted_path.exists()
    assert original.raw_path.read_bytes() == raw_before
    assert sidecar(original).read_bytes() == provenance_before
    assert json.loads(original.extracted_path.read_text()) == {"first": True}
    assert json.loads(loaded.extracted_path.read_text()) == {"reextracted": True}


def test_offline_load_detects_altered_raw_bytes(tmp_path):
    storage = Storage(tmp_path)
    stored = save(storage)
    stored.raw_path.write_bytes(stored.raw_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA256"):
        storage.load_raw(stored.raw_path)


def test_offline_load_requires_original_sidecar_even_if_extracted_file_exists(tmp_path):
    storage = Storage(tmp_path)
    stored = save(storage)
    storage.save_extracted(stored, {"provenance": stored.provenance})
    sidecar(stored).unlink()
    with pytest.raises(ValueError, match="sidecar is required"):
        storage.load_raw(stored.raw_path)


@pytest.mark.parametrize(("field", "replacement"), [
    ("source", "invented"), ("tribunal", "UNKNOWN"), ("tribunal", "tjsp"),
    ("endpoint_alias", "api_publica_stj"),
    ("endpoint", "https://secret@api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search"),
    ("query", []), ("raw_sha256", "invalid"), ("raw_sha256", "0" * 64),
    ("raw_file", "../../outside.json"), ("raw_file", "raw/another-file.json"),
    ("retrieved_at", "2026-09-21T12:00:00"),
    ("retrieved_at", "2026-09-21T12:00:00-03:00"),
])
def test_offline_load_validates_original_metadata(tmp_path, field, replacement):
    storage = Storage(tmp_path)
    stored = save(storage)
    metadata = dict(stored.provenance)
    metadata[field] = replacement
    sidecar(stored).write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError):
        storage.load_raw(stored.raw_path)


@pytest.mark.parametrize("content", ["not json", "null", "[]", "{}", "{\"x\":NaN}", "{\"x\":1,\"x\":2}"])
def test_offline_load_rejects_malformed_sidecar(tmp_path, content):
    storage = Storage(tmp_path)
    stored = save(storage)
    sidecar(stored).write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        storage.load_raw(stored.raw_path)


def test_offline_sidecar_must_not_add_authentication_fields(tmp_path):
    storage = Storage(tmp_path)
    stored = save(storage)
    metadata = {**stored.provenance, "Authorization": "not-a-real-secret"}
    sidecar(stored).write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="expected metadata"):
        storage.load_raw(stored.raw_path)


def test_offline_load_rejects_files_outside_raw_directory_and_sidecars(tmp_path):
    storage = Storage(tmp_path / "data")
    stored = save(storage)
    outside = tmp_path / "outside.json"
    outside.write_bytes(stored.raw_path.read_bytes())
    for path in (outside, stored.extracted_path, sidecar(stored)):
        with pytest.raises(ValueError, match="data_dir/raw"):
            storage.load_raw(path)


def test_mismatched_endpoint_cannot_be_persisted(tmp_path):
    with pytest.raises(ValueError, match="registry"):
        save(Storage(tmp_path), endpoint="https://example.invalid/_search?api_key=secret")
    assert not (tmp_path / "raw").exists()


def test_invalid_query_json_is_rejected_before_raw_write(tmp_path):
    with pytest.raises(ValueError):
        save(Storage(tmp_path), query={"size": float("inf")})
    assert not (tmp_path / "raw").exists()


def test_manifest_preserves_document_and_repetitions_are_exclusive(tmp_path):
    storage = Storage(tmp_path / "new" / "data")
    document = {"results": [{"tribunal": "TJSP"}], "discovery": {"query_id": "abc"}}
    first = storage.save_manifest(document, prefix="discovery_TJSP")
    second = storage.save_manifest(document, prefix="discovery_TJSP")
    assert first != second
    assert first.parent == storage.data_dir / "extracted"
    assert first.name.startswith("discovery_TJSP_")
    assert json.loads(first.read_text(encoding="utf-8")) == document
    assert first.read_bytes() == second.read_bytes()
    assert document == {"results": [{"tribunal": "TJSP"}], "discovery": {"query_id": "abc"}}


@pytest.mark.parametrize("prefix", ["../escape", "..\\escape", "/absolute", "C:\\absolute", "file:stream", "", "a" * 49, None])
def test_manifest_prefix_rejects_paths_and_unbounded_names(tmp_path, prefix):
    with pytest.raises(ValueError, match="Manifest prefix"):
        Storage(tmp_path).save_manifest({"result": True}, prefix=prefix)
    assert not (tmp_path / "extracted").exists()
