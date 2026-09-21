# Revisão independente: Dados e análises possíveis

Data: **2026-09-21**. Revisor: subagente independente (não autor). Escrita
exclusiva do revisor: este relatório. Nenhum arquivo do repositório foi editado
e não houve `git commit`/`push`.

## Escopo e arquivos revisados

- `docs/DADOS_E_ANALISES.md` (novo; lido integralmente, 346 linhas; versão idêntica à
  commitada em `11ef741`, cujas linhas citadas abaixo foram reconferidas).
- Inserções em `README.md` (linhas 14–17 e 302–303) e `docs/GUIA_DE_USO.md`
  (linhas 10–11, 18–19, 180–181, 518–519), via `git diff README.md docs/GUIA_DE_USO.md`.
- Plano `.omo/plans/2026-09-21-datajud-dados-e-analises.md` (versão de 21:20 UTC).

Fontes de verdade usadas: `app/extract.py`, `app/core.py`, `app/discover.py`,
`app/cli.py`, `app/models.py`, `app/queries.py`, `app/storage.py`, `app/main.py`,
`app/pagination.py`; `tests/fixtures/datajud_anonymized.json`; glossário oficial e
página institucional do CNJ salvos em texto no scratchpad da sessão; raws e
normalizados reais em `data/raw/` e `data/extracted/` (6 raws, 12 hits; não
commitados, `data/` está no `.gitignore`), em especial
`data/raw/TJSP_20260921T205620727442Z_566c10c5…_c3a249e4….json` (4 hits do
processo público do README) e o raw anterior do mesmo processo
(`TJSP_20260921T204021250944Z_da478d2f….json`).

## Comandos executados

| Comando | Resultado |
| --- | --- |
| `git status --short`; `git diff README.md docs/GUIA_DE_USO.md` | Só inserções; comandos e exemplos existentes intactos. |
| `uv run --no-sync python` com `app.extract.extract_response(fixture, provenance)` e comparação com o JSON da seção 7 | Igual ao documento, inclusive ordem das chaves e `datajud_id`/`datajud_index`. |
| Script de análise do raw `…205620727442Z…` (contagens, ids, órgãos, formatos, duplicatas, complementos) | Ver tabela de checagens e findings DA-01, DA-03, DA-08, DA-09. |
| Comparação dos dois raws do mesmo processo (20:40 e 20:56) ignorando `took` | Payloads idênticos; `took` 356 vs 761; SHA-256 distintos (DA-02). |
| Varredura dos 6 raws da sessão (`nivelSigilo`, `dataAjuizamento`, `sistema`, `formato`, campos extras, precisão de `@timestamp`) | `nivelSigilo` 0 em 12/12; 6 ISO-Z e 6 compactos; `sistema` SAJ/3 em 10/12 e `Inválido`/-1 em 2/12 (DA-10); nenhum `extra_fields`. |
| Snippet Python da seção 8 extraído para `rota.py` e executado contra `data/extracted/TJSP_20260921T205620727442Z_…json` | exit 0; imprime rota de 4 órgãos no registro mais recente e "(sem órgão por movimento neste registro)" nos outros 3. |
| `curl -sS -o /dev/null -w "%{http_code}" --max-time 30 <url>` para as 6 URLs externas | Todas `200`. |
| Script de âncoras (regra GitHub) e links relativos em README, guia e documento | Todas as 11 âncoras do documento, as 2 do guia para o documento e todos os arquivos relativos resolvem. |
| Leitura de envelopes reais (`search/process`, `extract` offline, manifesto discovery) | Confirma chaves do envelope (DA-04 a DA-07). |
| `uv run --no-sync pytest -q` (offline) | 406 passed, 1 skipped. |

## Tabela de checagens

