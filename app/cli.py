"""CLI for structural search, discovery and offline extraction."""
import json
import logging
import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from app.config import Settings
from app.core import DataJudService, error_document
from app.datajud import DataJudError
from app.models import DiscoverRequest, SearchRequest

app = typer.Typer(no_args_is_help=True, help='Explore DataJud/CNJ: search, discover, process e extract com provenance.', pretty_exceptions_enable=False)


@app.callback()
def configure():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)


@app.command()
def health():
    """Verifique a CLI local sem rede ou API key."""
    typer.echo(json.dumps({'status': 'ok', 'service': 'datajud-lite'}))


def _request(tribunal, processo, classe, assunto, movimento, date_from, date_to,
             size, search_after, query_file, company, party, *, discovery=None):
    fields = dict(tribunal=tribunal, company=company, party=party)
    if query_file is not None:
        if any(v is not None for v in (processo, classe, assunto, movimento, date_from, date_to, size, search_after)):
            raise ValueError('--query-file é exclusivo com filtros e paginação por opções.')
        if query_file.stat().st_size > 65536:
            raise ValueError('Query file excede 64 KiB.')
        query = json.loads(query_file.read_text(encoding='utf-8-sig'))
        if not isinstance(query, dict):
            raise ValueError('Query file deve conter um objeto JSON.')
        fields['query'] = query
    else:
        fields.update(processo=processo, classe=classe, assunto=assunto, movimento=movimento,
                      date_from=date_from, date_to=date_to)
        if discovery is None:
            fields['size'] = 10 if size is None else size
            fields['search_after'] = json.loads(search_after) if search_after is not None else None
    if discovery is not None:
        return DiscoverRequest(**fields, **discovery)
    return SearchRequest(**fields)


def _render(result, *, raw, as_json):
    if raw:
        paths = [page['raw_path'] for page in result['pages']] if 'pages' in result else [result['raw_path']]
        for index, path in enumerate(paths):
            data = Path(path).read_bytes()
            separator = b'\n' if index else b''
            stream = getattr(sys.stdout, 'buffer', None)
            if stream is not None:
                stream.write(separator + data)
                stream.flush()
            else:
                typer.echo((separator + data).decode('utf-8'), nl=False)
    elif as_json:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"{result['tribunal']} | consulta/extração bem-sucedida | {result['count']} resultado(s)")
        for item in result['results']:
            classe = item.get('classe', {})
            name = classe.get('nome', '') if isinstance(classe, dict) else str(classe)
            typer.echo(f"  {item.get('numero_processo', '(número não fornecido)')} | {item.get('grau', '')} | {name}")
        if 'manifest_path' in result:
            typer.echo(f"Manifesto: {result['manifest_path']} | páginas: {len(result['pages'])}")
        else:
            typer.echo(f"Raw: {result['raw_path']}\nExtraído: {result['extracted_path']}")
        if 'tribunal_resolution' in result:
            resolution = result['tribunal_resolution']
            typer.echo(f"Tribunal: {resolution['method']}. {resolution['note']}")
        for warning in result.get('warnings', []):
            typer.echo(f'Aviso: {warning}')


def _run(operation, *, raw=False, as_json=False):
    try:
        if raw and as_json:
            raise ValueError('Escolha --raw ou --json.')
        _render(operation(), raw=raw, as_json=as_json)
    except DataJudError as exc:
        typer.echo(json.dumps(error_document(exc), ensure_ascii=False), err=True)
        raise typer.Exit(1) from None
    except (ValueError, OSError, ValidationError) as exc:
        if isinstance(exc, ValidationError):
            message = '; '.join(e['msg'] for e in exc.errors())
        elif isinstance(exc, OSError):
            message = 'Não foi possível ler ou gravar o arquivo local solicitado.'
        else:
            message = str(exc)
        typer.echo(json.dumps({'query_status': 'error', 'error': {'code': 'invalid_request', 'message': message}}, ensure_ascii=False), err=True)
        raise typer.Exit(2) from None


