# Revisão independente — objetivo, contexto e QA

- Issue: #5, épico #1; escopos original e correção T002 (#6/#7).
- Revisor: api_research, independente dos produtores de app/ e README.
- Início: 2026-09-21T18:54:22Z.
- Término: 2026-09-21T18:59:28Z.
- Resultado: **PASS nas dimensões objetivo, contexto e QA**. Nenhum finding material novo nessas dimensões.
- Snapshot: arquivos locais após implementação de process/discover/extract offline e README final; ainda antes da correção dos dois P2 da revisão cruzada de cliente/discovery.

## Cinco dimensões e responsabilidade

| Dimensão | Parecer desta revisão | Evidência/limite |
| --- | --- | --- |
| Objetivo | PASS | CLI e HTTP compartilham DataJudService; busca, descoberta limitada, raw, extração e provenance implementados; escopo ampliado preserva a primitive original. |
| Contexto | PASS | README descreve DataJud como metadados, inferência apenas de origem, limitações de paginação, filtros públicos, extração offline e ausência de interpretação jurídica/inteiro teor. |
| QA | PASS | 36 testes offline executados pelo revisor; integração ao vivo anterior e reprocessamento adicional real sem rede; critérios detalhados abaixo. |
| Qualidade de código | Fora da atribuição | Coberta por revisão cruzada independente dos produtores; este PASS não substitui seus findings. |
| Segurança | Fora da atribuição | Coberta por revisão cruzada independente; sem novas conclusões globais de segurança neste relatório. |

## Comandos efetivamente executados nesta revisão

```powershell
.tools/bin/uv.exe sync --frozen --offline --cache-dir .uv-cache
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync datajud --help
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync datajud health
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync python -m pytest tests/test_cli.py tests/test_http.py tests/test_core.py tests/test_discover.py -q
```

Resultados: sync exit 0, 28 packages verificados no cache; help exit 0 com health/search/process/discover/extract; health exit 0 e `{"status":"ok","service":"datajud-lite"}`; testes **36 passed em 1.23s**, dois avisos de depreciação Starlette/httpx e anyio.

Também foi executado um verificador em memória usando o raw real de `live-report.json → checks.process_inferred.raw_path`: CliRunner chamou `extract <raw> --json`; TestClient chamou `POST /extract {raw_file:...}`; ambiente sem API key; `DataJudClient.search` substituído por uma função que falha se chamada. Resultado: **CLI exit 0, HTTP 200, 4 registros, mode=offline, mesma normalização e raw byte a byte inalterado**. Criaram-se apenas novas extrações locais. Nenhuma chamada CNJ adicional foi feita nesta revisão.

## Critérios A–I do pedido original

| Critério | Resultado | Evidência |
| --- | --- | --- |
| A — instalação | PASS | uv sync previamente concluído pela orquestradora; rechecagem independente `sync --frozen --offline` exit 0. |
| B — CLI help | PASS | Entrypoint instalado executado diretamente; help lista os cinco comandos. |
| C — health | PASS | CLI health exit 0 sem consulta externa; `/health` real retornou 200 no smoke anterior. |
| D — consulta real | PASS | Smoke oficial TJSP de 18:44:15–18:46:14 UTC e delta de 18:51:53–18:52:35 UTC; nenhum resultado simulado nesses percursos. |
| E — raw | PASS | Arquivos efetivos em data/raw; comparação byte a byte da saída CLI --raw e do corpo persistido. |
| F — extração | PASS | Arquivos efetivos em data/extracted; normalização e envelope persistidos conferidos. |
| G — provenance | PASS | SHA-256 recalculado sobre bytes salvos; UTC, tribunal, endpoint/alias e query presentes; provenance dos hits conferida. |
| H — HTTP | PASS | Uvicorn próprio em 127.0.0.1:8787: health/search 200; subprocess encerrado pelo smoke. Novas rotas verificadas offline abaixo. |
| I — testes | PASS | Execução independente direcionada: 36 passed. JUnit da suíte completa da orquestradora, inspecionado no disco: 329 testes, 327 passed, 2 skipped, 0 failures/errors. |

