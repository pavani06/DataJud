# Recibo final — DataJud V0

Objetivo entregue: SEARCH → DISCOVER → EXTRACT → PRESERVE PROVENANCE sobre CNJ/DataJud.
Versão: datajud-lite 0.1.0; snapshot exato e hashes em `support/acceptance.json`.
Repositório privado: https://github.com/pavani06/DataJud ; épico #1, issues #2–#7.

Estado corrente: **concluído**; épico e seis issues fechados após handoff e read-back.
Commit de implementação publicado: `37ee2f2541acc223c26c0fe8eea1051932194750`.
Timestamp exato do encerramento: evento T006 em state.json. A seção de próxima
transição abaixo preserva o recibo de validação pré-publicação; essa transição foi executada.

## Entregas e independência

| Entrega | Produtor | Revisor independente | Disposição |
| --- | --- | --- | --- |
| #2 cliente, registry, queries e CNJ | core | evidence | PASS |
| #3 armazenamento e extração | evidence | core | PASS |
| #4 interfaces/core/documentação | root | core + api_research | PASS após R1 |
| #6 discovery/paginação | root | evidence + api_research | PASS após RCD-01/02 |
| #7 reprocessamento offline | evidence + root | core + api_research | PASS |
| #5 integração e QA | api_research | root (hashes/artefatos) + revisões cruzadas | PASS |

Arquivos alterados: `app/`, `tests/`, `examples/`, pyproject/uv.lock, .env.example,
.gitignore, .python-version, AGENTS.md, README e registros locais de execução.
Territórios separados; nenhuma alteração concorrente em arquivos de produto.

## Comandos reproduzíveis

```powershell
.tools/bin/uv.exe sync --cache-dir .uv-cache --frozen --offline
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync datajud --help
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync datajud health
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync pytest -q --junitxml=work/orchestration/support/test-results.xml
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync python work/orchestration/support/live_smoke.py --public-key-from-docs
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync python work/orchestration/support/live_smoke.py --public-key-from-docs --delta-only
python work/orchestration/support/verify_delivery.py
```

O primeiro smoke foi executado antes da ampliação; o delta reutilizou a evidência
válida do primeiro. Não se repetiu a rede após correções que alteraram somente
guardas de erro/deduplicação: regressões offline verificaram o delta. Opt-in pytest
integração também executado com chave em memória: 1 teste aprovado.

Resultados correntes, contagens e hashes são regenerados pelo verificador em
`support/acceptance.json`, a partir do JUnit, raw efetivo e relatórios. O raw é local
e ignorado pelo Git; relatórios compactos não contêm credencial. SHA256 recomputado
confere com cada envelope/candidato. Os caminhos do relatório são da máquina desta execução.

## Findings e revalidação

| Finding | Severidade | Requisito/mecanismo | Correção | Evidência |
| --- | --- | --- | --- | --- |
| R1 | P2 | JSON profundo escapava sem erro estruturado | Captura RecursionError, raw/provenance no erro | Regressões CLI/HTTP + review-interfaces-storage rodada 2 |
| RCD-01 | P2 | Página upstream podia exceder size/limit | Rejeição após persistir raw, antes de normalizar | Regressão de página oversized + duas revisões do delta |
| RCD-02 | P2 | _id sem _index podia juntar graus | Fallback por hash dos dados quando identidade incompleta | Regressão G1/G2 + review-client-discovery rodada 2 |

Nenhum P0/P1; três P2 corrigidos por violarem critérios já existentes. Não houve
terceira rodada nem expansão de escopo por preferência do revisor. Históricos de
FAIL foram preservados; conclusões atuais das revisões são PASS.

## Tempo e burocracia — primeiras três entregas

Tempos abaixo são janelas observadas de relógio, não CPU nem estimativas de tokens.
Execução paralela significa que não devem ser somados como duração do projeto.

| Entrega | Execução inicial UTC | Delta autorizado UTC | Revisão independente | Retrabalho funcional |
| --- | --- | --- | --- | --- |
| #2 core | 18:40:02–18:45:34 (332s) | 18:47:28–18:50:32 (184s) | Compartilha revisão evidence, 18:54:23–18:56:46 | Nenhum defeito em módulos próprios |
| #3 evidência | 18:40:07–18:43:56 (229s) | 18:47:16–18:50:24 (188s) | Compartilha revisão core, 18:54:13–18:57:46 | Nenhum defeito em módulos próprios |
| #4 interfaces | Início 18:40:11; conclusão verificada pelo JUnit final | Integrada à janela de execução; não separada com precisão | Core e QA (18:54:22–18:59:28), mais delta core 19:00:03–19:00:30 | R1 e guard de size, uma correção; duração ativa não instrumentada |

Fila: nenhuma fila de workers observada; duração separada não instrumentada.
Coordenação: timestamps de publicação e correção em state.json; tempo ativo não
instrumentado e não substituído por zero. Houve espera pelo runtime/cache e pelas
aprovações automáticas de sandbox. Trace OpenCode indisponível; não inventamos
separação numérica entre execução/fila/coordenação quando não medível.

Aprendizado operacional: bootstrap/descoberta de skill e ambiente dominaram a
coordenação inicial. Módulos rodaram em paralelo e a correção de escopo reutilizou
o estado sem reinício. Revisão do delta evitou repetir consultas reais e revisões
integrais. Nenhuma nova regra/framework foi introduzida para medir o processo.

Defeitos após aceite: nenhum observado entre os PASS independentes de 19:00:30/39
UTC e o fechamento registrado em state.json. Esse período curto não equivale a
monitoramento em produção nem demonstra ausência de defeitos futuros.

## Limitações e próxima transição

Symlink: teste dinâmico pulado por permissão Windows; mecanismo inspecionado.
Integração real pulada no pytest normal por design; executada separadamente.
Dois avisos de depreciação no TestClient/dependências, sem falha funcional.
Todos os 91 aliases foram conferidos na documentação, mas o smoke real usa TJSP.
Paginação não garante snapshot/completude; origem CNJ não prova localização atual.

Próxima transição autorizada: commit/push seletivo, handoffs e fechamento GitHub após
checagem de consistência. A publicação é acompanhada no state.json; sem novas
funcionalidades, sem fetcher de jurisprudência nem LLM.
