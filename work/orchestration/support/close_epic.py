"""Owner root. Close verified issues with idempotent handoffs; no product edits.

Inputs: accepted report, independently reviewed source commit, state and GitHub issues.
Explicitly authorized by the DataJud repository/epic request and autonomous push mode.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SUPPORT = Path(__file__).resolve().parent
STATE = ROOT / 'work/orchestration/state.json'
state = json.loads(STATE.read_text(encoding='utf-8'))
REPO = state['repo']


def gh(*args):
    return subprocess.check_output(['gh', *args], cwd=ROOT, text=True, encoding='utf-8').strip()


def save():
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def comment_once(number, text, transition):
    marker = f'<!-- {transition} -->'
    comments = json.loads(gh('issue', 'view', str(number), '-R', REPO, '--json', 'comments'))['comments']
    if not any(marker in comment['body'] for comment in comments):
        path = SUPPORT / f'handoff-{number}.md'
        path.write_text(text + '\n\n' + marker + '\n', encoding='utf-8')
        gh('issue', 'comment', str(number), '-R', REPO, '--body-file', str(path))
    comments = json.loads(gh('issue', 'view', str(number), '-R', REPO, '--json', 'comments'))['comments']
    assert any(marker in comment['body'] for comment in comments)


def check_and_close(number):
    issue = json.loads(gh('issue', 'view', str(number), '-R', REPO, '--json', 'body,state'))
    body = issue['body'].replace('\r\n', '\n').replace('- [ ]', '- [x]')
    path = SUPPORT / f'closed-body-{number}.md'
    path.write_text(body, encoding='utf-8')
    gh('issue', 'edit', str(number), '-R', REPO, '--body-file', str(path))
    assert json.loads(gh('issue', 'view', str(number), '-R', REPO, '--json', 'body'))['body'].replace('\r\n', '\n').strip() == body.strip()
    if issue['state'] != 'CLOSED':
        gh('issue', 'close', str(number), '-R', REPO, '--reason', 'completed')
    assert json.loads(gh('issue', 'view', str(number), '-R', REPO, '--json', 'state'))['state'] == 'CLOSED'


assert state['push_mode'] == 'autonomous-approved'
subprocess.run([sys.executable, str(SUPPORT / 'verify_delivery.py'), '--check-only'], check=True, cwd=ROOT)
repo = json.loads(gh('repo', 'view', REPO, '--json', 'isPrivate,defaultBranchRef'))
assert repo['isPrivate'] and repo['defaultBranchRef']['name'] == 'main'
commit = state.get('implementation_commit') or subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert gh('api', f'repos/{REPO}/commits/{commit}', '--jq', '.sha') == commit
report_path = SUPPORT / 'acceptance.json'
report = json.loads(report_path.read_text(encoding='utf-8'))
report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
state['implementation_commit'] = commit
if state['phase'] != 'complete':
    state['phase'] = 'closing'
    if not any(event['id'] == 'T004-published-and-closing' for event in state['events']):
        state['events'].append({'id':'T004-published-and-closing','at':datetime.now(timezone.utc).isoformat(),'phase':'closing'})
    save()

details = {
    'core': ('app/config.py, datajud.py, queries.py, tribunals.py, cnj.py e testes', 'pytest tests/test_config.py tests/test_datajud.py tests/test_queries.py tests/test_tribunals.py tests/test_cnj.py', 'Registry oficial, MOD97/origem, filtros, limites, retry, auth/transporte/schema/parcial verificados. Movimento e período também passaram no smoke TJSP.'),
    'evidence': ('app/storage.py, app/extract.py e testes', 'pytest tests/test_storage.py tests/test_extract.py', 'Raw byte a byte, SHA256, provenance UTC, nomes exclusivos, assuntos aninhados e campos desconhecidos verificados.'),
    'interfaces': ('app/core.py, models.py, main.py, cli.py, README, pyproject, lockfile e testes', 'datajud --help; datajud health; pytest tests/test_core.py tests/test_cli.py tests/test_http.py', 'CLI/HTTP compartilham core; health offline, aliases, company/party unsupported, process e erros estruturados. R1 corrigido e revisão independente PASS.'),
    'discovery': ('app/discover.py, app/pagination.py, modelos/interfaces e testes', 'pytest tests/test_discover.py tests/test_pagination.py', 'Limite1000/página100/100páginas, guardas de loops e manifesto. RCD-01/02 corrigidos: excesso upstream recusado após raw e identidade incompleta preserva graus. Smoke real3candidatos/3páginas.'),
    'offline': ('app/storage.py, app/core.py, CLI/HTTP e testes', 'datajud extract <raw-file> --json; pytest tests/test_storage.py tests/test_core.py tests/test_cli.py tests/test_http.py', 'Sidecar validado, SHA256, origem original e extração nova. Reprocessamento real com chave ausente e busca proibida passou por core/CLI/HTTP.'),
    'validation': ('tests/, work/orchestration/support/ e receipts.md', 'pytest; python work/orchestration/support/verify_delivery.py --check-only', 'Cinco dimensões de revisão cobertas por três sessões independentes dos produtores, revisão cruzada e QA real. P0/P1=0; três P2 corrigidos e revalidados.'),
}
for key in ('core','evidence','interfaces','discovery','offline','validation'):
    issue = state['issues'][key]
    files, command, results = details[key]
    body = f'''## Handoff verificado — {key}

Objetivo e versão: DataJud Lite V0, commit [{commit[:7]}](https://github.com/{REPO}/commit/{commit}).
Arquivos: {files}.

Reprodução: `uv run {command}`; suíte global `uv run pytest`.
Resultado: {results}

Aceite global regenerado: **{report['tests']['passed']} passaram, {report['tests']['skipped']} pulados, zero falhas/erros**.
Relatório: `work/orchestration/support/acceptance.json`, SHA256 `{report_hash}`.
Snapshot de source: `{report['source_sha256']}`. Evidências reais verificadas:
{len(report['verified_raw_files'])} arquivos raw com SHA256; discovery {report['discovery_candidates']} candidatos em {report['discovery_pages']} páginas.
Opt-in integração real executado separadamente e passou. Raw/chave não estão no Git.

Limitações: symlink dinâmico sem permissão Windows; integração é skip no pytest normal;
dois avisos de depreciação no TestClient. Smoke real TJSP, sem promessa de snapshot/completude
ou inteiro teor. Tempos e desvios qi-epic documentados em `work/orchestration/receipts.md`.
Revisões atuais: PASS; findings R1/RCD-01/RCD-02 resolvidos. Próxima transição autorizada:
fechar esta issue e consolidar épico #1; não há funcionalidade adicional implícita.
'''
    comment_once(issue['number'], body, f'datajud-handoff-{issue["number"]}-{commit}')
    check_and_close(issue['number'])
    issue.update(status='closed', validated_commit=commit)
    transition = f'T005-close-issue-{issue["number"]}'
    if not any(event['id'] == transition for event in state['events']):
        state['events'].append({'id':transition,'at':datetime.now(timezone.utc).isoformat(),'phase':state['phase']})
    save()

subprocess.run([sys.executable, str(SUPPORT / 'verify_delivery.py'), '--check-only'], check=True, cwd=ROOT)
assert all(json.loads(gh('issue','view',str(issue['number']),'-R',REPO,'--json','state'))['state'] == 'CLOSED' for issue in state['issues'].values())
epic_body = f'''## Encerramento verificado

Implementação publicada em `{commit}`. Sub-issues #2–#7 fechadas com handoffs.
Critérios originais A–I e corrigidos A/B/C atendidos; cinco dimensões de revisão PASS.
Regressões finais: {report['tests']['passed']} testes passaram, {report['tests']['skipped']} skips conhecidos.
Relatório regenerado de aceite SHA256 `{report_hash}`; snapshot `{report['source_sha256']}`.

| Finding | Correção | Issue | Commit |
| --- | --- | --- | --- |
| R1/P2 | RecursionError estruturado com raw/provenance | #4 | {commit[:7]} |
| RCD-01/P2 | Recusa excesso de hits após preservação | #6 | {commit[:7]} |
| RCD-02/P2 | Fallback de identidade preserva graus | #6 | {commit[:7]} |

P0/P1 abertos: zero. P2/P3 funcionais pendentes: nenhum observado.
API real: processo TJSP4registros; discovery3candidatos/3páginas; movimento e período;
HTTP local health/search200; CLI raw byte exato; reprocessamento sem rede/API key.

Desvios: task-wrapper/obsidian-eval/qi-epic-close-check OpenCode indisponíveis;
ferramentas Codex, estado local, revisão em ondas e verificador local substituíram
o transporte/runtime. Medições de fila/coordenação ativa não instrumentadas e
explicitamente identificadas. Sem novo framework, sem gates técnicos repetidos.

Limitações técnicas no README: DataJud é descoberta de metadados, sem garantia de
completude/snapshot; inferência CNJ é origem; sem busca empresa/parte/inteiro teor.
Raw permanece local e ignorado. Próxima transição: publicar registro de encerramento
e parar; futuro jurisprudence-fetcher continua fora de escopo.
'''
comment_once(state['epic'], epic_body, f'datajud-epic-closed-{commit}')
check_and_close(state['epic'])
state['phase'] = 'complete'
state['epic_status'] = 'closed'
state['acceptance_sha256'] = report_hash
if not any(event['id'] == 'T006-epic-complete' for event in state['events']):
    state['events'].append({'id':'T006-epic-complete','at':datetime.now(timezone.utc).isoformat(),'phase':'complete'})
save()
print(json.dumps({'epic':state['epic'],'status':state['phase'],'commit':commit,'issues_closed':[item['number'] for item in state['issues'].values()]}))
