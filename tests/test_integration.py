"""Explicitly enabled, minimal live test against the official CNJ endpoint."""

import hashlib
import json
import os
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("DATAJUD_INTEGRATION_TEST") != "1",
        reason="Opt in with DATAJUD_INTEGRATION_TEST=1 (fetches the official public key)",
    ),
]


def test_live_tjsp_preserves_raw_and_provenance(tmp_path: Path) -> None:
    from app.config import Settings
    from app.core import DataJudService
    from app.models import SearchRequest

    result = DataJudService(
        Settings(auth_mode="auto", data_dir=tmp_path)
    ).search(SearchRequest(tribunal="TJSP", size=1))

    assert result["query_status"] == "success"
    assert result["count"] == len(result["results"])
    assert 0 <= result["count"] <= 1
    raw_path = Path(result["raw_path"])
    extracted_path = Path(result["extracted_path"])
    raw = raw_path.read_bytes()
    assert json.loads(raw)["hits"]["hits"] is not None
    assert json.loads(extracted_path.read_text(encoding="utf-8")) == result
    provenance = result["provenance"]
    assert provenance["raw_sha256"] == hashlib.sha256(raw).hexdigest()
    assert provenance["source"] == "CNJ/DataJud"
    assert provenance["tribunal"] == "TJSP"
    assert provenance["endpoint_alias"] == "api_publica_tjsp"
    assert provenance["retrieved_at"].endswith("Z")
    assert provenance["query"]["size"] == 1
    for item in result["results"]:
        assert item["provenance"]["raw_sha256"] == provenance["raw_sha256"]
