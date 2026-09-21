# Entrega — DataJud Lite V0

Este documento registra a entrega inicial e seus testes históricos. A atualização
do épico #11 passou a obter a chave pública automaticamente a cada busca; a
configuração manual descrita abaixo é o comportamento anterior. Para uso atual,
consulte o [README](README.md#autenticação-e-configuração-opcional) e o
[guia de uso](docs/GUIA_DE_USO.md). As evidências dessa atualização ficam em
`work/orchestration/public-key-state.json` e
`work/orchestration/support/public-key-acceptance.json`.

Repositório **privado**: https://github.com/pavani06/DataJud.
Implementação: commit `37ee2f2` na `main`; épico #1, issues #2–#7.
Workflow: qi-epic 1.1.0 com sessões paralelas, ownership exclusivo e revisão cruzada.
O estado GitHub e o encerramento estão em `work/orchestration/state.json`.

## IMPLEMENTED

CLI `health/search/process/discover/extract` e HTTP `/health`, `/search`, `/process`,
`/discover`, `/extract`. Core único, autenticação por ambiente, registry oficial,
queries estruturais, CNJ com MOD97 e inferência explícita de origem, discovery
paginado limitado, raw original, sidecar e normalização com provenance verificável.

```text
DataJud/
├── app/
│   ├── cli.py, main.py, models.py
│   ├── core.py, discover.py, pagination.py
│   ├── datajud.py, config.py, tribunals.py, queries.py, cnj.py
│   └── storage.py, extract.py, __init__.py
├── tests/                         testes offline + opt-in real + fixture anônima
├── examples/query.json
├── data/raw/                      local, ignorado pelo Git
├── data/extracted/                local, ignorado pelo Git
├── .omo/plans/                    plano canônico
├── work/orchestration/            estado, recibos, revisões e evidência compacta
├── .env.example, .gitignore, .python-version, AGENTS.md
└── pyproject.toml, uv.lock, README.md, DELIVERY.md
```

Arquitetura: CLI/FastAPI → DataJudService → query builder/DataJudClient → CNJ;
resposta → Storage (raw + sidecar) → extractor → normalizado/provenance.
Discovery reutiliza search; reextração reutiliza Storage/extractor sem client HTTP.

## CHANGED

A correção recebida durante a execução acrescentou discovery, process com inferência,
movimentos, aliases em inglês e extração offline. Company/party são explicitamente
unsupported. Três casos adversariais da revisão foram corrigidos: profundidade JSON,
excesso de hits upstream e deduplicação com identidade incompleta.

## PRESERVED

Arquitetura plana, separação cliente/query/extractor/storage, CLI/HTTP no mesmo core,
raw sem descarte e sem sobrescrita. Zero hits não significa inexistência. As consultas
reais já aprovadas foram reutilizadas durante a validação dos deltas.

## TESTED

**331 testes passaram; 2 pulados; zero falhas.** Integração real opt-in: **1 passou**.
Os skips normais são opt-in de rede e criação de symlink sem privilégio no Windows.
Dois avisos de depreciação do TestClient/dependências foram mantidos visíveis.

Relatório regenerado: `work/orchestration/support/acceptance.json`.
SHA256: `4eb91ffcfae1ed21c68c31bc70f48b85d94f47b0c3881676aa1f11de6c07842f`.
Snapshot de source: `5ebba9e50b135780b657a53241dabc861206eec7b13a19bf71a46ee5f2d32073`.

Validação real em 2026-09-21: processo TJSP `00182260520208260050` retornou quatro
registros. Discovery com classe 386 e ajuizamento em 2020-06-02 retornou três
candidatos em três páginas; total informado `113/eq`. Movimento 982, filtro de datas,
CLI raw/JSON e HTTP loopback health/search passaram. Reextração real por core/CLI/HTTP
passou sem API key e com busca de rede proibida. Isso verifica esses percursos,
sem provar completude da base.

Exemplo de evidência local do processo:

```text
data/raw/TJSP_20260921T185202629788Z_dbfd5c78489b849926287afe8f10d32facab12ae4b265021cd6a93865526bca9_97ccd000382e4f2cb62980932a0c35ce.json
data/extracted/TJSP_20260921T185202629788Z_dbfd5c78489b849926287afe8f10d32facab12ae4b265021cd6a93865526bca9_97ccd000382e4f2cb62980932a0c35ce.json
SHA256: dbfd5c78489b849926287afe8f10d32facab12ae4b265021cd6a93865526bca9
```

Comandos efetivamente usados para validar neste host:

```powershell
.tools/bin/uv.exe sync --python 3.12 --cache-dir .uv-cache
.tools/bin/uv.exe sync --cache-dir .uv-cache --frozen --offline
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync datajud --help
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync datajud health
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync pytest -q --junitxml=work/orchestration/support/test-results.xml
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync python work/orchestration/support/live_smoke.py --public-key-from-docs
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync python work/orchestration/support/live_smoke.py --public-key-from-docs --delta-only
python work/orchestration/support/verify_delivery.py --check-only
git status --short
git show --stat 37ee2f2
```

O smoke inicia e encerra seu próprio uvicorn em `127.0.0.1:8787`; não há servidor
residual em execução. O commit de implementação registrou 51 arquivos e 5235 linhas
adicionadas, incluindo testes, lockfile e registros de execução; o fechamento contém
apenas documentos/estado/scripts de suporte.

## Instalar, configurar e consultar

```powershell
git clone https://github.com/pavani06/DataJud.git
cd DataJud
uv sync
Copy-Item .env.example .env
```

Preencha `DATAJUD_API_KEY` no `.env` local com o valor da
[chave vigente do CNJ](https://datajud-wiki.cnj.jus.br/api-publica/acesso/).
A chave usada nos testes ficou somente em memória; nenhuma chave foi gravada no repo.

```powershell
uv run datajud health
uv run --env-file .env datajud search --tribunal TJSP --size 1 --json
uv run --env-file .env datajud process 00182260520208260050 --json
uv run --env-file .env datajud discover --tribunal TJSP --class 386 --from 2020-06-02 --to 2020-06-02 --limit 3 --page-size 1 --json
$consulta = uv run --env-file .env datajud search --tribunal TJSP --size 1 --json | ConvertFrom-Json
uv run datajud extract $consulta.raw_path --json
uv run --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8787
```

Fontes primárias: [endpoints](https://datajud-wiki.cnj.jus.br/api-publica/endpoints/),
[glossário](https://datajud-wiki.cnj.jus.br/api-publica/glossario/),
[exemplos](https://datajud-wiki.cnj.jus.br/api-publica/exemplos/),
[paginação](https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo3/) e
[Resolução 65 consolidada](https://atos.cnj.jus.br/atos/detalhar/119).
Links completos e detalhes de configuração constam no README.

## KNOWN LIMITATIONS

Discovery não garante snapshot/completude. O número CNJ identifica origem, não
necessariamente tribunal atual. Smoke real limitado ao TJSP; outros aliases foram
conferidos documentalmente. Empresa/parte não suportadas; nenhum inteiro teor presumido.
Sidecar e raw devem permanecer juntos. O teste dinâmico de symlink não rodou neste host.
Tempo ativo de fila/coordenação não foi instrumentado separadamente; janelas observadas
e essa limitação constam nos recibos, sem fabricar métricas.

## NOT IMPLEMENTED

MCP, LLM, RAG, embeddings, bancos, UI, crawler, adapters de jurisprudência,
workers distribuídos e integrações BeeBackCase/GovEvo.

## NEXT LOGICAL STEP

Avaliar cobertura de discovery com consultas representativas e decidir, em outro
escopo, se um JurisprudenceFetcher consumirá CandidateProcess. Esta entrega termina
na descoberta/extração auditável de metadados.
