"""Structural discovery over bounded pages of the existing search service."""
from datetime import datetime, timezone
import hashlib
import json
import time
from uuid import uuid4

from app.datajud import DataJudError
from app.models import DiscoverRequest, SearchRequest
from app.pagination import PaginationGuard
from app.queries import build_query, prepare_raw_query


def _identity(record: dict) -> str:
    provenance = record['provenance']
    if provenance.get('datajud_id') is not None and provenance.get('datajud_index') is not None:
        return json.dumps([provenance.get('datajud_index'), provenance['datajud_id']], sort_keys=True)
    source = {key: value for key, value in record.items() if key != 'provenance'}
    return hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def discover(service, request: DiscoverRequest) -> dict:
    service.check_supported(request)
    filters = request.model_dump(mode='json', exclude_none=True, exclude={'limit', 'page_size', 'size', 'search_after'})
    base_query = prepare_raw_query(request.query) if request.query is not None else build_query(
        processo=request.processo, classe=request.classe, assunto=request.assunto,
        movimento=request.movimento, date_from=request.date_from, date_to=request.date_to,
    )
    query_id = uuid4().hex
    guard = PaginationGuard()
    candidates, pages, seen = [], [], set()
    cursor, stop_reason, total, returned_hits = None, 'limit', None, 0
    while len(candidates) < request.limit:
        query = dict(base_query)
        query['size'] = min(request.page_size, request.limit - len(candidates))
        if cursor is not None:
            query['search_after'] = cursor
        page = service.search(SearchRequest(tribunal=request.tribunal, query=query))
        total = page['total'] if total is None else total
        returned_hits += page['count']
        pages.append({key: page[key] for key in ('raw_path', 'extracted_path', 'provenance', 'count')})
        identities = [_identity(record) for record in page['results']]
        for key, record in zip(identities, page['results']):
            if key not in seen:
                seen.add(key)
                candidates.append(record)
        cursor = page['next_search_after']
        problem = guard.observe(identities, cursor)
        if not page['count']:
            stop_reason = 'empty_page'
            break
        if len(candidates) >= request.limit:
            stop_reason = 'limit'
            break
        if page['count'] < query['size']:
            stop_reason = 'short_page'
            break
        if problem:
            stop_reason = problem
            break
        time.sleep(0.1)
    warnings = ['Discovery é uma seleção de candidatos; search_after sem snapshot/desempate não garante completude.']
    if stop_reason in {'repeated_cursor', 'repeated_page', 'missing_cursor', 'max_pages'}:
        warnings.append(f'Paginação interrompida por proteção: {stop_reason}.')
    if not candidates:
        warnings.append('Nenhum candidato retornado não demonstra inexistência de processos ou jurisprudência.')
    output = {
        'schema_version': 'candidate-process-set/1', 'source': 'CNJ/DataJud',
        'tribunal': pages[0]['provenance']['tribunal'], 'query_status': 'success',
        'found': bool(candidates), 'count': len(candidates), 'total': total,
        'results': candidates, 'pages': pages, 'warnings': warnings,
        'discovery': {
            'query_id': query_id, 'filters': filters,
            'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'returned_hits': returned_hits,
            'pagination': {'limit': request.limit, 'page_size': request.page_size,
                           'pages': len(pages), 'max_pages': guard.max_pages,
                           'duplicates_removed': returned_hits - len(candidates),
                           'stop_reason': stop_reason, 'next_search_after': cursor,
                           'complete_snapshot': False},
        },
    }
    try:
        path = service.storage.save_manifest(output, prefix=f'discovery_{query_id}')
    except OSError as exc:
        raise DataJudError('storage_error', 'Falha ao salvar manifesto de discovery; páginas preservadas em data/.', status_code=500) from exc
    output['manifest_path'] = str(path)
    return output
