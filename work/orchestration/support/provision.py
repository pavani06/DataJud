"""Owner: root. Input: canonical plan. Publish the authorized epic/issues once."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUPPORT = Path(__file__).resolve().parent
STATE = ROOT / 'work/orchestration/state.json'
REPO = 'pavani06/DataJud'


def gh(*args):
    return subprocess.check_output(['gh', *args], cwd=ROOT, text=True, encoding='utf-8').strip()


def save(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {
    'owner': 'root', 'repo': REPO, 'push_mode': 'autonomous-approved',
    'phase': 'planning', 'iteration': 0,
    'canonical_plan_path': '.omo/plans/2026-09-21-qi-loop-datajud.md',
    'issues': {}, 'events': [], 'findings': [],
}
if state['phase'] not in ('planning', 'implementation'):
    raise SystemExit('Bootstrap encerrado; não repetir publicação em uma entrega já verificada.')
for label in ('epic', 'qi-loop'):
    gh('label', 'create', label, '-R', REPO, '--force')
if not state.get('epic'):
    url = gh('issue', 'create', '-R', REPO, '--title', 'EPIC: DataJud V0 — busca, raw, extração e provenance',
             '--label', 'epic', '--label', 'qi-loop', '--body-file', str(SUPPORT / 'epic.md'))
    state['epic'] = int(url.rsplit('/', 1)[1])
    save(state)

tasks = [
    ('core', 'Core DataJud oficial, registry, queries e robustez HTTP', 'G1', 'REC-001',
     'app/config.py, app/datajud.py, app/tribunals.py, app/queries.py; testes correspondentes',
     'Confirmar documentação CNJ. Implementar configuração por ambiente, registry validado, POST _search com httpx, erros tipados, timeout/backoff limitado; query por número CNJ, classe, assunto, datas UTC e search_after. Limitar size a 100, não executar scripts de DSL e nunca converter falha upstream em zero hits.',
     'uv run pytest tests/test_queries.py tests/test_datajud.py tests/test_tribunals.py tests/test_config.py',
     'Registry TJSP/STJ/TST/TSE/STM; número mascarado/20 dígitos; filtros; limites; 401/403/404 sem retry; 429/5xx/transporte com retry limitado; JSON/schema inesperado e parcial distinguíveis de sucesso vazio.',
     'Contrato comum; desbloqueia integração CLI/HTTP e validação'),
    ('evidence', 'Persistência raw, extração normalizada e provenance verificável', 'G2', 'REC-002',
     'app/storage.py, app/extract.py; tests/test_storage.py e tests/test_extract.py',
     'Persistir bytes originais da resposta antes de extrair, criar diretórios automaticamente, evitar sobrescrita em consultas repetidas. Extrair somente dados presentes, normalizar assuntos aninhados, preservar campos desconhecidos. Cada resultado e envelope vazio têm provenance com UTC, fonte, tribunal, endpoint/alias, query enviada e SHA-256 dos bytes persistidos.',
     'uv run pytest tests/test_storage.py tests/test_extract.py',
     'Raw idêntico byte a byte; hash recalculado confere; repetição sem perda; paths não escapam do diretório; dados ausentes sem fabricação; campos adicionais preservados; zero hits permanece consulta bem-sucedida vazia.',
     'Contrato comum; desbloqueia integração CLI/HTTP e validação'),
    ('interfaces', 'CLI e FastAPI sobre core único, instalação e README', 'G3', 'REC-003',
     'app/models.py, app/core.py, app/main.py, app/cli.py, app/__init__.py, pyproject.toml, uv.lock, .env.example, README.md, examples/, testes de interfaces',
     'Criar projeto uv Python 3.12+, core fino compartilhado, CLI health/search/extract com help/json/raw/query-file; HTTP GET /health, POST /search, GET /process/{numero}, POST /extract. Saúde offline e bind local. Documentar configuração segura, fontes oficiais, evidência, paginação limitada e exclusões de escopo.',
     'uv sync; uv run datajud --help; uv run datajud health; uv run pytest tests/test_cli.py tests/test_http.py tests/test_core.py',
     'Instalação e comandos funcionam; CLI/HTTP compartilham integração; raw sem perda; erros estruturados sem segredo; README permite clone→consulta→servidor; dados e .env ignorados no Git.',
     'Contrato comum; integração depende de core e evidência; desbloqueia validação'),
    ('validation', 'Revisão independente, smoke real e aceite adversarial', 'G4', 'REC-004',
     'tests/test_integration.py, work/orchestration/support/, work/orchestration/receipts.md; revisão read-only de app/ e README',
     'Revisar objetivo/contexto, código/segurança e QA com independência dos produtores. Demonstrar cedo consulta TJSP limitada, raw+extraído+hash. Rodar suíte offline e smoke real opt-in. Subir FastAPI em 127.0.0.1 e consultar. Exercitar tribunal inválido, CNJ malformado, chave ausente/inválida, zero hits, timeout, upstream, JSON inesperado, diretório ausente e repetição. Findings materiais recebem correção e revalidação do delta.',
     'uv run pytest; DATAJUD_INTEGRATION_TEST=1 uv run pytest -m integration; uv run uvicorn app.main:app --host 127.0.0.1 --port 8787',
     'Todos os critérios A–I da missão demonstrados, dez cenários adversariais cobertos, nenhum P0/P1 aberto, recibos com versão/comandos/limitações e state consistente. Chave real e dados brutos nunca commitados.',
     'Depende de core, evidência e interfaces; desbloqueia fechamento do épico'),
]
for key, title, gap, rec, files, steps, command, acceptance, deps in tasks:
    body = f'''**Epic:** #{state['epic']} · **{rec}** · **Gap {gap} (requisito novo)**
**Repo:** {REPO} · raiz local: C:\\Users\\pavan\\OneDrive\\Documents\\ChatGPT\\DataJud

## Contexto
Construir serviço local pequeno DataJud/CNJ independente: search → retrieve → preserve raw → extract → provenance.
CLI e HTTP compartilham core. Ausência de hits não demonstra inexistência de processo. Sem MCP/LLM/RAG/banco/crawler.
Plano canônico: `.omo/plans/2026-09-21-qi-loop-datajud.md`; contrato: `work/orchestration/contract.md`.

## Território exclusivo
{files}

## Tarefas
1. Ler contrato e documentação oficial em https://datajud-wiki.cnj.jus.br/api-publica/.
2. {steps}
3. Verificar no disco: `{command}`. Esperado: exit 0, comportamento indicado no aceite.

## Aceite
- [ ] {acceptance}
- [ ] Evidência revisada por pessoa/agente diferente do produtor.

## Dependências
{deps}. Execução paralela apenas em territórios exclusivos; orquestradora é única escritora de Git/GitHub/estado.

## Handoff ao fechar
Comentar objetivo/versão, arquivos, comandos/entradas, resultados/limitações, findings/disposição e próxima transição.
Medir execução, fila, coordenação, review e retrabalho nas primeiras três entregas; anotar período observado.
Somente fechar após conferir critérios no disco; push_mode autonomous-approved.
'''
    path = SUPPORT / f'issue-{key}.md'
    path.write_text(body, encoding='utf-8')
    if key not in state['issues']:
        url = gh('issue', 'create', '-R', REPO, '--title', title, '--label', 'qi-loop', '--body-file', str(path))
        state['issues'][key] = {'number': int(url.rsplit('/', 1)[1]), 'status': 'planned', 'owner': None}
        save(state)
    number = state['issues'][key]['number']
    published = json.loads(gh('issue', 'view', str(number), '-R', REPO, '--json', 'body'))['body']
    assert published.replace('\r\n', '\n').strip() == body.strip(), f'Body divergiu: {key}'
    node = json.loads(gh('api', f'repos/{REPO}/issues/{number}'))
    children = json.loads(gh('api', f'repos/{REPO}/issues/{state["epic"]}/sub_issues'))
    if not any(child['number'] == number for child in children):
        gh('api', f'repos/{REPO}/issues/{state["epic"]}/sub_issues', '-X', 'POST', '-F', f'sub_issue_id={node["id"]}')

epic = (SUPPORT / 'epic.md').read_text(encoding='utf-8')
epic += '\n## Issues publicadas\n' + ''.join(f'- [ ] #{v["number"]}: {k}\n' for k, v in state['issues'].items())
(SUPPORT / 'epic-published.md').write_text(epic, encoding='utf-8')
gh('issue', 'edit', str(state['epic']), '-R', REPO, '--body-file', str(SUPPORT / 'epic-published.md'))
assert json.loads(gh('issue', 'view', str(state['epic']), '-R', REPO, '--json', 'body'))['body'].replace('\r\n', '\n').strip() == epic.strip()
state['phase'] = 'implementation'
if not any(event['id'] == 'T001-issues-published' for event in state['events']):
    state['events'].append({'id': 'T001-issues-published', 'at': datetime.now(timezone.utc).isoformat(), 'phase': 'implementation'})
save(state)
print(json.dumps({'epic': state['epic'], 'issues': state['issues']}, ensure_ascii=False))
