# DataJud / datajud-lite

Cliente local leve para **busca, descoberta estrutural e extração** da API Pública
DataJud/CNJ. CLI e HTTP usam o mesmo core. Preserva a resposta original, os metadados
normalizados e a origem verificável de cada consulta.

Não é buscador full-text de jurisprudência, fonte garantida de inteiro teor, RAG,
MCP, agente ou substituto dos sistemas dos tribunais. Não faz análise jurídica.

**Comece pelo [guia de uso com exemplos e prompts](docs/GUIA_DE_USO.md)**:
terminal (PowerShell/Bash/CMD), Claude, ChatGPT, Claude Code, Codex, OpenCode,
PI e Herdr; inclui exportação de JSON, reextração offline e HTTP local.

## Quick start

Requisitos: Python 3.12+ e [uv](https://docs.astral.sh/uv/getting-started/installation/).
Repositório privado: a conta usada no clone precisa ter acesso.

```powershell
git clone https://github.com/pavani06/DataJud.git
cd DataJud
uv sync
```

Não é necessário criar `.env` nem copiar uma chave. O padrão
`DATAJUD_AUTH_MODE=auto` obtém a chave pública vigente na
[página oficial de acesso](https://datajud-wiki.cnj.jus.br/api-publica/acesso/)
antes de cada busca, incluindo cada página de discovery. O CNJ informa que pode
alterar a chave a qualquer momento; ela não fica embutida no código.

```powershell
uv run datajud --help
uv run datajud search --help
uv run datajud health
uv run datajud search --tribunal TJSP --size 1 --json
```

`health` não consulta a wiki nem a API. `uv run datajud ...` usa diretamente a CLI
local; não precisa iniciar o servidor HTTP.

## Autenticação e configuração opcional

No modo `auto`, cada chamada de busca lê a página oficial novamente, sem cache
entre chamadas ou páginas. O GET da wiki não envia Authorization; a chave fica
somente em memória e vai apenas no POST do endpoint DataJud do registry.
O serviço não grava a chave nem o HTML da página. Uma `DATAJUD_API_KEY` antiga no
ambiente é ignorada em `auto`; não há fallback silencioso para ela.

Se o DataJud responder 401/403, o modo automático atualiza a chave uma vez e faz
uma nova tentativa de autenticação por chamada. Se a wiki falhar ou não fornecer
uma chave inequívoca, a busca retorna erro explícito; isso não vira resultado vazio.
Health e `extract <raw-file>` continuam inteiramente offline, sem acesso à wiki.

Para alterar timeout, retries ou pasta, exporte variáveis ou crie um `.env`
opcional a partir de `.env.example`, preservando um arquivo existente:

```dotenv
DATAJUD_AUTH_MODE=auto
DATAJUD_TIMEOUT_SECONDS=30
DATAJUD_MAX_RETRIES=2
DATAJUD_DATA_DIR=./data
```

A aplicação não carrega `.env` automaticamente. Se optar por esse arquivo, use
`uv run --env-file .env datajud search --tribunal TJSP --size 1 --json`, ou
`uv run --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8787`.
Sem esse arquivo, os comandos do quick start funcionam com os padrões.

O override manual é explícito, para diagnóstico ou ambiente controlado:

```dotenv
DATAJUD_AUTH_MODE=manual
DATAJUD_API_KEY=<somente o valor da chave pública vigente>
```

Nesse modo, preencha o valor obtido na página oficial sem o prefixo `APIKey`.
O cliente acrescenta o header. `manual` exige a variável, não consulta a wiki e
não atualiza a chave ao receber 401/403. Só definir `DATAJUD_API_KEY` não ativa
esse modo. `.env` é ignorado pelo Git; não publique o arquivo preenchido.

## Três consultas verificadas na API real

As consultas abaixo foram verificadas na entrega inicial de **2026-09-21, antes
da autenticação automática**. Os comandos já usam o padrão atual sem `.env`;
as contagens são observações históricas, não uma nova execução nem garantias
futuras. Números de processo são texto: zeros iniciais são preservados.

```powershell
# A: processo público descoberto pelo próprio DataJud; tribunal de origem inferido
uv run datajud process 0018226-05.2020.8.26.0050 --json

# B: conjunto estrutural com classe e período; três páginas de um registro
uv run datajud discover --tribunal TJSP --class 386 --from 2020-06-02 --to 2020-06-02 --limit 3 --page-size 1 --json

# C: processo com movimento estrutural observado na resposta real
uv run datajud search --tribunal TJSP --processo 00182260520208260050 --movement 982 --size 1 --json
```

O teste A retornou 4 registros; B retornou 3 candidatos em 3 páginas, com total
upstream `113/eq`; C retornou 1 registro na página solicitada. Classe, grau e
movimentos são metadados da fonte. Não fazemos interpretação jurídica deles.
O registro histórico está em [live-report.json](work/orchestration/support/live-report.json).

Também é possível consultar assuntos e combinar filtros:

```powershell
uv run datajud search --tribunal TJSP --subject 7791 --class 386 --size 10
uv run datajud search --tribunal TJSP --query-file examples/query.json --raw
uv run datajud discover --tribunal TJSP --subject 7791 --limit 1000 --raw
```

O filtro de assunto está coberto por testes de DSL; os três exemplos acima da seção
anterior são os percursos específicos validados ao vivo. `--assunto/--subject`,
`--classe/--class`, `--movimento/--movement`, `--date-from/--from` e
`--date-to/--to` são aliases. O período filtra **data de ajuizamento**, em dias UTC,
com início inclusivo e meia-noite do dia seguinte ao fim exclusiva. O filtro de
movimento exige o código em `movimentos.codigo`; não associa uma data ao movimento.

`--company` e `--party` retornam **unsupported_filter** antes de qualquer consulta.
O glossário público não oferece nome de parte/empresa como campo de busca desta
integração. Não há busca simulada por empresa, CPF ou CNPJ.

## Process e tribunal

`process` valida máscara, 20 dígitos e dígitos verificadores MOD97 da numeração CNJ.
Sem `--tribunal`, resolve somente o **tribunal de origem codificado** em J/TR,
segundo a Resolução CNJ 65 e alterações. A resposta mostra `tribunal_resolution`.
Processos redistribuídos ou recursos podem estar em outro tribunal; a inferência
não procura todas as instâncias. Use o override explicitamente:

```powershell
uv run datajud process 00182260520208260050 --tribunal TJSP --json
```

Segmentos/conselhos sem endpoint público inequívoco geram erro pedindo tribunal.
O registry central contém os 91 aliases documentados, incluindo TJSP, STJ, TST,
TSE e STM. Extensão ocorre em `app/tribunals.py`, após conferir a documentação.
O teste real desta entrega foi no TJSP; os demais aliases foram verificados na
lista oficial e por testes de resolução, não consultados individualmente ao vivo.

## Raw e reprocessamento sem rede

Toda busca bem-sucedida salva:

```text
data/raw/<tribunal>_<UTC>_<sha256>_<nonce>.json
data/raw/<mesmo nome>.json.provenance.json
data/extracted/<mesmo nome>.json
```

O raw contém os bytes do corpo disponibilizados por httpx após descompressão HTTP,
sem parse/resserialização; campos desconhecidos, espaços e ordem são mantidos.
SHA-256 é calculado sobre **esses mesmos bytes efetivamente gravados**. A resposta
normalizada e cada objeto contêm fonte, tribunal, endpoint/alias, query enviada,
timestamp UTC, caminho do raw e hash. `_id` e `_index` são retidos na provenance do hit.
O sidecar permite recuperar a origem mesmo quando a extração falha.

Use o `raw_path` retornado por uma consulta (o arquivo original, não seu sidecar):

```powershell
uv run datajud extract "data/raw/<arquivo retornado pela consulta>.json" --json
```

Isso não exige API key nem consulta a wiki ou a API CNJ. O arquivo deve estar no diretório `raw/` de
`DATAJUD_DATA_DIR`; se a pasta de dados for diferente, configure a variável também
na reextração. Raw e sidecar devem ser mantidos juntos. Hash divergente, metadata
inválida, sidecar ausente ou resposta parcial são recusados explicitamente.

A saída é um novo arquivo, mantém `retrieved_at` e `raw_sha256` originais e acrescenta
`extracted_at`. Consultas repetidas e reextrações não sobrescrevem evidência anterior.
Também permanece disponível `extract --tribunal TJSP --processo <numero>` para recuperar
novamente e extrair. O hash detecta alteração de conteúdo; não é assinatura da fonte
nem uma cadeia de custódia criptográfica.

`search/process --raw` emite o corpo original no stdout; logs vão para stderr.
`discover --raw` emite as respostas originais de todas as páginas separadas por
newline. Esse fluxo não é um único objeto JSON nem promete JSONL se o upstream
usar JSON multilinha. Os arquivos individuais continuam idênticos aos bytes recebidos.
`--json` emite o envelope normalizado; a saída padrão é um resumo legível.

## Discovery e limites

`search` busca uma página de 1–100 hits. `discover` busca até `--limit` candidatos
(1–1000), com `--page-size` de 1–100 e no máximo 100 páginas. Não baixa universos
arbitrários. Paginação fica isolada em `app/pagination.py`; comunicação continua
exclusivamente no `DataJudClient`.

Cada página salva raw, sidecar e normalizado antes de continuar. O conjunto recebe
um manifesto em `data/extracted/discovery_*.json`, com:

- `discovery.query_id`, filtros, horário, `returned_hits` e informações de paginação;
- páginas, caminhos, provenance e candidatos normalizados;
- limite, quantidade de duplicatas removidas e motivo da parada.

Deduplicação usa `_index/_id`, preservando registros de graus distintos. Se não
houver identificador, usa hash dos dados normalizados. `count` é quantidade de
candidatos distintos; `returned_hits` inclui os hits repetidos recebidos. O total
upstream preserva `relation`: `gte` é limite inferior, `eq` é o total informado.

O CNJ documenta `search_after` ordenado por `@timestamp`. Sem desempate único ou
snapshot, alterações e empates podem causar omissões/duplicatas. Por isso
`complete_snapshot` é sempre `false`. Cursor/página repetidos, cursor ausente,
página vazia/curta e limites encerram o loop com `stop_reason` explícito.
Erro numa página interrompe a operação como erro; páginas já gravadas permanecem
no disco. Não é emitido manifesto de sucesso para uma consulta interrompida por erro.

Para explorar uma página manualmente, passe o array `next_search_after` sem alterar
filtros/ordenação. Exemplo de formato: `--search-after '[1681366085550]'`.
O corpo de `--query-file` aceita `query`, `size`, `sort`, `search_after`, `from` e
`track_total_hits` (exceto `false`). Limites também se aplicam ao modo raw: 64 KiB,
size ≤100, janela from+size ≤10000, profundidade ≤64. Scripts, runtime fields e
operações fora de `_search` são rejeitados. Em discovery, paginação raw é gerenciada
pelo serviço: use `limit/page_size`, sem `size/from/search_after` no arquivo.

## HTTP local

```powershell
uv run uvicorn app.main:app --host 127.0.0.1 --port 8787
```

| Método/rota | Entrada |
| --- | --- |
| GET `/health` | Sem chamada externa |
| POST `/search` | Parâmetros de busca ou `query` raw exclusivo |
| POST `/discover` | Mesmos filtros + `limit`, `page_size` |
| GET `/process/{numero}` | `tribunal` opcional; origem inferida quando segura |
| POST `/extract` | `{ "raw_file": "data/raw/...json" }` offline, ou parâmetros de busca |

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health
Invoke-RestMethod http://127.0.0.1:8787/search -Method Post -ContentType application/json -Body '{"tribunal":"TJSP","size":1}'
Invoke-RestMethod http://127.0.0.1:8787/discover -Method Post -ContentType application/json -Body '{"tribunal":"TJSP","class":386,"date_from":"2020-06-02","date_to":"2020-06-02","limit":3,"page_size":1}'
```

Equivalente com curl (Bash):

```bash
curl -sS http://127.0.0.1:8787/search -H 'Content-Type: application/json' \
  -d '{"tribunal":"TJSP","size":1}'
```

Swagger: `http://127.0.0.1:8787/docs`. API destinada apenas ao uso local; sem
autenticação multiusuário. Não exponha como proxy público.

## Semântica e falhas

**Não encontrado ≠ não existe.** `query_status: success`, `found: false`, `count: 0`
significam somente que a consulta naquela fonte/momento não retornou hits.
Isso não prova inexistência de processo nem ausência de jurisprudência.

Falha ao obter a chave oficial, timeout, conexão, 401/403 persistente, 404, 429,
5xx, JSON/schema inválido e resultado parcial são erros explícitos.
`timed_out: true` e shards com falha não são sucesso vazio;
Se houver corpo da API DataJud recebido com HTTP 2xx, o raw é preservado para
inspeção. O HTML da wiki nunca é salvo como evidência da consulta.

Retries transitórios: no máximo 2 por padrão (configurável 0–3), para transporte e
429/502/503/504; backoff pequeno, até 2 segundos. A renovação após 401/403 é separada
e limitada a uma por chamada no modo auto. Em manual, 401/403 não são repetidos;
404 também não. Uma falha da wiki nunca aciona chave antiga como fallback.
Timeout de 30s por operação de transporte; não é prazo total de toda a descoberta.
Erros upstream retornam 502/503/504 localmente; entrada inválida/unsupported é 422.
CLI encerra com status não zero. Logs mostram tribunal, operação, status, duração e
hits sem cabeçalhos de autenticação ou corpos gigantes.

## Arquitetura e CandidateProcess

```text
                 ┌── CLI (app/cli.py)
                 │
                 ├── FastAPI (app/main.py)
                 │
                 ▼
       DataJudService (app/core.py)
          │       └── discover + pagination
          ▼
   query builder → DataJudClient → CNJ/DataJud
                         │
                         ▼
                   raw + sidecar
                         │
                         ▼
                      extractor → normalized + provenance
```

O client não conhece FastAPI, Typer ou storage. `Storage` preserva arquivos;
`extract_response` é transformação determinística e pode ser reaplicada offline.
A organização plana foi mantida para evitar reorganização sem benefício funcional.

Contrato `CandidateProcess` desta V0: objeto JSON normalizado com os campos
presentes da fonte, em português (`numero_processo`, `tribunal`, `grau`, `classe`,
`assuntos`, `orgao_julgador`, `data_ajuizamento`, `movimentos`, `sistema`, `formato`,
`id`, timestamps e `nivel_sigilo`), mais `provenance`. Campos ausentes continuam
ausentes; objetos/códigos mantêm tipos da fonte. Assuntos aninhados são achatados;
campos adicionais ficam em `extra_fields`. Não há interpretação jurídica.
Conjuntos discovery declaram `schema_version: candidate-process-set/1`.

Fronteira futura documentada, ainda não implementada:

```text
DataJud Discover → CandidateProcess[] → JurisprudenceFetcher (futuro)
                    → DecisionDocument[] → Legal Analysis (futuro)
```

## Testes e reprodução da evidência

```powershell
uv sync
uv run datajud --help
uv run datajud health
uv run pytest
```

Testes normais usam mocks. A fixture `tests/fixtures/datajud_anonymized.json` deriva
do schema do canário real, com identificadores/contexto processual substituídos.
O opt-in de integração exige `DATAJUD_INTEGRATION_TEST=1`; no modo automático
padrão não é preciso configurar `DATAJUD_API_KEY`:

```powershell
$env:DATAJUD_INTEGRATION_TEST = '1'
uv run pytest -m integration
Remove-Item Env:DATAJUD_INTEGRATION_TEST
```

Canário específico da autenticação automática, habilitado explicitamente:

```powershell
uv run python work/orchestration/support/public_key_smoke.py --live
```

Esse script faz uma busca de tamanho 1 com a chave obtida pela rotina automática
e reprocessa a evidência offline. Grava o resultado em
[public-key-live-report.json](work/orchestration/support/public-key-live-report.json)
quando executado; não imprime nem persiste a chave. Esse relatório registra a
validação atual, separadamente das contagens históricas da V0 acima.

Smoke completo de aceitação (faz poucas consultas reais e inicia/encerra seu próprio
uvicorn loopback; não imprime nem grava a chave):

```powershell
uv run python work/orchestration/support/live_smoke.py
```

O smoke usa o mesmo fluxo automático do serviço, sem copiar a chave para o ambiente.
`--delta-only` reaproveita um relatório local anterior e exercita
processo/discovery/movimento/offline da correção de escopo. Os relatórios da entrega
inicial documentam o comportamento anterior; o canário da autenticação automática
é uma validação separada. Testes normais continuam sem rede.

Neste host uv foi instalado localmente em `.tools/bin/uv.exe`; os comandos registrados
usaram `uv run --cache-dir .uv-cache --no-sync ...` após o sync, com escalonamento
para acesso ao runtime Python/cache bloqueado pela sandbox. Essa particularidade
não é dependência funcional do projeto. Recibos e revisão em `work/orchestration/`.

## Fontes oficiais consultadas

Verificadas em 2026-09-21; comportamento real conferido pelo smoke:

- [CNJ — API Pública](https://www.cnj.jus.br/sistemas/datajud/api-publica/)
- [Acesso e chave vigente](https://datajud-wiki.cnj.jus.br/api-publica/acesso/)
- [Registry de endpoints](https://datajud-wiki.cnj.jus.br/api-publica/endpoints/)
- [Glossário de campos](https://datajud-wiki.cnj.jus.br/api-publica/glossario/)
- [Busca por número CNJ](https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo1/)
- [Classe/órgão e estrutura de assuntos](https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo2/)
- [Paginação search_after](https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo3/)
- [Resolução CNJ 65 consolidada](https://atos.cnj.jus.br/atos/detalhar/119)
- [Alteração incluindo TRF6](https://atos.cnj.jus.br/atos/detalhar/4781)
- [Anexos da Resolução 65, cópia oficial TJPA](https://libra.tjpa.jus.br/libra/pages/downloads/rescnj_65.pdf)

Complemento técnico primário: [Elastic — paginação](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/paginate-search-results),
[range query](https://www.elastic.co/docs/reference/query-languages/query-dsl/query-dsl-range-query)
e [resposta search](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-search).
O range foi derivado da DSL Elastic e confirmado em consulta real DataJud.

## Limitações e futuras extensões

O modo automático depende tanto da página oficial da chave quanto da API DataJud;
uma falha ou mudança incompatível na página pode impedir a consulta. Não há cache
nem uso automático de uma chave antiga. O modo manual exige escolha explícita.

Não há promessa de completude, consistência entre páginas ou atualização imediata da
base. Uma numeração pode ter múltiplos registros/graus; a origem CNJ pode divergir do
tribunal atual. Sem suporte a empresa/parte, inteiro teor ou ranking jurisprudencial.
Um processo pode ter muitos movimentos; a V0 limita hits, não corta campos do raw.
Raw e sidecar precisam permanecer juntos para reprocessamento verificável.

Não implementados: LLM, RAG, embeddings, vector database, MCP, crawler, UI, bancos,
workers distribuídos, integrações BeeBackCase/GovEvo ou adapters de jurisprudência.
Próximo passo lógico: avaliar cobertura e qualidade dos candidatos com consultas reais
representativas. Somente depois, em escopo separado, conectar um eventual fetcher de
inteiro teor ao contrato de candidatos preservando provenance.
