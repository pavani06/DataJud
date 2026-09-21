# DataJud V0 — plano canônico de execução

Objetivo: validar search → retrieve → preserve raw → extract normalized → provenance,
por CLI e FastAPI usando o mesmo core, em repositório privado `pavani06/DataJud`.

## Diagnóstico e recomendações

Diretório inspecionado em 2026-09-21: apenas `.git`, sem commits, código ou AGENTS.md.
É construção nova: os gaps abaixo são requisitos ainda não implementados, não bugs
atribuídos a código inexistente. A revisão integral de código ocorre após a construção.

| Gap | Requisito de origem | Recomendação | Entrega |
| --- | --- | --- | --- |
| G1 | Missão §§4A/B, 7–8, 12–14 | REC-001: cliente isolado, registry e queries limitadas | Core |
| G2 | Missão §§4C/D, 5–6 | REC-002: preservar bytes, normalizar e provar hash | Evidência |
| G3 | Missão §§9–11, 16–17 | REC-003: uma aplicação compartilhada por CLI/HTTP | Interfaces |
| G4 | Missão §§15, 19–21 | REC-004: revisão independente, testes e demonstração real | Validação |

## Autoridade e simplificações

- `push_mode: autonomous-approved`: solicitação explícita de construir e entregar no GitHub.
- Épico e issues publicados antes de qualquer implementação do serviço.
- Orquestradora é a única escritora do estado e do GitHub. Trabalhadores têm arquivos exclusivos.
- Instrução complementar autoriza auxiliares em `work/orchestration/support/`, substitui
  registros globais e dispensa novos gates para transferências administrativas.
- Autorização atual cobre execução técnica; nenhum novo framework de orquestração.
- Skill: qi-epic 1.1.0, commit `18ee0c2a9f76fad1868d06e1abd0b3796c373d6a`
  de `pavani06/opencode-config`; dependências review-work, recommendation-writer,
  writing-plans e quality-improvement-loop consultadas. Ferramentas Codex equivalentes.
- Trace instrumentation pulada: task-wrapper.sh indisponível.
- Canonical grounding skipped — canonical-context unavailable (obsidian-eval ausente).
- qi-epic-close-check ausente: checar estado/issues/evidências via script local pequeno.
- Cinco dimensões de revisão serão cobertas em ondas, respeitando o limite de sessões.

## Restrições de implementação

1. Python 3.12+, uv, httpx, FastAPI, Pydantic, Typer, pytest; dependências mínimas.
2. Registry somente com aliases confirmados na wiki oficial; segredo só por ambiente.
3. Erros e respostas parciais upstream nunca viram sucesso vazio.
4. Raw preservado antes de normalização; hash SHA-256 dos bytes efetivamente persistidos.
5. HTTP local em 127.0.0.1; endpoint fixo; sem execução arbitrária nem proxy aberto.
6. Sem MCP, LLM, RAG, crawler, banco ou plataforma jurídica nesta V0.

## Ondas e ownership

### Onda 0 — fundação (orquestradora)

Publicar épico e quatro issues autossuficientes com read-back. Registrar contrato comum
em `work/orchestration/contract.md`, configurar projeto uv e instalar dependências.
Verificação: repositório privado, quatro issues ligadas ao épico, `uv sync` exit 0.

### Onda 1 — três entregas em paralelo

- Core (trabalhador core): `app/config.py`, `app/datajud.py`, `app/tribunals.py`,
  `app/queries.py`, testes correspondentes. Verificar registry, filtros, limites,
  timeout/401/403/404/429/5xx/conexão/JSON inesperado via MockTransport.
- Evidência (trabalhador evidence): `app/storage.py`, `app/extract.py`, testes respectivos.
  Verificar raw byte a byte, SHA-256, UTC, arquivos repetidos sem overwrite e campos desconhecidos.
- Interfaces (orquestradora): `app/models.py`, `app/core.py`, `app/main.py`, `app/cli.py`,
  `pyproject.toml`, README, exemplos e testes de superfícies. Verificar CLI help/health,
  HTTP health/search/process/extract, zero hits e falhas com dependência injetada.

