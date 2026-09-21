# Contrato entre trabalhadores — V0

Owner do contrato: root. Python síncrono, dataclasses no cliente e storage; Pydantic nas interfaces.
Nenhum trabalhador altera arquivos de outro ou executa git/GitHub.

## config.py / tribunals.py / queries.py / datajud.py (core worker)

`Settings` dataclass: `api_key: str = ''` (repr=False), `timeout_seconds: float = 30`,
`data_dir: Path = Path('data')`, `max_retries: int = 2`; `Settings.from_env()` lê
DATAJUD_API_KEY, DATAJUD_TIMEOUT_SECONDS, DATAJUD_DATA_DIR, DATAJUD_MAX_RETRIES.
Config inválida levanta `ValueError` sem ecoar credencial. Health independe da chave.

`TRIBUNALS: dict[str,str]` mapeia sigla para alias; `resolve_tribunal(tribunal) -> tuple[str,str,str]`
retorna sigla normalizada, alias, endpoint completo HTTPS _search. Erro ValueError.
Centralizar base URL. Mínimo TJSP/STJ/TST/TSE/STM; expansão abrangente só com aliases documentados.

`build_query(*, processo=None, classe=None, assunto=None, date_from=None, date_to=None,
size=10, search_after=None) -> dict`. Datas aceitam `date` ou string ISO YYYY-MM-DD.
Processo 20 dígitos ASCII ou máscara estrita, sem validação de dígito verificador nesta V0.
Query usa match numeroProcesso, classe.codigo, assuntos.codigo; range dataAjuizamento
início 00:00 UTC inclusivo, dia posterior ao fim exclusivo. `sort` @timestamp asc.
size 1..100; search_after array não vazio com valores escalares. Sem scroll automático.
`prepare_raw_query(query: dict) -> dict`: deepcopy, limite 64 KiB JSON; top-level apenas
query/size/sort/search_after/from/track_total_hits; default size=10 e sort timestamp;
from 0..9900 e from+size<=10000; rejeitar search_after+from não zero; rejeitar scripts,
script_fields/runtime_mappings e sort _script recursivamente. Não aceitar NaN/Infinity.
Toda query enviada pelo cliente passa pela mesma validação de envelope/limites.

`Retrieval` dataclass: `raw_bytes: bytes`, `payload: Any`, `tribunal: str`,
`endpoint_alias: str`, `endpoint: str`, `query: dict`, `retrieved_at: str` UTC com Z.
`DataJudError(Exception)`: `code: str`, mensagem segura, `status_code: int=502`
(HTTP local), `upstream_status: int|None`, `retrieval: Retrieval|None`.
Cliente `DataJudClient(settings: Settings, *, transport: httpx.BaseTransport|None=None)`.
`search(tribunal: str, query: dict) -> Retrieval`; `close()`, context manager.
Chave ausente: configuration_error, status 503; auth upstream: authentication_error 502;
timeout 504; conexões 503; demais HTTP/JSON/schema 502. Retry no máximo configurado
0..3, apenas transporte transitório/429/502/503/504, backoff <=2s e Retry-After limitado.
Nunca incluir header/corpo upstream ou chave na mensagem/log. Repr settings seguro.
Logs: tribunal, operação search, status HTTP, duração, hits; sem payload/chave.

Validar resposta: objeto hits.hits lista de objetos com _source objeto; total valor inteiro
não negativo + relation eq/gte (ou inteiro legado); timed_out bool; _shards.failed inteiro
não negativo. `timed_out=true` ou shards.failed>0 => partial_response, nunca sucesso.
Erro de JSON/schema/partial em resposta 200 carrega Retrieval com bytes para core preservar.
Retornar zero hits válido sem conclusão de inexistência. Não inventar campos obrigatórios ausentes.

## storage.py / extract.py (evidence worker)

`StoredRaw` dataclass: `raw_path: Path`, `extracted_path: Path`, `provenance: dict`.
`Storage(data_dir: Path)`; `save_raw(raw_bytes: bytes, *, tribunal: str, endpoint_alias: str,
endpoint: str, query: dict, retrieved_at: str) -> StoredRaw`; `save_extracted(stored: StoredRaw,
document: dict) -> Path`. Repetição nunca sobrescreve; nomes seguros tribunal+UTC+hash+nonce.
Mkdir recursivo; hash SHA256 dos bytes exatos, sem reserialização. I/O falha explícita.
Provenance: source='CNJ/DataJud', tribunal, endpoint_alias, endpoint, retrieved_at,
query (deepcopy), raw_sha256, raw_file (relativo ao data_dir). Não colocar credencial.

`extract_response(payload: dict, provenance: dict) -> list[dict]`: já validado pelo cliente,
mas checagens próprias evitam shape incorreto como vazio. Mapear numeroProcesso→numero_processo,
orgaoJulgador→orgao_julgador, dataAjuizamento→data_ajuizamento, dataHoraUltimaAtualizacao→
data_hora_ultima_atualizacao, @timestamp→timestamp, nivelSigilo→nivel_sigilo; manter classe,
assuntos, movimentos, grau, tribunal, sistema, formato, id quando presentes.
Achatar assuntos em arrays aninhados; preservar detalhes dos objetos (sem inventar null).
Outros campos em `extra_fields`; _id/_index do hit em provenance.datajud_id/datajud_index.
Provenance independente por resultado. Raw nunca é mutado. Nenhuma importação de FastAPI/Typer.