O teste opcional de integração já foi executado com API key em memória e opt-in: **1 passed em 9.67s**. Sem opt-in foi confirmado **1 skipped em 0.01s**, antes de importar/executar a consulta. Na suíte completa, o outro skip é a criação de symlink no Windows, conforme limitação do host.

## Critérios A/B/C da correção

| Critério | Resultado | Evidência |
| --- | --- | --- |
| A — processo | PASS | Core real inferiu TJSP a partir do CNJ e retornou 4 registros preservados. Testes de CLI process e GET /process sem tribunal confirmam a mesma rota e `tribunal_resolution.method=cnj_origin`. Override explícito também coberto. |
| B — discovery | PASS | Classe 386, TJSP, ajuizamento em 2020-06-02: 3 candidatos em 3 páginas reais de 1 hit, limite 3 respeitado, total upstream 113/eq, manifesto e provenance por página conferidos. CLI aliases e POST /discover cobertos com MockTransport. |
| C — offline | PASS | Raw real reextraído pelo core, CLI e HTTP, sem chave e com busca de rede proibida. Novo extracted_path, mesmo retrieved_at/hash, raw original intacto. |

Movimento 982 foi observado no raw real e efetivamente validado por consulta oficial. Assunto está verificado no builder e nas interfaces com mocks; não se afirma validação ao vivo de todas as combinações. A fixture anonimizada preserva o schema observado e marca explicitamente as substituições sintéticas.

## Dez casos adversariais

As implementações e testes lidos diferenciam: tribunal desconhecido; CNJ malformado/checksum inválido; chave ausente; 401/403; zero hits válido; timeout; erros HTTP/transporte; JSON/schema inesperado; criação da pasta ausente; execução repetida sem sobrescrita. Zero hits preserva provenance e aviso de evidência; upstream parcial (`timed_out`/shards) não vira sucesso vazio. Discovery interrompida por erro conserva páginas, sem manifesto falso de sucesso. Estes casos de falha usam mocks, não novas consultas destrutivas ou repetitivas à fonte.

## README e premissas verificadas

- Fluxo clone → uv sync → configuração da chave → help/health → consulta → HTTP documentado. `.env` exige `uv run --env-file`; `.env.example` não contém credencial.
- Exemplos e aliases CLI conferidos contra app/cli.py; examples/query.json existe. HTTP documenta as cinco rotas, limites e modo offline.
- Fontes CNJ/DataJud: acesso, endpoints, glossário e exemplos 1/2/3. Numeração: Resolução 65 consolidada e alteração TRF6. Complementos técnicos primários Elastic para range/paginação/resposta.
- Range UTC foi confirmado ao vivo; inferência é de origem, não localização atual. Não há promessa de cobertura geral ou validação ao vivo dos 91 aliases.
- CandidateProcess é um contrato JSON documentado, sem alegação de conteúdo integral de decisões. Futuro fetcher/analysis é somente fronteira documental.
- Raw tem bytes do corpo após descompressão HTTP, sem resserialização; hash não é assinatura da fonte. Sidecar é necessário para reprocessamento verificável.
- `complete_snapshot=false` e a documentação refletem o risco de empates/atualizações no search_after. Contagens desta revisão são observações pontuais.

## Disposição

Os três escopos desta revisão estão aprovados. Não foram alterados app/, README, testes de outros produtores nem evidências live já aprovadas. Os dois P2 da revisão cruzada de cliente/discovery permanecem sob responsabilidade da orquestradora para correção e validação do delta; não são duplicados aqui. Fechamento de issues, atualização de estado, visibilidade privada do remoto e commit/push continuam na fronteira exclusiva da orquestradora, fora deste parecer de runtime/documentação.
