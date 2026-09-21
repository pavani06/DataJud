"""Owner root. Apply user scope correction once; inputs are this file and plan."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUPPORT = Path(__file__).resolve().parent
state_path = ROOT / 'work/orchestration/state.json'
state = json.loads(state_path.read_text(encoding='utf-8'))
if state['phase'] != 'implementation':
    raise SystemExit('Delta já passou da implementação; não repetir transição administrativa.')
repo = state['repo']


def gh(*args):
    return subprocess.check_output(['gh', *args], cwd=ROOT, text=True, encoding='utf-8').strip()


def update(number, name, addition):
    body = json.loads(gh('issue', 'view', str(number), '-R', repo, '--json', 'body'))['body'].replace('\r\n', '\n')
    if '## Correção de escopo — T002' not in body:
        body += '\n\n## Correção de escopo — T002\n' + addition + '\n'
    path = SUPPORT / f'updated-{name}.md'
    path.write_text(body, encoding='utf-8')
    gh('issue', 'edit', str(number), '-R', repo, '--body-file', str(path))
    assert json.loads(gh('issue', 'view', str(number), '-R', repo, '--json', 'body'))['body'].replace('\r\n', '\n').strip() == body.strip()


new_tasks = {
 'discovery': ('Descoberta estrutural paginada com candidatos e provenance', '''REC-005 · gap G5: falta operação DISCOVER na especificação corrigida.
Território: app/discover.py, app/pagination.py, testes respectivos; root integra modelos/CLI/HTTP.
Preservar app/core.py e módulos existentes. Inputs: tribunal + assunto/classe/movimento + datas.
Implementar limite 1..1000 e page_size 1..100, máximo 100 páginas, search_after isolado,
detecção de cursor/página repetida e ausência de cursor. Deduplicar por identidade do hit,
preservando registros de graus distintos. Cada página salva raw+extraído, candidato retém
provenance e agregado contém query_id/filtros/returned_hits/pagination. Manifesto persistido.
Não prometer completude/snapshot; não interpretar juridicamente. Company/party unsupported explícito.
CLI discover com subject/class/movement/from/to/limit/raw/json; POST /discover no mesmo core.
Aceite: uv run pytest tests/test_discover.py tests/test_pagination.py; smoke real filtrado
com duas páginas; limites e loops verificáveis. Depende #2/#3/#4; desbloqueia #5.
Handoff: versão, arquivos, comandos, resultados, limitações, findings e próxima transição.
'''),
 'offline': ('Reprocessar raw local sem rede e verificar provenance persistida', '''REC-006 · gap G6: extração anterior dependia de nova consulta.
Território storage/extract e testes: worker evidence; core/models/CLI/HTTP: root.
Salvar sidecar de provenance junto a cada raw, com hash bytes exatos, endpoint, UTC e query.
load_raw verifica hash e metadados antes de devolver payload/provenance; caminhos contidos
em data_dir; ausência de sidecar gera erro explícito sem fabricar origem. Guardar raw de erros
200 também, mas reextração não pode transformar payload parcial em sucesso.
Implementar datajud extract <raw-file> e POST /extract {raw_file:...}; nenhum acesso à rede
ou necessidade de API key. Saída normalizada nova, sem sobrescrever a original, vinculada
ao mesmo raw/hash/retrieved_at e com extracted_at separado.
Aceite: uv run pytest tests/test_storage.py tests/test_core.py tests/test_cli.py tests/test_http.py;
teste que falha se rede for invocada, adulteração raw/sidecar rejeitada, reextração determinística
em campos normalizados. Demonstrar com raw real previamente salvo. Depende #3/#4; desbloqueia #5.
Handoff: versão, arquivos, comandos, resultados, limitações, findings e próxima transição.
''')
}
for key, (title, body) in new_tasks.items():
    body = f'**Epic:** #{state["epic"]} · **Repo:** {repo}\n\n' + body + '\nPlano canônico: .omo/plans/2026-09-21-qi-loop-datajud.md. Push_mode autonomous-approved.\n'
    path = SUPPORT / f'issue-{key}.md'
    path.write_text(body, encoding='utf-8')
    if key not in state['issues']:
        url = gh('issue', 'create', '-R', repo, '--title', title, '--label', 'qi-loop', '--body-file', str(path))
        state['issues'][key] = {'number': int(url.rsplit('/', 1)[1]), 'status': 'planned', 'owner': None}
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    number = state['issues'][key]['number']
    assert json.loads(gh('issue', 'view', str(number), '-R', repo, '--json', 'body'))['body'].replace('\r\n', '\n').strip() == body.strip()
    node = json.loads(gh('api', f'repos/{repo}/issues/{number}'))
    children = json.loads(gh('api', f'repos/{repo}/issues/{state["epic"]}/sub_issues'))
    if not any(child['number'] == number for child in children):
        gh('api', f'repos/{repo}/issues/{state["epic"]}/sub_issues', '-X', 'POST', '-F', f'sub_issue_id={node["id"]}')

update(2, 'core', 'Acrescentar movimento/movimentos.codigo a queries após consulta oficial. Acrescentar app/cnj.py com normalize_cnj e infer_tribunal: Resolução 65/CNJ (https://atos.cnj.jus.br/atos/detalhar/119), resolução atualizadora TRF6 (https://atos.cnj.jus.br/atos/detalhar/4781). Número identifica origem, não todas as instâncias; inferência deve ser explícita, limitada a regras documentadas e permitir --tribunal. Testar formatado/sem máscara/inválido/ambíguo. Demais critérios preservados.')
update(4, 'interfaces', 'Acrescentar process, discover e extract <raw-file> CLI/HTTP, aliases --subject/--class/--movement/--from/--to. Company/party devem retornar unsupported_filter antes da rede. Manter os comandos anteriores quando compatíveis. README com três consultas reais, CandidateProcess e fronteira futura sem fetcher.')
update(5, 'validation', 'Aceite adicional: A processo real com raw/normalizado/provenance; B descoberta tribunal+subject/class+período com paginação e limite; C reprocessamento de raw salvo SEM rede/API key. Testar movimento real antes de declarar capacidade validada. Fixture real anonimizada para normalização. Não declarar completude de discovery.')
update(1, 'epic', f'Objetivo corrigido: SEARCH → DISCOVER → EXTRACT → PRESERVE PROVENANCE. Preservar componentes existentes. Novas sub-issues: #{state["issues"]["discovery"]["number"]} e #{state["issues"]["offline"]["number"]}. Critérios finais incluem processo, discovery paginado filtrado e reprocessamento offline. Sem inteiro teor/jurisprudence-fetcher. Aceites anteriores continuam válidos.')
for key, owner in {'core':'core','evidence':'evidence','interfaces':'root','validation':'api_research','discovery':'root','offline':'evidence+root'}.items():
    state['issues'][key].update(status='in_progress', owner=owner)
if not any(e['id'] == 'T002-scope-correction' for e in state['events']):
    state['events'].append({'id':'T002-scope-correction','at':datetime.now(timezone.utc).isoformat(),'phase':'implementation'})
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(state['issues'], ensure_ascii=False))