Tribunal = Annotated[str, typer.Option('--tribunal', help='Sigla do tribunal, por exemplo TJSP.')]
Processo = Annotated[str | None, typer.Option('--processo', '--process', help='20 dígitos ou máscara CNJ.')]
Classe = Annotated[int | None, typer.Option('--classe', '--class', min=1)]
Assunto = Annotated[int | None, typer.Option('--assunto', '--subject', min=1)]
Movimento = Annotated[int | None, typer.Option('--movimento', '--movement', min=1)]
DateFrom = Annotated[str | None, typer.Option('--date-from', '--from', help='Dia inicial UTC: YYYY-MM-DD.')]
DateTo = Annotated[str | None, typer.Option('--date-to', '--to', help='Dia final UTC inclusivo: YYYY-MM-DD.')]
Size = Annotated[int | None, typer.Option('--size', min=1, max=100, help='Tamanho da página; padrão 10.')]
Cursor = Annotated[str | None, typer.Option('--search-after', help='Array JSON do cursor da página anterior.')]
QueryFile = Annotated[Path | None, typer.Option('--query-file', exists=True, dir_okay=False, help='Corpo Query DSL JSON.')]
Raw = Annotated[bool, typer.Option('--raw', help='Emita as respostas originais; discovery separa páginas por newline.')]
AsJson = Annotated[bool, typer.Option('--json', help='Emita JSON normalizado com provenance.')]
Company = Annotated[str | None, typer.Option('--company', help='Não suportado pela API Pública; retorna erro explícito.')]
Party = Annotated[str | None, typer.Option('--party', help='Nome de parte: não suportado; retorna erro explícito.')]


@app.command()
def search(tribunal: Tribunal, processo: Processo = None, classe: Classe = None,
           assunto: Assunto = None, movimento: Movimento = None,
           date_from: DateFrom = None, date_to: DateTo = None,
           size: Size = None, search_after: Cursor = None, query_file: QueryFile = None,
           company: Company = None, party: Party = None, raw: Raw = False, as_json: AsJson = False):
    """Recupere uma página e salve raw + normalizado."""
    _run(lambda: DataJudService(Settings.from_env()).search(_request(
        tribunal, processo, classe, assunto, movimento, date_from, date_to, size,
        search_after, query_file, company, party)), raw=raw, as_json=as_json)


@app.command()
def process(numero: Annotated[str, typer.Argument(help='Número CNJ com ou sem máscara.')],
            tribunal: Annotated[str | None, typer.Option('--tribunal')] = None,
            raw: Raw = False, as_json: AsJson = False):
    """Consulte processo; sem tribunal explícito, use a origem codificada no CNJ."""
    _run(lambda: DataJudService(Settings.from_env()).process(numero, tribunal), raw=raw, as_json=as_json)


@app.command()
def discover(tribunal: Tribunal, processo: Processo = None, classe: Classe = None,
             assunto: Assunto = None, movimento: Movimento = None,
             date_from: DateFrom = None, date_to: DateTo = None,
             limit: Annotated[int, typer.Option('--limit', min=1, max=1000)] = 100,
             page_size: Annotated[int, typer.Option('--page-size', min=1, max=100)] = 100,
             query_file: QueryFile = None, company: Company = None, party: Party = None,
             raw: Raw = False, as_json: AsJson = False):
    """Descubra até 1000 candidatos; páginas e provenance ficam preservadas."""
    _run(lambda: DataJudService(Settings.from_env()).discover(_request(
        tribunal, processo, classe, assunto, movimento, date_from, date_to, None,
        None, query_file, company, party, discovery={'limit': limit, 'page_size': page_size})), raw=raw, as_json=as_json)


@app.command()
def extract(raw_file: Annotated[Path | None, typer.Argument(help='Raw salvo em data/raw; reprocessamento offline.')] = None,
            tribunal: Annotated[str | None, typer.Option('--tribunal')] = None,
            processo: Processo = None, classe: Classe = None, assunto: Assunto = None,
            movimento: Movimento = None, date_from: DateFrom = None, date_to: DateTo = None,
            size: Size = None, search_after: Cursor = None, query_file: QueryFile = None,
            as_json: AsJson = False):
    """Reextraia raw SEM rede; ou recupere e extraia com --tribunal e filtros."""
    def operation():
        service = DataJudService(Settings.from_env())
        if raw_file is not None:
            if any(value is not None for value in (tribunal, processo, classe, assunto, movimento, date_from, date_to, size, search_after, query_file)):
                raise ValueError('raw-file não pode ser combinado com parâmetros de consulta.')
            return service.extract_file(raw_file)
        if tribunal is None:
            raise ValueError('Forneça um raw-file para reprocessar ou --tribunal para consultar.')
        return service.search(_request(tribunal, processo, classe, assunto, movimento, date_from, date_to, size, search_after, query_file, None, None))
    _run(operation, as_json=as_json)