## models.py / core.py / main.py / cli.py (root)

SearchRequest: tribunal, processo?, classe?, assunto?, date_from?, date_to?, size=10,
search_after?, query? (corpo DSL exclusivo com filtros/parâmetros de paginação).
`DataJudService(settings, client=None).search(request)` retorna dict JSON com source,
tribunal, query_status='success', count=len(results), total (objeto upstream), results,
provenance do envelope mesmo vazio, paths raw/extracted, next_search_after?, warnings.
`search` e `extract` persistem raw+normalizado; --raw lê os bytes persistidos sem normalização.
Core salva raw antes de extrair; DataJudError com Retrieval também preserva raw e relança
erro explícito com caminho seguro. Um request = uma página, cursor explícito, sem loops.
`GET /health` e CLI health sem rede; FastAPI `create_app(settings=None, service=None)` para teste.
POST /search e /extract aceitam SearchRequest; GET /process/{numero}?tribunal=TJSP.
HTTP erro estruturado, CLI erro seguro exit não zero; sem traceback de segredo.

## Fontes verificadas

https://datajud-wiki.cnj.jus.br/api-publica/acesso/
https://datajud-wiki.cnj.jus.br/api-publica/endpoints/
https://datajud-wiki.cnj.jus.br/api-publica/glossario/
https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo1/
https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo2/
https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo3/
Range derivado da documentação Elastic; confirmar ao vivo antes de declarar compatibilidade.
Paginação oficial tem apenas @timestamp, sem desempate/snapshot garantidos; documentar limite.

## Delta T002 — authoritative após correção do usuário

- Core worker: `app/cnj.py` exporta `normalize_cnj(numero: str) -> str` (formato estrito,
  20 dígitos, zeros preservados; validar dígito verificador se implementação pequena com
  fonte oficial e testes) e `infer_tribunal(numero: str) -> str` (origem documentada ou
  ValueError solicitando tribunal explícito). build_query adiciona `movimento: int|None`
  por movimentos.codigo. Exportar `validate_response(payload) -> int` em datajud.py para
  uso offline: valida shape E rejeita timed_out/shards.failed via ValueError.
  O cliente segue envolvendo falhas em DataJudError com Retrieval.
- Evidence worker: save_raw grava também sidecar `<raw_filename>.provenance.json` com
  provenance antes de retornar. `Storage.load_raw(raw_file: Path) -> tuple[bytes, StoredRaw]`
  exige arquivo dentro data_dir/raw, sidecar válido/hash/metadata UTC, sem credenciais;
  StoredRaw tem raw_path original, provenance original e NOVO extracted_path exclusivo.
  Sem sidecar: falhar explicitamente, não fabricar origem. Storage aceita siglas TRE-XX
  do registry mantendo segurança de paths. Arquivos legados do canário anterior podem
  ser reprocessados por sidecar obtido de seu envelope existente, validado pelo mesmo hash.
  `Storage.save_manifest(document: dict, *, prefix: str) -> Path` salva agregado discovery
  em extracted com filename exclusivo e prefix limitado/sanitizado, sem path arbitrário.
- Root: `DataJudService.extract_file(raw_file: Path)` é offline, usa load_raw + JSON parse
  estrito + validate_response + extract_response + save_extracted. Mantém retrieved_at do
  raw e adiciona extracted_at novo. Nenhuma construção/consulta DataJudClient nesta rota.
  `DataJudService.process(numero, tribunal=None)` usa inferência explícita de origem, aviso
  de que não garante tribunal atual; override fornecido é respeitado e registrado.
- `DiscoverRequest(SearchRequest)` tem `limit=100` (1..1000), `page_size=100` (1..100),
  filtros simples e query raw opcionais; não permite size/search_after externos (cursor
  administrado internamente). `DataJudService.discover(request)` delega app/discover.py.
  Uma página de cada vez por search; máximo 100 páginas; detecta cursor repetido, falta
  de cursor/página repetida; dedup por _index/_id, fallback numero/tribunal/grau/hash fonte.
  Cada hit mantém provenance; agregado possui discovery.query_id/filters/returned_hits/
  pagination, lista pages com paths/provenance, results e manifest_path. count é candidatos
  distintos preservando graus; returned_hits inclui duplicatas vistas. Não garantir
  universo completo nem interpretar juridicamente. Falha numa página retorna erro, nunca
  sucesso agregado incompleto, e conserva páginas anteriores no disco.
- CLI `discover --raw`: stdout é JSONL, uma resposta original por linha; arquivo raw
  individual continua byte a byte. Para qualquer raw com whitespace multiline, --raw
  imprime documentos originais separados por newline, documentar formato; JSON normalizado
  agregado com --json. Sem descarte de campos.
- Company/party entram explicitamente na interface e geram DataJudError unsupported_filter
  (HTTP422/CLI não zero) ANTES de credencial/rede. Aliases English subject/class/movement.
- `POST /extract` aceita discriminadamente `{raw_file:...}` ou SearchRequest anterior;
  `GET /process` permite tribunal opcional; novo POST /discover.