| O que foi checado | Como | Resultado |
| --- | --- | --- |
| Exemplo da seção 7 corresponde ao extrator | `extract_response` sobre a fixture; comparação dict a dict e da ordem de chaves | PASS (idêntico; `raw_sha256`/`raw_file` ilustrativos, como declarado) |
| Dicionário da seção 2 vs `app/extract.py` `_FIELDS` (L8–18), `extra_fields` (L57–58), `datajud_id`/`datajud_index` (L59–65) | Leitura do código | PASS (nomes, achatamento de `assuntos`, ausência de invenção de valores) |
| Definições atribuídas ao glossário (id, `dataHoraUltimaAtualizacao`, `@timestamp`, `orgaoJulgador.codigo` "atual", `codigoOrgao`/`nomeOrgao`, `grau`, tipos) | Confronto com `glossario.txt` | PASS (todas constam; paráfrases fiéis) |
| Frases atribuídas ao CNJ na seção 1 ("capas processuais e movimentações", "proteção dos processos sigilosos e das informações das partes envolvidas", Portaria n. 160/2020) | Confronto com `api-publica.txt` | PASS |
| Envelope da seção 3 vs `core.py` L79–84, L122–129, L151–158 e `discover.py` L41, L62–81 | Leitura do código e de envelopes reais em `data/extracted` | PARCIAL: DA-04, DA-05, DA-06, DA-07, DA-16 |
| `tribunal_resolution` (`method`, `tribunal`, `process_number`, `note`) só em `process` | `core.py` L103–106 | PASS |
| `unsupported_filter` para `--company`/`--party` antes da consulta | `core.py` L32–34 (`check_supported`), chamado em `search` e `discover`; `cli.py` L116–117; `main.py` | PASS (também vale para HTTP: DA-15) |
| Filtros e aliases citados (`--class/--subject/--movement`, período sobre ajuizamento, movimento sem data) | `cli.py` L104–112, `queries.py` L130–152 | PASS |
| Raw: 4 registros, mesmo número/classe/grau/ajuizamento | Script | PASS |
| Raw: ids `TJSP_386_G1_<órgão>_<n>` ×3 e `TJSP_G1_<n>` (mais recente, 2026-09-12) | Script | PASS |
| Raw: "cada um sob um órgão julgador diferente" | Script: códigos 18457, 10542, 18294, **10542** | FAIL → DA-01 |
| Raw: `data_ajuizamento` em ISO-Z (1) e `AAAAMMDDHHMMSS` (3) | Script | PASS |
| Raw: `codigoMunicipioIBGE` presente (1), ausente (2), `null` (1) | Script | PASS |
| Raw: `orgaoJulgador` por movimento só em um registro, `codigo` string | Script: só no hit 4, 81/82 movimentos, 81× `str` | PASS na observação; plural do texto → DA-08 |
| Raw: 982 e 123 ambos "Remessa" | Script | PASS |
| Raw: 82 movimentos (2020–2026), 4 órgãos na rota, 41 em 2023, redistribuição em 2023 para outra RAJ | Script e snippet | PASS |
| Raw: 294 movimentos nos 4 registros; 12 "Outras Decisões" (12164) | Script | PASS |
| Raw: "Recebimento e Remessa eram 176 de 294" | Script: 132→106, 982→70, 123→6 | 176 só sem o código 123 (182 por nome) → DA-03 |
| Raw: variáveis de complemento (`motivo_da_remessa`, `tipo_de_documento` com certidão/ofício/mandado/outros, `tipo_de_distribuicao_redistribuicao` com sorteio/dependência/competência exclusiva, `tipo_de_conclusao`, `tipo_de_peticao`) | Script | PASS (exatamente essas 5, nenhuma outra) |
| Raw: exemplo de complemento da seção 4 (18/`motivo_da_remessa`, 40/`outros motivos`) | Script | PASS |
| Raw: `nivel_sigilo` sempre 0; `sistema` SAJ código 3; `formato` Eletrônico | Varredura dos 6 raws | PASS para sigilo/formato; `sistema` também `Inválido`/-1 em 2 hits → DA-10 |
| Raw: movimentos idênticos no mesmo instante | Script (chave: JSON completo do movimento) | Observado até **11** cópias idênticas (Recebimento 132 e Remessa 982) → DA-09 |
| Raw: lista de movimentos fora de ordem cronológica | Script | Confirmado em 2 dos 4 registros (apoia o conselho da seção 4) |
| Raw: nomes de órgão em caixa alta com e sem acentos | Script | PASS |
| Raw: `dataHora` com `Z` | Script: 294/294 | PASS |
| Códigos citados na seção 8 (26, 36, 132, 982, 123, 92, 11383, 12164) com esses nomes | Script | PASS (todos presentes no raw com os nomes citados) |
| `raw_sha256` como sinal de mudança | Diff dos dois raws do mesmo processo | FAIL → DA-02 |
| Snippet da seção 8 | Execução | PASS |
| Links externos (6) | curl | PASS (200) |
| Âncoras e links relativos | Script | PASS |
| README/guia: inserções coerentes com o conteúdo do documento, sem alterar comandos | Diff | PASS |
| Plano vs entrega | Leitura | Coerente: seções previstas existem; links nos pontos previstos; raw usado (20:56) anterior à redação (21:17); `work/orchestration/dados-analises-state.json` ainda não existe, o que o plano prevê para o commit de fechamento |
| Regras AGENTS.md (sem interpretação jurídica, zero hits, sem promessas, sem raw/.env/chave, textos como dados, V0 sem MCP/LLM/RAG) | Leitura | PASS (só contagens do processo público e vocabulário TPU; sem nomes de órgão do raw; `data/` ignorado pelo Git) |

