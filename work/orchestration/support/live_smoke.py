"""Small, explicit live acceptance check; never prints or persists the API key.

Run: uv run python work/orchestration/support/live_smoke.py
Uses the production auth mode (auto by default); no separate key scraper.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parents[3]
REPORT_PATH = ROOT / "work/orchestration/support/live-report.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def verify_result(result: dict) -> dict:
    assert result["query_status"] == "success"
    assert result["count"] == len(result["results"])
    raw_path = Path(result["raw_path"])
    extracted_path = Path(result["extracted_path"])
    raw_bytes = raw_path.read_bytes()
    payload = json.loads(raw_bytes)
    assert payload["timed_out"] is False
    assert payload["_shards"]["failed"] == 0
    assert len(payload["hits"]["hits"]) == result["count"]
    provenance = result["provenance"]
    digest = hashlib.sha256(raw_bytes).hexdigest()
    assert provenance["raw_sha256"] == digest
    assert provenance["source"] == "CNJ/DataJud"
    assert provenance["retrieved_at"].endswith("Z")
    assert provenance["endpoint_alias"] == "api_publica_tjsp"
    assert json.loads(extracted_path.read_text(encoding="utf-8")) == result
    for item in result["results"]:
        assert item["provenance"]["raw_sha256"] == digest
    return {
        "query_status": result["query_status"],
        "count": result["count"],
        "total": result.get("total"),
        "raw_path": str(raw_path),
        "extracted_path": str(extracted_path),
        "raw_sha256": digest,
        "provenance_verified": True,
    }


def run_cli(arguments: list[str], env: dict[str, str]) -> bytes:
    executable = ROOT / ".venv" / ("Scripts/datajud.exe" if os.name == "nt" else "bin/datajud")
    completed = subprocess.run(
        [str(executable), *arguments], cwd=ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if completed.returncode:
        raise RuntimeError("CLI command failed; output deliberately omitted")
    return completed.stdout


def http_check(request: dict, env: dict[str, str]) -> dict:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8787))
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8787"],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        with httpx.Client(base_url="http://127.0.0.1:8787", timeout=120) as client:
            deadline = time.monotonic() + 20
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Created uvicorn process exited before readiness")
                try:
                    health = client.get("/health", timeout=1)
                    if health.status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Created uvicorn process did not become ready")
                time.sleep(0.2)
            assert health.json()["status"] == "ok"
            response = client.post("/search", json=request)
            response.raise_for_status()
            result = verify_result(response.json())
            result["health_http_status"] = health.status_code
            result["search_http_status"] = response.status_code
            return result
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def delta_checks(service, canary: dict, report: dict) -> None:
    """Validate process inference, bounded discovery, movement and offline replay."""
    from app.config import Settings
    from app.core import DataJudService
    from app.models import DiscoverRequest, SearchRequest

    record = canary["results"][0]
    number = record["numero_processo"]
    filing_date = date.fromisoformat(record["data_ajuizamento"][:10])
    print("WORKING process inference", file=sys.stderr, flush=True)
    result = service.process(number)
    report["checks"]["process_inferred"] = verify_result(result)
    assert result["tribunal"] == "TJSP" and result["count"] >= 1
    assert all(item["numero_processo"] == number for item in result["results"])

    print("WORKING filtered discovery with page_size=1 and limit=3", file=sys.stderr, flush=True)
    filters = {"tribunal": "TJSP", "classe": record["classe"]["codigo"], "date_from": filing_date, "date_to": filing_date}
    discovered = service.discover(DiscoverRequest(**filters, limit=3, page_size=1))
    if discovered["count"] < 2:
        filters.update(date_from=date(filing_date.year, 1, 1), date_to=date(filing_date.year, 12, 31))
        discovered = service.discover(DiscoverRequest(**filters, limit=3, page_size=1))
    assert discovered["query_status"] == "success"
    assert 2 <= discovered["count"] <= 3
    assert len(discovered["pages"]) >= 2
    assert Path(discovered["manifest_path"]).is_file()
    pages = [verify_result(json.loads(Path(page["extracted_path"]).read_text(encoding="utf-8"))) for page in discovered["pages"]]
    for item in discovered["results"]:
        assert item["classe"]["codigo"] == record["classe"]["codigo"]
        assert filters["date_from"] <= date.fromisoformat(item["data_ajuizamento"][:10]) <= filters["date_to"]
        assert item["provenance"]["raw_sha256"] in {page["raw_sha256"] for page in pages}
    report["checks"]["discovery"] = {
        "query_status": "success", "count": discovered["count"], "page_count": len(pages),
        "manifest_path": discovered["manifest_path"], "filters_verified": True,
        "pages": pages, "discovery": discovered["discovery"],
    }

    print("WORKING observed movement filter", file=sys.stderr, flush=True)
    movement = next(item["codigo"] for item in record["movimentos"] if isinstance(item.get("codigo"), int))
    moved = service.search(SearchRequest(tribunal="TJSP", processo=number, movimento=movement, size=1))
    report["checks"]["movement"] = verify_result(moved)
    assert moved["count"] >= 1
    assert all(any(item.get("codigo") == movement for item in entry["movimentos"]) for entry in moved["results"])
    report["checks"]["movement"]["movement_code"] = movement

    print("WORKING offline extraction with no key and network search forbidden", file=sys.stderr, flush=True)
    raw_path = Path(result["raw_path"])
    before = raw_path.read_bytes()
    with patch.dict(os.environ, {"DATAJUD_API_KEY": ""}), patch(
        "app.datajud.DataJudClient.search", side_effect=AssertionError("Offline path attempted network search")
    ):
        offline = DataJudService(Settings(data_dir=ROOT / "data")).extract_file(raw_path)
    report["checks"]["offline_extract"] = verify_result(offline)
    assert raw_path.read_bytes() == before
    assert offline["provenance"]["retrieved_at"] == result["provenance"]["retrieved_at"]
    assert offline["extracted_path"] != result["extracted_path"]
    assert offline["results"] == result["results"]
    report["checks"]["offline_extract"].update(no_api_key=True, network_search_forbidden=True, original_raw_unchanged=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-key-from-docs", action="store_true", help="Compatibility flag: explicitly select production auto authentication")
    parser.add_argument("--delta-only", action="store_true", help="Reuse the verified canary from live-report.json and run only the expanded acceptance checks")
    args = parser.parse_args()
    report: dict = {"started_at": utc_now(), "status": "running", "checks": {}}
    stage = "configuration"
    try:
        from app.config import Settings
        from app.core import DataJudService
        from app.models import SearchRequest

        settings = replace(Settings.from_env(), data_dir=ROOT / "data")
        if args.public_key_from_docs:
            settings = replace(settings, auth_mode="auto")
        env = os.environ.copy()
        env.update(DATAJUD_AUTH_MODE=settings.auth_mode, DATAJUD_DATA_DIR=str(settings.data_dir), PYTHONIOENCODING="utf-8")
        service = DataJudService(settings)
        if args.delta_only:
            previous = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
            report["checks"].update(previous["checks"])
            report["sample"] = previous["sample"]
            report["previous_live_run"] = {name: previous[name] for name in ("started_at", "finished_at", "status")}
            canary = json.loads(Path(previous["checks"]["canary"]["extracted_path"]).read_text(encoding="utf-8"))
            verify_result(canary)
            stage = "delta"
            delta_checks(service, canary, report)
            report["status"] = "success"
            report["finished_at"] = utc_now()
            REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        stage = "canary"
        canary = service.search(SearchRequest(tribunal="TJSP", size=1))
        report["checks"][stage] = verify_result(canary)
        assert canary["count"] == 1, "Canary needs one public record for follow-up checks"
        record = canary["results"][0]
        number = record["numero_processo"]
        report["sample"] = {field: record[field] for field in ("numero_processo", "tribunal", "grau", "classe", "data_ajuizamento") if field in record}
        stage = "by_number"
        by_number = service.search(SearchRequest(tribunal="TJSP", processo=number, size=1))
        report["checks"][stage] = verify_result(by_number)
        assert by_number["count"] >= 1
        assert by_number["results"][0]["numero_processo"] == number
        stage = "date_range"
        filing_value = record["data_ajuizamento"]
        filing_date = date.fromisoformat(filing_value[:10])
        ranged = service.search(SearchRequest(tribunal="TJSP", processo=number, date_from=filing_date, date_to=filing_date, size=1))
        report["checks"][stage] = verify_result(ranged)
        assert ranged["count"] >= 1
        assert ranged["results"][0]["numero_processo"] == number
        stage = "cli_json"
        cli_json = json.loads(run_cli(["search", "--tribunal", "TJSP", "--processo", number, "--size", "1", "--json"], env))
        report["checks"][stage] = verify_result(cli_json)
        stage = "cli_raw"
        raw_output = run_cli(["search", "--tribunal", "TJSP", "--processo", number, "--size", "1", "--raw"], env)
        raw_payload = json.loads(raw_output)
        assert len(raw_payload["hits"]["hits"]) >= 1
        assert any(path.read_bytes() == raw_output for path in (ROOT / "data/raw").glob("*.json"))
        report["checks"][stage] = {"valid_upstream_json": True, "bytes_match_persisted_raw": True}
        stage = "http"
        report["checks"][stage] = http_check({"tribunal": "TJSP", "processo": number, "size": 1}, env)
        stage = "delta"
        delta_checks(service, canary, report)
        report["status"] = "success"
        return_code = 0
    except Exception as error:
        last_frame = traceback.extract_tb(error.__traceback__)[-1]
        report.update(status="failed", failed_stage=stage, error_type=type(error).__name__,
                      error_location=f"{Path(last_frame.filename).name}:{last_frame.lineno}")
        return_code = 1
    report["finished_at"] = utc_now()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