Primeiro canário: busca de tamanho 1 no TJSP, chave pública obtida da wiki apenas em
memória, raw + extracted + hash. Falha principal: credencial inválida via mock; limite:
size >100 rejeitado. Escritas de teste em tmp_path, sem modificar dados reais prévios.
Não há migração ou batch writer de dados existentes; sandbox/canário/rollback em lote
não se aplicam. Repetição de consultas será testada sem exclusão de evidência anterior.

### Onda 2 — revisão e integração

Revisores independentes dos produtores cobrem objetivo/contexto, qualidade/segurança e QA.
Rodar `uv run pytest`, CLI real e servidor HTTP loopback; smoke opcional isolado por marker/env.
Todo blocker deve citar requisito, file:line, mecanismo e evidência de resolução.
Corrigir deltas materiais; no máximo duas iterações de review e três tentativas por critério.

### Onda 3 — fechamento

Atualizar README, recibos e estado; testar consistência JSON/referências/transições;
stage seletivo, scan de segredos, commit/push, handoff e fechamento das issues/épico
apenas com critérios atendidos. Relatar limitações e evidências sem dados brutos no GitHub.

## Medição

Primeiras três entregas registram início/fim, execução, fila, coordenação, revisão e
retrabalho em recibos. Tempos estimados são identificados; sem inventar precisão.
Defeitos após aceite: registrar contagem e período observado até fechamento.

## Análise por Eixo

1. Verificação/dependências: testes offline por responsabilidade mais smoke real explicitamente
   habilitado; lockfile reprodutível. Aceite global exige CLI, HTTP e hash comprovados.
2. Manutenção: core compartilhado e módulos pequenos; futuro MCP consumirá o mesmo core.
   Não há abstrações de domínio especulativas nem duplicação de integração.
3. Arquitetura: quatro responsabilidades separadas; orquestração fina une persistência e
   extração. Decisões documentadas aqui e no README, sem ADR adicional para projeto vazio.

Gate pós-plano: tarefas com comandos/critérios, três eixos presentes, sem placeholders.
Estado corrente e eventos: `work/orchestration/state.json` (único escritor: orquestradora).

## Delta autorizado — correção de escopo recebida durante implementação

Estado inspecionado: cliente/registry/query builder, raw/extractor e interfaces iniciais
materializados; instalação uv concluída. Testes de storage/extractor já executados.
Preservar estrutura plana e APIs corretas. Objetivo passa a SEARCH → DISCOVER → EXTRACT
→ PRESERVE PROVENANCE, terminando em metadados/candidatos, sem inteiro teor.

Novas entregas antes de código do delta:
- Estender REC-001/issue core com movimentos e `app/cnj.py`: normalização e inferência
  somente de origem codificada na Resolução 65/CNJ, com fonte/aviso e override explícito.
- REC-005 / discovery: `app/discover.py`, `app/pagination.py`, modelos/interfaces/testes.
  Limite total 1..1000, páginas 1..100, máximo 100 páginas; repetir cursor ou página,
  cursor ausente e limite interrompem com motivo explícito. Preservar cada página e
  provenance por candidato; manifesto agrega query_id, filtros, returned_hits e paginação.
- REC-006 / offline: sidecar de provenance por raw, leitura/hash verificados, extração
  offline reutilizando bytes sem rede e sem sobrescrever extração anterior.
- Atualizar QA para demonstrar processo real, discovery filtrado com múltiplas páginas
  e reprocessamento offline. Fixture anônima derivada do raw real para teste determinístico.

Company/party recebem unsupported_filter explícito. Inglês (subject/class/movement/from/to)
é alias de entrada, sem renomear mecanicamente campos normalizados já existentes.
CandidateProcess será contrato documental simples versionado; sem adapter futuro implementado.
Critérios/arquivos finais e mudança de ownership serão refletidos em state/issues.
