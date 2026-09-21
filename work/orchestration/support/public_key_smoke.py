"""Explicit live opt-in: one auto-authenticated search, then offline replay.

Run: uv run python work/orchestration/support/public_key_smoke.py --live
Neither the wiki HTML nor API key is written to output or evidence.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.core import DataJudService
from app.datajud import DataJudClient, DataJudError
from app.models import SearchRequest

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "work/orchestration/support/public-key-live-report.json"
WIKI = "https://datajud-wiki.cnj.jus.br/api-publica/acesso/"
ENDPOINT = "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    seen: list[dict] = []
    observed_keys: set[str] = set()
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "status": "running"}

    def observe(request):
        url = str(request.url)
        assert url in (WIKI, ENDPOINT), "Unexpected request target"
        header = request.headers.get("Authorization", "")
        if url == WIKI:
            assert request.method == "GET" and not header, "Unexpected wiki authorization"
        else:
            assert request.method == "POST" and header.startswith("APIKey "), "Missing API authorization"
            observed_keys.add(header.removeprefix("APIKey "))
        seen.append({"method": request.method, "url": url})

    try:
        settings = Settings(auth_mode="auto", api_key="", data_dir=ROOT / "data")
        with DataJudClient(settings) as client:
            client._client.event_hooks["request"].append(observe)
            result = DataJudService(settings, client).search(SearchRequest(tribunal="TJSP", size=1))
        assert result["query_status"] == "success" and 0 <= result["count"] <= 1
        assert seen[0] == {"method": "GET", "url": WIKI}
        assert any(item["method"] == "POST" for item in seen)
        raw_path = Path(result["raw_path"])
        raw = raw_path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == result["provenance"]["raw_sha256"]
        with patch("httpx.Client.send", side_effect=AssertionError("Offline replay attempted network")):
            offline = DataJudService(settings).extract_file(raw_path)
        assert offline["mode"] == "offline" and offline["results"] == result["results"]
        assert raw_path.read_bytes() == raw
        evidence = [raw_path, Path(str(raw_path) + ".provenance.json"), Path(result["extracted_path"]), Path(offline["extracted_path"])]
        for path in evidence:
            data = path.read_bytes()
            assert all(key.encode("ascii") not in data for key in observed_keys), "Credential in evidence"
        report.update(
            status="success", auth_mode="auto", configured_key=False,
            requests=seen, count=result["count"], raw_path=str(raw_path),
            extracted_path=result["extracted_path"], raw_sha256=result["provenance"]["raw_sha256"],
            offline_replay="passed", credential_absent_from_evidence=True,
        )
        code = 0
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__)
        if isinstance(exc, DataJudError):
            report["error_code"] = exc.code
            report["upstream_status"] = exc.upstream_status
        code = 1
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    assert all(key not in serialized for key in observed_keys), "Credential in report"
    REPORT.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
