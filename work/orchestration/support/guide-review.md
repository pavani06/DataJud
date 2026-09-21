# Revisão independente do guia de uso

Conclusão: **PASS — nenhum finding bloqueante ou material aberto.** Guia e link
do README conferidos após a redação, incluindo o ajuste de nomes de raw/sidecar.

Épico #8; redação #9; revisão #10. Revisor: trabalhador evidence. Produtor: root.
Escopo exclusivo de escrita do revisor: este relatório. Runtime, guia, Git/GitHub e
estado de coordenação não foram alterados pelo revisor.

## Auditoria inicial

Início UTC: `2026-09-21T19:38:19Z`. O guia ainda estava em redação nesta etapa
inicial. A revisão final e a evidência de exportação estão registradas adiante.

Foram lidos CLI, HTTP, modelos, configuração, persistência, README, `.env.example`
e as issues documentais. Cuidados enviados ao produtor antes da redação final:

- `.env` não é carregado pelo runtime; usar `uv run --env-file .env ...` ou ambiente
  configurado, inclusive no offline quando a pasta de dados foi personalizada.
- Extração offline recebe raw em `DATAJUD_DATA_DIR/raw`, com sidecar
  `nome.json.provenance.json` adjacente e nome original. Exportar ou renomear
  somente o raw não constitui um conjunto reprocessável.
- Para exportar fielmente, copiar arquivos persistidos é preferível a reserializar
  stdout. PowerShell 5 pode usar UTF-16 em `>`; `ConvertTo-Json` sem profundidade
  explícita também pode perder objetos. Raw original não deve ser reserializado.
- Houve confirmação concreta de stdout CP1252 no host Windows: uma captura Python
  de `uv run datajud --help` que presumia UTF-8 falhou no byte `0xE1`. A execução
  seguinte com `PYTHONUTF8=1` no ambiente do subprocesso capturou corretamente.
- CMD requer aspas duplas para os exemplos comuns; os caracteres de continuação
  diferem entre CMD, PowerShell e Bash. `curl` pode ser alias do PowerShell antigo.
- `--raw`/`--json` são exclusivos; discovery raw não é JSON único nem JSONL
  garantido. `extract` não tem `--raw`, e modo offline não recebe filtros.
- HTTP usa `date_from`/`date_to`; os aliases CLI `--from`/`--to` não são nomes de
  campos HTTP. HTTP aceita `class`/`subject`/`movement` além dos nomes portugueses.
- HTTP loopback é acesso local; não há MCP nem conexão automática de chat cloud.

## Comandos offline executados

No host foi usado o equivalente com `.tools/bin/uv.exe`, `--cache-dir .uv-cache`
e `--no-sync`, após instalação existente. O cache/runtime exigiu escalonamento.

| Comando | Resultado |
| --- | --- |
| `uv run datajud --help` | exit 0 |
| `uv run datajud search --help` | exit 0 |
| `uv run datajud process --help` | exit 0 |
| `uv run datajud discover --help` | exit 0 |
| `uv run datajud extract --help` | exit 0 |
| `uv run datajud health` | exit 0, status ok, service datajud-lite |
| `GET /health` via FastAPI TestClient | HTTP 200, mesmo corpo |

A auditoria HTTP utilizou `patch('app.datajud.DataJudClient.search',
side_effect=AssertionError('Unexpected network path'))`; portanto health não
passou pelo caminho de consulta externa. Não foi iniciada consulta CNJ real.
Nenhum teste novo permanente foi criado.

## Revisão final do documento

`docs/GUIA_DE_USO.md` foi lido integralmente e confrontado com CLI, modelos e
rotas. A ligação está presente em `README.md:10`. Conclusão UTC:
`2026-09-21T19:45:40Z`.