## Findings

### Bloqueantes

Nenhum. Não há interpretação jurídica, promessa de inteiro teor/partes/completude,
dado recuperado, `.env` ou chave no documento; o processo público citado é o mesmo
do README e só aparecem contagens e vocabulário da TPU.

### Importantes

**DA-01 (importante)** — `docs/DADOS_E_ANALISES.md`, seção 6, L170–172 e L155–159, L165.
Trecho: "4 registros com o mesmo número, classe, grau e ajuizamento, cada um sob um
órgão julgador diferente". Evidência (raw `…205620727442Z…`): `orgaoJulgador.codigo`
dos 4 registros = 18457, 10542, 18294 e **10542**; os hits 2 e 4 têm o mesmo órgão
(código e nome iguais; o quarto só acrescenta `codigoMunicipioIBGE: null`). Há
**3** órgãos distintos, não 4. Consequências no texto: (a) a inferência da L156 ("O
DataJud guarda, portanto, um documento por combinação dessas partes") é contrariada
pela própria observação: dois documentos compartilham Tribunal, Classe, Grau, Órgão e
Número e diferem só pelo formato do `id` (`TJSP_386_G1_10542_<n>` vs `TJSP_G1_<n>`);
(b) a linha da tabela "Qual órgão indexou o registro | `orgao_julgador.codigo` e o
trecho correspondente de `provenance.datajud_id`" não distingue esses dois registros
e conflita com a seção 10 ("Não faça parse do `id`"). Correção sugerida: "4 registros
… sob **3** órgãos julgadores distintos; dois registros compartilham o mesmo órgão e
se distinguem apenas pelo formato do `id`"; trocar "portanto" por "em regra" e
acrescentar que a unicidade dessa chave não se confirmou na observação; na tabela,
"Qual registro é qual | `provenance.datajud_id` (igual a `id`); `orgao_julgador.codigo`
não é único entre registros do mesmo número". Os "4 órgãos" da seção 8 referem-se à
rota por movimento do registro mais recente e estão corretos.

**DA-02 (importante)** — seção 8, L244–246, item "Mudanças ao longo do tempo".
Trecho: "comparar `data_hora_ultima_atualizacao`, a quantidade de movimentos e o
`raw_sha256` da proveniência revela se algo mudou desde a coleta anterior".
Evidência: os dois raws do mesmo processo gravados na sessão (20:40:21 e 20:56:20)
têm payloads idênticos exceto `took` (356 vs 761 ms) e SHA-256 diferentes
(`da478d2f…` vs `566c10c5…`). Como o hash cobre os bytes completos do corpo, ele
muda a cada coleta mesmo sem alteração de dados; usá-lo como sinal de mudança gera
falso positivo sempre. Correção sugerida: remover `raw_sha256` desse item e indicar
comparar `results` sem `provenance` (ou um hash desse conteúdo), além de
`data_hora_ultima_atualizacao` e contagem de movimentos; opcionalmente registrar na
seção 10 que o raw contém `took`, campo volátil da fonte.

### Menores

**DA-03 (menor)** — seção 8, L250–251. "Recebimento e Remessa eram 176 de 294
movimentos". Contagem no raw: Recebimento (132) = 106, Remessa (982) = 70, Remessa
(123) = 6. Por nome são **182**; 176 só vale para os códigos 132 + 982. Como o
documento afirma que 123 também é "Remessa" (seção 5) e recomenda agrupar por
código, explicitar: "Recebimento (132) e Remessa (982) eram 176 de 294; com Remessa
(123), 182".

**DA-04 (menor)** — seção 3, L84. "`next_search_after` … ausente quando não há."
`core.py` L74–77 e L83: em `search`/`process` a chave está sempre presente e vale
`null` quando não há hits ou quando o cursor não avançou; a chave só é ausente em
`extract <raw-file>` (L122–129); em `discover` ela fica em
`discovery.pagination.next_search_after`. Corrigir para "`null` quando não há
próxima página; ausente em `extract <raw-file>`; em `discover`, dentro de
`discovery.pagination`".

**DA-05 (menor)** — seção 3, L85. "A nota de paginação sem snapshot está sempre
presente." Verdadeiro só em `search`/`process` (`core.py` L71). Em `extract
<raw-file>` `warnings` é `[]` quando há resultados (`core.py` L128; confirmado no
envelope `…_extract_…json` da sessão); em `discover` a nota tem outro texto
("Discovery é uma seleção de candidatos…", `discover.py` L62). Reescrever por
comando.

**DA-06 (menor)** — seção 3, L91–92. "`pages` (uma entrada por página, com raw,
proveniência e candidatos)". `discover.py` L41: cada entrada tem `raw_path`,
`extracted_path`, `provenance` e `count`; os candidatos ficam apenas em `results`
(confirmado no manifesto `discovery_73d122bb…json`). Trocar "candidatos" por
"`count`" e citar `extracted_path`.

**DA-07 (menor)** — seção 3, tabela L77–89. Faltam as chaves de topo `source`
(`CNJ/DataJud`) e `tribunal`, presentes em todos os envelopes (`core.py` L79 e L123;
`discover.py` L68–69). Acrescentar uma linha.

**DA-08 (menor)** — seção 4, L122 ("Presente só em registros mais recentes") e
seção 10, L314 ("só em registros recentes"). Observação real: presente em **um** dos
quatro registros (o mais recente, com `id` fora do padrão), em 81 de 82 movimentos.
O plural generaliza a partir de n = 1. Sugestão: "Observado em apenas um dos quatro
registros (o mais recente); não presuma o campo em registros novos de outros
tribunais".

**DA-09 (menor)** — seção 4, L130–131. "Observado: o mesmo movimento repetido no
mesmo instante (dois "Recebimento" idênticos)." A observação é bem mais forte: nos 4
registros há até **11** cópias integralmente idênticas (código, nome, `dataHora`,
complementos e, no registro com órgão por movimento, o mesmo órgão) de Recebimento
(132) e de Remessa (982) em três instantes de 2023, além de pares em 2023–2025. Ajustar
o texto ("até 11 cópias idênticas de um mesmo Recebimento ou Remessa") para que a
ressalva da seção 10 (deduplicar antes de contar atos) tenha o peso correto.

**DA-10 (menor)** — seção 2, L63 (`sistema`: "Observado `SAJ` (código 3) no TJSP") e
seção 10. Nos raws da mesma sessão (páginas de discovery), 2 dos 12 hits trazem
`sistema` = `{"codigo": -1, "nome": "Inválido"}`. Não é falso, mas omite uma ressalva
de qualidade útil a quem automatiza: acrescentar "também observado `Inválido`
(código -1) em candidatos da descoberta; não trate `sistema.codigo` como sempre
válido".

### Editoriais

**DA-11 (editorial)** — seção 10. Sugerir linha sobre precisão fracionária variável
de `timestamp`/`data_hora_ultima_atualizacao` (observado `.792Z`, `.338074Z`,
`.290930875Z` nos 4 registros). `datetime.fromisoformat` do Python 3.12 aceita os
três, mas comparação textual entre precisões diferentes exige normalização.

**DA-12 (editorial)** — seção 11, L329. "Datas e horas estão em UTC." O formato
compacto `AAAAMMDDHHMMSS` não traz fuso; observou-se que coincide dígito a dígito
com o valor `Z` do registro em ISO (`2020-06-02T14:53:02.000Z` ↔ `20200602145302`),
mas isso não é documentado pelo CNJ. Sugestão: "Datas e horas com sufixo `Z` estão
em UTC; o formato compacto não declara fuso (observado coincidindo com o valor UTC)".

**DA-13 (editorial)** — seção 2, L54. `tribunal`: "Coincide com o alias consultado."
O valor é a sigla (`TJSP`, igual a `provenance.tribunal`); o alias é
`api_publica_tjsp` (`provenance.endpoint_alias`/`datajud_index`). Trocar por
"Coincide com a sigla consultada (`provenance.tribunal`)".

**DA-14 (editorial)** — seção 2, L70–71. "O glossário não lista `sistema` e
`formato` como obrigatórios". O glossário não marca campo algum como obrigatório;
a frase sugere que outros seriam. Reescrever: "O glossário não marca nenhum campo
como obrigatório nem garante…".

**DA-15 (editorial)** — seção 9, L294–295. "a CLI rejeita `--company` e `--party`".
A verificação está no core compartilhado (`DataJudService.check_supported`), logo
`POST /search` e `POST /discover` com `company`/`party` também devolvem
`unsupported_filter` (422). Escrever "a CLI e o HTTP rejeitam".

**DA-16 (editorial)** — seção 3, L79. Em erro podem existir também
`error.upstream_status`, `error.raw_path` e `error.provenance` (`core.py`
L151–158) e, em corpo HTTP inválido, `error.details` sem `message` (`main.py` L29).
Mencionar como opcionais, se couber.

## Veredito

**FAIL** — há 2 findings importantes (DA-01, DA-02), 8 menores (DA-03 a DA-10) e
6 editoriais (DA-11 a DA-16); nenhum bloqueante. Estrutura, dicionário do registro,
exemplo da seção 7, definições do glossário, códigos citados, snippet, links e
âncoras estão corretos; a suíte offline passa. Após corrigir DA-01 e DA-02 (e, de
preferência, DA-03 a DA-10), o documento fica apto a PASS COM CORREÇÕES ou PASS.

## Rechecagem do delta

Data: **2026-09-21**. Objeto: correções do autor em `docs/DADOS_E_ANALISES.md`
(delta lido via `git diff` contra `11ef741`; durante a rechecagem o autor commitou
essa mesma versão como `0bdea12`, idêntica ao texto reconferido). Só esse arquivo mudou;
`app/`, README, guia e plano estão como na revisão original, logo as referências de
código citadas acima permanecem válidas.

Reconferido:

- Diff completo e leitura integral do documento atual (356 linhas).
- DA-01, DA-03, DA-08, DA-09, DA-10, DA-11 contra os 6 raws da sessão em `data/raw/`
  (12 hits), com recontagem no raw `…205620727442Z…`: 294 movimentos; 132 = 106,
  982 = 70, 123 = 6 (176 / 182); máximo de 11 cópias integralmente idênticas de um
  movimento; `orgaoJulgador.codigo` por registro = 18457, 10542, 18294, 10542 (3
  distintos), sendo o mais recente (`TJSP_G1_<n>`) o que compartilha órgão com
  `TJSP_386_G1_10542_<n>`; `_id == id` em 12/12 hits; órgão por movimento só no
  registro mais recente do processo (81/82) e em nenhum candidato da descoberta;
  `sistema` `Inválido`/-1 exatamente nos 2 hits das páginas de discovery (queries
  `bool/filter` por classe e período); precisão fracionária: `@timestamp` 3/6/9
  dígitos, `dataHoraUltimaAtualizacao` 3/6.
- DA-02 contra os dois raws do mesmo processo (idênticos exceto `took`).
- DA-04 a DA-07 e DA-16 contra `app/core.py` (L71–84, L122–129, L151–158),
  `app/discover.py` (L41, L62–81) e `app/main.py` (L23, L29).
- Âncoras e links relativos: 33 verificados em README, guia e documento, todos
  resolvem; headings do documento inalterados em relação a `11ef741`.
- Bloco do snippet (seção 8) e exemplo da seção 7: idênticos a `11ef741`; snippet não
  reexecutado por não ter mudado (execução anterior: exit 0).
- URLs externas: 6, todas `200`.

| Finding | Status | Evidência curta |
| --- | --- | --- |
| DA-01 | resolvido | L159 "Em regra"; L162–163 admite chave não única; L169 usa `provenance.datajud_id` (igual a `id`, confirmado 12/12) e nega unicidade de `orgao_julgador.codigo`; L174–179 "3 órgãos julgadores distintos", dois registros no mesmo órgão distinguidos pelo formato do id, o `TJSP_G1_<número>` sendo o mais recente. Confere com o raw. |
| DA-02 | resolvido | L249–253 compara `results` sem `provenance`, veta `raw_sha256` e explica `took`; L327 nova linha na seção 10. Confere com os raws (`took` 356 vs 761, resto idêntico). |
| DA-03 | resolvido | L258–259 "Recebimento (132) e Remessa (982) eram 176 de 294 … 182 contando a Remessa de código 123". Confere: 106 + 70 = 176; + 6 = 182. |
| DA-04 | resolvido | L85: `null` quando não há; ausente em `extract <raw-file>`; em `discover` dentro de `discovery.pagination`. Confere com `core.py` L74–77/L83/L122–129 e `discover.py` L79. |
| DA-05 | resolvido | L86 distingue `search`/`process` (nota de paginação sempre), `discover` (nota de seleção) e `extract <raw-file>` (vazio com resultados). Confere com `core.py` L71/L128 e `discover.py` L62. |
| DA-06 | resolvido | L92–94: `pages` com `raw_path`, `extracted_path`, `provenance`, `count`; candidatos só em `results`. Confere com `discover.py` L41. |
| DA-07 | resolvido | L80 acrescenta `source`/`tribunal`. Confere com `core.py` L79/L123 e `discover.py` L68–69. Nit em DA-17. |
| DA-08 | resolvido | L124 "apenas um dos quatro registros do exemplo, o mais recente"; L321 "em apenas um registro". Confirmado também nos candidatos de discovery (0 movimentos com órgão). |
| DA-09 | resolvido | L132–134 e L319: "até 11 cópias integralmente idênticas … código, nome, `dataHora` e complementos iguais". Confere (máximo 11). |
| DA-10 | resolvido | L63 e L326: `Inválido` (código -1) em candidatos da descoberta. Confere: 2 hits, ambos de páginas de discovery. |
| DA-11 | resolvido | L325 nova linha sobre precisão fracionária. Nit em DA-19. |
| DA-12 | resolvido | L339–341: só o sufixo `Z` garante UTC; compacto sem fuso, observado coincidindo com o valor UTC. Confere (`2020-06-02T14:53:02.000Z` ↔ `20200602145302`). Nit em DA-18. |
| DA-13 | resolvido | L54 "Coincide com a sigla consultada (`provenance.tribunal`)". |
| DA-14 | resolvido | L70–71 "não marca nenhum campo como obrigatório". |
| DA-15 | resolvido | L300–302 "a CLI e o HTTP rejeitam `company` e `party`". Confere com `core.py` L32–34 chamado em `search`/`discover` e rotas de `main.py`. |
| DA-16 | parcialmente (editorial) | L79 cita `error.upstream_status`, `error.raw_path`, `error.provenance` e `error.details`, mas mantém "há `error.code` e `error.message`" sem dizer que, em corpo HTTP inválido, `error.details` vem **no lugar** de `error.message` (`main.py` L29). Sugestão: "…ou, em corpo HTTP inválido, `error.details` em vez de `error.message`". |

Ressalvas editoriais residuais introduzidas pelo delta (nenhuma altera fatos
verificados nem bloqueia o commit):

- **DA-17 (editorial)** — L80 "Presentes em todos os envelopes": os envelopes de erro
  (`core.py` L151–158, `main.py` L23/L29, `cli.py` L100) não têm `source`/`tribunal`.
  Escrever "em todos os envelopes de sucesso".
- **DA-18 (editorial)** — L340 "coincidindo com o valor UTC do mesmo registro em ISO":
  o valor em ISO está em **outro registro do mesmo processo** (hit 1), não no mesmo
  registro. Escrever "do mesmo processo em outro registro".
- **DA-19 (editorial)** — L325 "(3, 6 ou 9 dígitos)": 9 dígitos só foram observados em
  `timestamp`; `data_hora_ultima_atualizacao` apareceu com 3 ou 6. Especificar por campo.
- **DA-20 (editorial)** — L252 e L327 "muda a cada coleta": só é garantido quando `took`
  difere; "tende a mudar a cada coleta" é mais preciso. A consequência prática está correta.
- **DA-21 (editorial)** — L259 tem 128 caracteres em parágrafo corrido; quebrar a linha
  como o restante do texto.

Veredito final atualizado: **PASS COM CORREÇÕES** — nenhum bloqueante ou importante
permanece; DA-01 a DA-15 resolvidos e reconferidos contra código e raws; DA-16
parcialmente resolvido e DA-17 a DA-21 são ajustes editoriais opcionais, que o autor
pode aplicar no commit de fechamento sem nova rodada de revisão.
