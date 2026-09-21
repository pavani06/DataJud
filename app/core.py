"""Small application core: retrieve, preserve bytes, then extract."""
from datetime import datetime, timezone
import json
from pathlib import Path

from app.config import Settings
from app.datajud import DataJudClient, DataJudError, Retrieval, validate_response
from app.extract import extract_response
from app.models import DiscoverRequest, SearchRequest
from app.queries import build_query, prepare_raw_query
from app.storage import Storage
from app.tribunals import resolve_tribunal

EVIDENCE_NOTE = 'Zero resultados significa apenas que esta consulta, nesta fonte e momento, não retornou hits.'
PAGINATION_NOTE = 'Paginação por @timestamp sem snapshot ou desempate único: pode haver omissões ou duplicatas entre páginas.'


class DataJudService:
    def __init__(self, settings: Settings, client: DataJudClient | None = None):
        self.settings = settings
        self.client = client
        self.storage = Storage(Path(settings.data_dir))

    def _preserve(self, retrieval: Retrieval):
        return self.storage.save_raw(
            retrieval.raw_bytes, tribunal=retrieval.tribunal,
            endpoint_alias=retrieval.endpoint_alias, endpoint=retrieval.endpoint,
            query=retrieval.query, retrieved_at=retrieval.retrieved_at,
        )

    @staticmethod
    def check_supported(request: SearchRequest):
        if request.company is not None or request.party is not None:
            raise DataJudError('unsupported_filter', 'A API Pública DataJud não disponibiliza pesquisa por empresa ou nome de parte neste serviço.', status_code=422)

    def search(self, request: SearchRequest, *, context: dict | None = None) -> dict:
        self.check_supported(request)
        tribunal, _, _ = resolve_tribunal(request.tribunal)
        query = prepare_raw_query(request.query) if request.query is not None else build_query(
            processo=request.processo, classe=request.classe, assunto=request.assunto, movimento=request.movimento,
            date_from=request.date_from, date_to=request.date_to,
            size=request.size, search_after=request.search_after,
        )
        try:
            if self.client is not None:
                retrieval = self.client.search(tribunal, query)
            else:
                with DataJudClient(self.settings) as client:
                    retrieval = client.search(tribunal, query)
        except DataJudError as exc:
            if exc.retrieval is not None:
                try:
                    saved = self._preserve(exc.retrieval)
                    exc.raw_path = str(saved.raw_path)
                    exc.provenance = saved.provenance
                except OSError as storage_error:
                    raise DataJudError('storage_error', 'Falha ao preservar resposta upstream.', status_code=500) from storage_error
            raise
        try:
            stored = self._preserve(retrieval)
            if len(retrieval.payload['hits']['hits']) > retrieval.query['size']:
                error = DataJudError('unexpected_page_size', 'DataJud retornou mais hits que o tamanho solicitado; raw preservado.', status_code=502)
                error.raw_path = str(stored.raw_path)
                error.provenance = stored.provenance
                raise error
            results = extract_response(retrieval.payload, stored.provenance)
            hits = retrieval.payload['hits']['hits']
            total = retrieval.payload['hits']['total']
            if isinstance(total, int):
                total = {'value': total, 'relation': 'eq'}
            warnings = [PAGINATION_NOTE]
            if not results:
                warnings.append(EVIDENCE_NOTE)
            cursor = hits[-1].get('sort') if hits else None
            if cursor == query.get('search_after') and cursor is not None:
                warnings.append('Cursor não avançou; não continue com este cursor.')
                cursor = None
            response = {
                'source': 'CNJ/DataJud', 'tribunal': tribunal, 'query_status': 'success',
                'found': bool(results), 'count': len(results), 'total': total, 'results': results,
                'provenance': stored.provenance,
                'raw_path': str(stored.raw_path), 'extracted_path': str(stored.extracted_path),
                'next_search_after': cursor, 'warnings': warnings,
            }
            if context:
                response.update(context)
            self.storage.save_extracted(stored, response)
            return response
        except OSError as exc:
            raise DataJudError('storage_error', 'Falha ao persistir evidência local; verifique DATAJUD_DATA_DIR.', status_code=500) from exc
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            error = DataJudError('extraction_error', 'Resposta preservada, mas não pôde ser normalizada.', status_code=502)
            if 'stored' in locals():
                error.raw_path = str(stored.raw_path)
                error.provenance = stored.provenance
            raise error from exc

    def process(self, numero: str, tribunal: str | None = None) -> dict:
        from app.cnj import infer_tribunal, normalize_cnj

        normalized = normalize_cnj(numero)
        selected = tribunal if tribunal is not None else infer_tribunal(normalized)
        resolution = {'method': 'provided' if tribunal is not None else 'cnj_origin',
                      'tribunal': resolve_tribunal(selected)[0], 'process_number': normalized,
                      'note': 'A numeração indica origem; redistribuição/recursos podem exigir tribunal explícito.'}
        return self.search(SearchRequest(tribunal=selected, processo=normalized), context={'tribunal_resolution': resolution})

    def discover(self, request: DiscoverRequest) -> dict:
        from app.discover import discover

        return discover(self, request)

    def extract_file(self, raw_file: Path) -> dict:
        try:
            raw, stored = self.storage.load_raw(Path(raw_file))
            payload = json.loads(raw, parse_constant=_invalid_constant, object_pairs_hook=_unique_keys)
            validate_response(payload)
            results = extract_response(payload, stored.provenance)
            total = payload['hits']['total']
            if type(total) is int:
                total = {'value': total, 'relation': 'eq'}
            response = {
                'source': 'CNJ/DataJud', 'tribunal': stored.provenance['tribunal'],
                'query_status': 'success', 'found': bool(results), 'count': len(results),
                'total': total, 'results': results, 'provenance': stored.provenance,
                'raw_path': str(stored.raw_path), 'extracted_path': str(stored.extracted_path),
                'extracted_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'mode': 'offline', 'warnings': [] if results else [EVIDENCE_NOTE],
            }
            self.storage.save_extracted(stored, response)
            return response
        except (ValueError, KeyError, TypeError, UnicodeError, RecursionError) as exc:
            raise DataJudError('invalid_raw_evidence', 'Raw/provenance ausente, inválido, parcial ou hash divergente; reprocessamento recusado.', status_code=422) from exc
        except OSError as exc:
            raise DataJudError('storage_error', 'Não foi possível ler ou gravar a evidência local.', status_code=422) from exc


def _invalid_constant(value):
    raise ValueError('Nonfinite JSON')


def _unique_keys(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError('Duplicate JSON key')
        output[key] = value
    return output


def error_document(exc: DataJudError) -> dict:
    error = {'code': exc.code, 'message': str(exc)}
    if exc.upstream_status is not None:
        error['upstream_status'] = exc.upstream_status
    if getattr(exc, 'raw_path', None):
        error['raw_path'] = exc.raw_path
        error['provenance'] = exc.provenance
    return {'query_status': 'error', 'error': error}