| Critério | Resultado |
| --- | --- |
| health, process, search, discover e extract com flags reais | PASS |
| `.env` explícito, marcador sem segredo, precedência do ambiente | PASS |
| PowerShell, Bash e CMD separados nas operações específicas | PASS |
| Exportação normalizada separada de raw e sidecar | PASS |
| Offline exige pasta, nome, sidecar e configuração coerentes | PASS |
| `process` é uma página; origem inferida não é tribunal atual | PASS |
| Limites discovery 1000/100/100 páginas e ausência de snapshot | PASS |
| Datas de ajuizamento, códigos numéricos e movimento sem filtro temporal próprio | PASS |
| Datas HTTP `date_from`/`date_to`, rotas e corpos conferidos | PASS |
| Prompt de agente local sem simulação de consulta ou alteração de software | PASS |
| Chat cloud recebe JSON; localhost não é exposto automaticamente | PASS |
| Claude Code, Codex, OpenCode, Pi e Herdr sem integração MCP inventada | PASS |
| Semântica de zero hits, múltiplos registros e hash informado versus verificado | PASS |

Refinamento editorial solicitado e resolvido pelo produtor: o padrão
`data/raw/*.json` da tabela também poderia selecionar sidecars. Em
`docs/GUIA_DE_USO.md:260`, o texto final usa `data/raw/<nome>.json` e a linha
seguinte identifica separadamente `<nome>.json.provenance.json`. Não permanece
finding aberto.

Os exemplos PowerShell usam captura UTF-8 e cópia do arquivo produzido, evitando
o erro real de codificação observado na auditoria inicial. Bash e CMD definem
`PYTHONUTF8` e `PYTHONIOENCODING` antes de redirecionar o JSON; o guia exige código
de saída zero e distingue arquivo vazio de resultado válido. Os exemplos HTTP
não misturam aspas Bash com CMD; `Invoke-RestMethod` evita o alias `curl` do
PowerShell antigo. O uso de `ConvertTo-Json` no corpo offline contém apenas
`raw_file`, portanto não trunca resultados aninhados.

## Prova offline de captura, cópia e reextração

Usado o raw de `checks.process_inferred` do relatório real já existente, sem
nova consulta externa. Raw e sidecar foram copiados, sem renomear, para:

```text
data/guide-review/ca126dfd087c4a38b5ac2af782f60326/raw/
```

Na sessão de auditoria, `DATAJUD_DATA_DIR` apontou para essa pasta de revisão e
`DATAJUD_API_KEY` ficou vazio. O mesmo padrão do guia foi exercitado:

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$saida = & .\.tools\bin\uv.exe run --cache-dir .uv-cache --no-sync datajud extract $guideRaw --json
if ($LASTEXITCODE -ne 0) { throw 'Offline extraction failed.' }
$consulta = ($saida -join "`n") | ConvertFrom-Json
Copy-Item -LiteralPath $consulta.extracted_path -Destination $guideCopy
```

`$guideRaw` e `$guideCopy` foram caminhos absolutos da pasta isolada; o uso do
ambiente em vez de `.env` evitou depender de chave/configuração privada. A captura
foi comparada ao texto UTF-8 efetivamente persistido e a cópia comparada byte a
byte. Confirmados caracteres não ASCII no conteúdo e hash inalterado do raw
original.

| Ambiente efetivamente executado | Resultado |
| --- | --- |
| PowerShell 7.6.5 | exit 0, mode offline, count 4; captura Unicode e cópia iguais |
| Windows PowerShell 5.1.26100.9444 | exit 0, mode offline, count 4; captura Unicode e cópia iguais |

O segundo teste invocou explicitamente
`C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe` com
`-NoProfile -NonInteractive`, validando a afirmação de compatibilidade 5.1 do
guia. Os dois testes mantiveram a API key vazia. A evidência real original não
foi sobrescrita; somente a pasta de revisão recebeu cópias e novas extrações.

## Limites da revisão

- Não houve execução de nova busca CNJ; os exemplos de consulta reutilizam o
  relatório de validação da V0.
- Bash/CMD e os corpos HTTP de consulta foram conferidos contra sintaxe e código;
  não houve nova execução de consultas nesses shells ou no servidor real.
- Inicialização dos assistentes não foi testada ponta a ponta pelo revisor; o
  produtor informou conferência nas fontes oficiais vinculadas. O guia declara
  esse limite e condiciona Herdr/Pi ambíguo às capacidades da sessão.
- Não foram instalados MCP, plugins, túneis ou integrações de nuvem. Esta entrega
  aprova o documento, não acrescenta garantias de execução desses produtos.
