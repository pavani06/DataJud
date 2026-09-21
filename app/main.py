"""Local HTTP interface. Run on 127.0.0.1; health does not contact CNJ."""
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import Settings
from app.core import DataJudService, error_document
from app.datajud import DataJudError
from pathlib import Path

from app.models import DiscoverRequest, ExtractFileRequest, SearchRequest


def create_app(settings: Settings | None = None, service: DataJudService | None = None) -> FastAPI:
    api = FastAPI(title='datajud-lite', version='0.1.0')

    @api.exception_handler(DataJudError)
    async def upstream_error(_request: Request, exc: DataJudError):
        return JSONResponse(status_code=exc.status_code, content=error_document(exc))

    @api.exception_handler(ValueError)
    async def invalid_input(_request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={'query_status': 'error', 'error': {'code': 'invalid_request', 'message': str(exc)}})

    @api.exception_handler(RequestValidationError)
    async def invalid_body(_request: Request, exc: RequestValidationError):
        # Omit input/context: a rejected body may itself contain sensitive text.
        errors = [{'loc': e['loc'], 'type': e['type'], 'message': e['msg']} for e in exc.errors()]
        return JSONResponse(status_code=422, content={'query_status': 'error', 'error': {'code': 'invalid_request', 'details': errors}})

    def get_service():
        current_service = service
        if current_service is None:
            try:
                current_settings = settings or Settings.from_env()
            except ValueError as exc:
                raise DataJudError('configuration_error', 'Configuração DataJud inválida; confira as variáveis de ambiente.', status_code=503) from exc
            current_service = DataJudService(current_settings)
        return current_service

    @api.get('/health')
    def health():
        return {'status': 'ok', 'service': 'datajud-lite'}

    @api.post('/search')
    def search(request: SearchRequest):
        return get_service().search(request)

    @api.get('/process/{numero}')
    def process(numero: str, tribunal: str | None = Query(None)):
        return get_service().process(numero, tribunal)

    @api.post('/discover')
    def discover(request: DiscoverRequest):
        return get_service().discover(request)

    @api.post('/extract')
    def extract(request: ExtractFileRequest | SearchRequest):
        if isinstance(request, ExtractFileRequest):
            return get_service().extract_file(Path(request.raw_file))
        return get_service().search(request)

    return api


app = create_app()
