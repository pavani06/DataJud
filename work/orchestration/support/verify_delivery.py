"""Owner root. Verify local evidence/state and regenerate a compact acceptance receipt.

Inputs: state.json, live-report.json, test-results.xml, source and review reports.
No network, deletion, Git mutation or access to credentials.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
SUPPORT = Path(__file__).resolve().parent


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


state = load(ROOT / 'work/orchestration/state.json')
assert state['owner'] == 'root'
assert state['push_mode'] == 'autonomous-approved'
assert (ROOT / state['canonical_plan_path']).is_file()
events = state['events']
assert len({event['id'] for event in events}) == len(events), 'Duplicate transition'
assert events[-1]['phase'] == state['phase'], 'State/event phase divergence'
issues = state['issues']
assert len({issue['number'] for issue in issues.values()}) == len(issues)
assert all(issue['owner'] for issue in issues.values())
assert not [f for f in state['findings'] if f['severity'] in ('P0', 'P1') and f['status'] != 'resolved']
for path in (ROOT / 'work/orchestration').rglob('*.json'):
    load(path)

verified = {}


def verify_evidence(value):
    if isinstance(value, dict):
        if {'raw_path', 'raw_sha256', 'extracted_path'} <= value.keys():
            raw, extracted = Path(value['raw_path']), Path(value['extracted_path'])
            assert raw.resolve().is_relative_to(ROOT / 'data')
            assert extracted.resolve().is_relative_to(ROOT / 'data')
            digest = sha(raw)
            assert digest == value['raw_sha256']
            document = load(extracted)
            assert document['provenance']['raw_sha256'] == digest
            assert document['provenance']['source'] == 'CNJ/DataJud'
            assert document['count'] == len(document['results'])
            assert all(record['provenance']['raw_sha256'] == digest for record in document['results'])
            verified[str(raw.relative_to(ROOT))] = digest
        for child in value.values():
            verify_evidence(child)
    elif isinstance(value, list):
        for child in value:
            verify_evidence(child)


live_path = SUPPORT / 'live-report.json'
live = load(live_path)
assert live['status'] == 'success'
verify_evidence(live)
discovery = live['checks']['discovery']
manifest = load(Path(discovery['manifest_path']))
assert manifest['count'] == len(manifest['results']) == discovery['count']
assert len(manifest['pages']) == discovery['page_count']
assert live['checks']['offline_extract']['network_search_forbidden']
assert live['checks']['http']['health_http_status'] == 200
assert live['checks']['http']['search_http_status'] == 200

test_path = SUPPORT / 'test-results.xml'
suites = ET.parse(test_path).getroot().findall('testsuite')
counts = {name: sum(int(suite.attrib.get(name, 0)) for suite in suites)
          for name in ('tests', 'failures', 'errors', 'skipped')}
assert counts['tests'] > 0 and counts['failures'] == counts['errors'] == 0
counts['passed'] = counts['tests'] - counts['skipped']

source_files = sorted(list((ROOT / 'app').glob('*.py')) + list((ROOT / 'tests').rglob('*.py'))
                      + [ROOT / 'pyproject.toml', ROOT / 'uv.lock', ROOT / 'README.md'])
source_hashes = {str(path.relative_to(ROOT)).replace('\\', '/'): sha(path) for path in source_files}
source_digest = hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest()
report = {
    'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    'source_sha256': source_digest, 'tests': counts, 'test_report_sha256': sha(test_path),
    'live_report_sha256': sha(live_path), 'live_checks': list(live['checks']),
    'verified_raw_files': verified, 'discovery_candidates': manifest['count'],
    'discovery_pages': len(manifest['pages']), 'state_consistent': True,
    'review_reports': {path.name: sha(path) for path in SUPPORT.glob('review-*.md')},
    'source_files': source_hashes,
}
output = SUPPORT / 'acceptance.json'
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'tests': counts, 'source_sha256': source_digest, 'acceptance_sha256': sha(output),
                  'verified_raw_count': len(verified), 'discovery_candidates': manifest['count'],
                  'discovery_pages': len(manifest['pages']), 'state_consistent': True}, ensure_ascii=False))
