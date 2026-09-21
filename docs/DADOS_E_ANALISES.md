# Dados e análises possíveis com o DataJud

O que cada consulta devolve, o que cada campo significa, o que se pode derivar
desses metadados e o que a fonte não fornece. Complementa o
[guia de uso](GUIA_DE_USO.md), que ensina a executar as consultas, e o
[README](../README.md), que documenta comandos, limites e arquitetura.

Base deste documento, conferida em **21/09/2026**: o
[glossário de dados oficial](https://datajud-wiki.cnj.jus.br/api-publica/glossario/)
da API Pública, a [página institucional da API](https://www.cnj.jus.br/sistemas/datajud/api-publica/),
o extrator do projeto (`app/extract.py`) e a fixture anonimizada
`tests/fixtures/datajud_anonymized.json`. Quando o texto diz **observado**,
trata-se de comportamento visto em consultas reais ao TJSP nessa data, não de
garantia documentada pelo CNJ. Contagens observadas podem mudar a qualquer momento.

Atalhos: [camadas](#1-o-que-a-fonte-entrega) ·
[dicionário do registro](#2-dicionário-do-registro-normalizado) ·
[envelope](#3-campos-do-envelope-da-consulta) ·
[movimentos](#4-anatomia-de-um-movimento) ·
[códigos](#5-códigos-onde-consultar-e-como-não-errar) ·
[registros múltiplos](#6-vários-registros-para-um-mesmo-número) ·
[exemplo](#7-exemplo-de-registro-normalizado) ·
[análises](#8-o-que-se-deriva-dos-metadados) ·
[o que não existe](#9-o-que-a-fonte-não-fornece) ·
[qualidade](#10-ressalvas-de-qualidade-observadas) ·
[limites](#11-limites-de-interpretação).

## 1. O que a fonte entrega

O CNJ descreve a API Pública como acesso aos **metadados** de processos judiciais:
"capas processuais e movimentações", com "proteção dos processos sigilosos e das
informações das partes envolvidas", segundo os critérios da Portaria CNJ n. 160/2020.
Cada registro devolvido traz três camadas:

| Camada | Conteúdo | Pergunta que responde |
| --- | --- | --- |
| Identificação | número CNJ, tribunal, grau, órgão julgador, sistema, formato, nível de sigilo | Que processo é e onde está indexado |
| Classificação | classe e assuntos, codificados pelas Tabelas Processuais Unificadas | De que tipo de processo se trata |
| Trajetória | movimentos com data e hora, complementos tabelados e órgão do movimento | Por onde passou, quando e com que frequência |

Não há partes, advogados, valores, texto de decisões nem documentos. A seção 9
consolida essa lista.

## 2. Dicionário do registro normalizado

`search`, `process`, `discover` e `extract` devolvem um envelope com `results`.
Cada item de `results` é um registro normalizado, um por hit do DataJud. O extrator
renomeia os campos para português em snake_case, mantém os tipos da fonte e não
inventa valores: campo ausente na fonte fica ausente no registro.

| Campo normalizado | Campo na fonte | Tipo | Significado segundo o glossário oficial | Observações |
| --- | --- | --- | --- | --- |
| `numero_processo` | `numeroProcesso` | texto | Numeração única CNJ sem formatação | 20 dígitos. Trate como texto para preservar zeros iniciais. |
| `tribunal` | `tribunal` | texto | Sigla do tribunal | Coincide com a sigla consultada (`provenance.tribunal`). |
| `grau` | `grau` | texto | Instância: `G1`, `G2`, `JE` etc. | |
| `classe` | `classe` | objeto `{codigo, nome}` | Classe processual conforme TPU | Ver seção 5. |
| `assuntos` | `assuntos` | lista de `{codigo, nome}` | Assuntos do processo conforme TPU | O extrator achata listas aninhadas em uma lista simples. |
| `orgao_julgador` | `orgaoJulgador` | objeto `{codigo, nome, codigoMunicipioIBGE}` | Serventia ou vara **atual** do processo; código IBGE do município | `codigoMunicipioIBGE` observado ausente ou `null` em parte dos registros. |
| `data_ajuizamento` | `dataAjuizamento` | data e hora | Data de ajuizamento da capa do processo | Observado em dois formatos: ISO 8601 com `Z` e compacto `AAAAMMDDHHMMSS`. |
| `data_hora_ultima_atualizacao` | `dataHoraUltimaAtualizacao` | data e hora | Controle interno: instante de inserção do dado na origem | Indica qual registro é o mais recente. |
| `timestamp` | `@timestamp` | data e hora | Controle interno: atualização do documento no índice | Chave de ordenação e paginação. Não é data processual. |
| `nivel_sigilo` | `nivelSigilo` | inteiro | Nível de sigilo | Observado sempre `0` nos registros consultados. |
| `sistema` | `sistema` | objeto `{codigo, nome}` | Sistema processual de origem no tribunal | Observado `SAJ` (código 3) no TJSP e também `Inválido` (código -1) em candidatos da descoberta. |
| `formato` | `formato` | objeto `{codigo, nome}` | Processo físico ou eletrônico | |
| `id` | `id` | texto | Chave `Tribunal_Classe_Grau_OrgaoJulgador_NumeroProcesso` | Ver seção 6. |
| `movimentos` | `movimentos` | lista | Movimentos processuais | Estrutura na seção 4. |
| `extra_fields` | qualquer outro | objeto | Campos da fonte fora da lista acima | Só existe quando a fonte enviar algo não previsto. |
| `provenance` | gerado localmente | objeto | Fonte, tribunal, alias e endpoint, `retrieved_at`, query enviada, `raw_sha256`, `raw_file`, `datajud_id`, `datajud_index` | `datajud_id` e `datajud_index` vêm de `_id` e `_index` do hit. |

O glossário não marca nenhum campo como obrigatório nem garante a presença de todos
os campos em todos os tribunais. Leia o que veio; não presuma o que faltou.

## 3. Campos do envelope da consulta

O envelope é o que a CLI imprime com `--json` e o que as rotas HTTP devolvem.

| Campo | Significado |
| --- | --- |
| `query_status` | `success` ou `error`. Em erro, há `error.code` e `error.message`; podem existir `error.upstream_status`, `error.raw_path` e `error.provenance`, ou `error.details` quando o corpo HTTP é inválido. |
| `source`, `tribunal` | `CNJ/DataJud` e a sigla consultada. Presentes em todos os envelopes. |
| `found` | `true` quando houve ao menos um hit. |
| `count` | Registros nesta página ou candidatos distintos na descoberta. Não é número de processos únicos. |
| `total` | `{value, relation}` informado pela fonte. `eq` é total exato; `gte` é limite inferior. |
| `results` | Registros normalizados da seção 2. |
| `next_search_after` | Cursor da próxima página em `search` e `process`; `null` quando não há. Ausente em `extract <raw-file>`; em `discover`, fica em `discovery.pagination`. |
| `warnings` | Avisos do serviço. Em `search` e `process` inclui sempre a nota de paginação sem snapshot; em `discover`, a nota de que o conjunto é uma seleção de candidatos; em `extract <raw-file>`, vazio quando há resultados. |
| `tribunal_resolution` | Só em `process`: `method` (`provided` ou `cnj_origin`), `tribunal`, `process_number`, `note`. |
| `raw_path`, `extracted_path` | Arquivos gravados desta consulta. |
| `provenance` | Proveniência do envelope, igual à de cada registro sem `datajud_id`/`datajud_index`. |
| `extracted_at`, `mode` | Só em `extract <raw-file>`: instante da reextração e `offline`. |

A descoberta acrescenta `schema_version` (`candidate-process-set/1`), `pages` (uma
entrada por página, com `raw_path`, `extracted_path`, `provenance` e `count`; os
candidatos ficam só em `results`), `manifest_path` e o bloco
`discovery` com `query_id`, `filters`, `created_at`, `returned_hits` e `pagination`
(`limit`, `page_size`, `pages`, `max_pages`, `duplicates_removed`, `stop_reason`,
`next_search_after`, `complete_snapshot`, sempre `false`).

## 4. Anatomia de um movimento

Cada item de `movimentos` descreve um ato registrado no sistema do tribunal.
Exemplo ilustrativo, com o vocabulário da fixture anonimizada e complementos
observados na fonte:

```json
{
  "codigo": 982,
  "nome": "Remessa",
  "dataHora": "2020-01-02T12:00:00.000Z",
  "complementosTabelados": [
    {"codigo": 18, "descricao": "motivo_da_remessa", "valor": 40, "nome": "outros motivos"}
  ],
  "orgaoJulgador": {"codigo": "1", "nome": "Órgão fictício para testes"}
}
```

| Campo | Significado segundo o glossário | Observações |
| --- | --- | --- |
| `codigo`, `nome` | Código e descrição da movimentação conforme TPU | O código é a chave; o nome é a descrição da fonte. |
| `dataHora` | Data e hora da ocorrência | Observado em UTC com `Z`. |
| `complementosTabelados[]` | Lista de complementos daquele movimento | Nem todo movimento tem complementos. |
| `complementosTabelados[].codigo`, `.descricao` | Código e descrição da **variável** do movimento | Exemplo: 18, `motivo_da_remessa`. |
| `complementosTabelados[].valor`, `.nome` | Código e descrição do **valor** do complemento | Exemplo: 40, `outros motivos`. |
| `orgaoJulgador` | Órgão julgador do movimento | Glossário nomeia `codigoOrgao` e `nomeOrgao`; observado `codigo` e `nome`, com `codigo` como texto. Observado em apenas um dos quatro registros do exemplo, o mais recente; não presuma o campo. |

Variáveis de complemento observadas em 21/09/2026: `motivo_da_remessa`,
`tipo_de_documento` (certidão, ofício, mandado, outros documentos),
`tipo_de_distribuicao_redistribuicao` (sorteio, dependência, competência exclusiva),
`tipo_de_conclusao` e `tipo_de_peticao`. A lista completa de variáveis e valores
está na tabela de movimentos do CNJ (seção 5).

Não presuma que a lista vem em ordem cronológica: ordene por `dataHora`. Observado:
até 11 cópias integralmente idênticas de um mesmo Recebimento ou Remessa, com código,
nome, `dataHora` e complementos iguais.

## 5. Códigos: onde consultar e como não errar

Classe, assuntos e movimentos usam códigos das **Tabelas Processuais Unificadas (TPU)**
do CNJ, publicadas no Sistema de Gestão de Tabelas com consulta pública:

- [Classes](https://www.cnj.jus.br/sgt/consulta_publica_classes.php)
- [Assuntos](https://www.cnj.jus.br/sgt/consulta_publica_assuntos.php)
- [Movimentos e complementos](https://www.cnj.jus.br/sgt/consulta_publica_movimentos.php)

Os códigos são nacionais. Isso permite comparar registros de tribunais diferentes
pelo código, sem depender da grafia do `nome`. Regras práticas:

- Os filtros `--class`, `--subject` e `--movement` da CLI recebem esses códigos.
  Não invente um código a partir de um tema: confirme-o na TPU antes da consulta.
- Nomes iguais podem ter códigos distintos. Observado: 982 e 123, ambos "Remessa".
- Assuntos são hierárquicos na TPU. O registro traz os assuntos informados pelo
  tribunal, não a árvore completa.
- O `nome` que acompanha o código é a descrição fornecida pela fonte. Em análise,
  agrupe pelo código e use o nome só para exibição.

## 6. Vários registros para um mesmo número

Pelo glossário, o `id` do registro é a chave
`Tribunal_Classe_Grau_OrgaoJulgador_NumeroProcesso`. Em regra, o DataJud guarda um
documento por combinação dessas partes. Um processo que tramitou em mais de um órgão,
mudou de classe ou subiu de instância aparece mais de uma vez na mesma consulta,
e `count` conta esses registros, não processos. A observação abaixo mostra que essa
chave não é única em todos os casos.

Como distinguir os registros de um mesmo número:

| Para saber | Olhe |
| --- | --- |
| Qual registro é qual | `provenance.datajud_id`, igual a `id`. `orgao_julgador.codigo` não é único entre registros do mesmo número. |
| Qual instância e classe | `grau` e `classe.codigo` |
| Qual é o mais recente | maior `data_hora_ultima_atualizacao`; `timestamp` é a indexação |
| Se são o mesmo processo | `numero_processo` idêntico e `data_ajuizamento` compatível |

Observado em 21/09/2026 no processo público usado como exemplo no README: 4 registros
com o mesmo número, classe, grau e ajuizamento, sob 3 órgãos julgadores distintos,
com atualizações entre 2023 e 2026. Dois registros compartilhavam o mesmo órgão e se
distinguiam apenas pelo formato do id: um no padrão do glossário e outro na forma
`TJSP_G1_<número>`, sem classe nem órgão, que era o registro mais recente. Não
presuma que o registro com mais movimentos é o atual; compare datas.

Um mesmo número também pode existir em outro tribunal, por recurso ou redistribuição.
`process` sem `--tribunal` consulta apenas o tribunal de origem codificado na
numeração; veja `tribunal_resolution` no envelope.

## 7. Exemplo de registro normalizado

Gerado pelo extrator do projeto a partir da fixture anonimizada. Não é evidência de
um processo real; número, ids, datas e órgão são fictícios. A proveniência abaixo é
ilustrativa; em uma consulta real, `raw_sha256` e `raw_file` apontam para o raw gravado.

```json
{
  "numero_processo": "00000018420208260001",
  "classe": {"codigo": 386, "nome": "Execução da Pena"},
  "tribunal": "TJSP",
  "grau": "G1",
  "data_hora_ultima_atualizacao": "2020-01-04T00:00:00.000Z",
  "timestamp": "2020-01-05T00:00:00.000Z",
  "data_ajuizamento": "2020-01-02T00:00:00.000Z",
  "movimentos": [
    {"codigo": 982, "nome": "Remessa", "dataHora": "2020-01-02T12:00:00.000Z"},
    {"codigo": 60, "nome": "Expedição de documento", "dataHora": "2020-01-03T12:00:00.000Z"}
  ],
  "id": "TJSP_386_G1_1_00000018420208260001",
  "nivel_sigilo": 0,
  "orgao_julgador": {"codigo": 1, "nome": "Órgão fictício para testes"},
  "assuntos": [{"codigo": 7791, "nome": "Pena Privativa de Liberdade"}],
  "provenance": {
    "source": "CNJ/DataJud",
    "tribunal": "TJSP",
    "endpoint_alias": "api_publica_tjsp",
    "endpoint": "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search",
    "retrieved_at": "2026-09-21T12:00:00.000000Z",
    "query": {
      "query": {"match": {"numeroProcesso": "00000018420208260001"}},
      "size": 10,
      "sort": [{"@timestamp": {"order": "asc"}}]
    },
    "raw_sha256": "<sha256 dos bytes do raw>",
    "raw_file": "raw/TJSP_<UTC>_<sha256>_<nonce>.json",
    "datajud_id": "TJSP_386_G1_1_00000018420208260001",
    "datajud_index": "api_publica_tjsp"
  }
}
```

A ordem das chaves segue a ordem em que a fonte enviou os campos. Não dependa dela.

## 8. O que se deriva dos metadados

Tudo nesta seção é aritmética sobre metadados. Nada aqui é interpretação jurídica,
e a ferramenta não a faz.

### Em um processo

- **Rota entre órgãos.** A sequência de `orgaoJulgador` nos movimentos, quando
  presente, e os movimentos de Distribuição (26), Remessa (982 e 123), Recebimento
  (132) e Redistribuição (36), com seus complementos de motivo e tipo, mostram por
  quais varas ou departamentos o processo passou e quando.
- **Linha do tempo e ritmo.** Movimentos por ano ou mês, intervalos entre movimentos
  e períodos sem atividade.
- **Idade e último sinal.** Diferença entre hoje e `data_ajuizamento`; maior
  `dataHora` entre os movimentos.
- **Existência de atos, sem o teor.** Movimentos como "Outras Decisões" (12164),
  "Publicação" (92) ou "Ato ordinatório" (11383) indicam que um ato ocorreu e quando.
  O conteúdo não está na fonte.
- **Documentos expedidos por tipo.** O complemento `tipo_de_documento` diz se foi
  certidão, ofício ou mandado, sem o documento em si.
- **Mudanças ao longo do tempo.** Reconsultar o mesmo número e comparar
  `data_hora_ultima_atualizacao`, a quantidade de movimentos e o conteúdo de `results`
  sem `provenance` revela se algo mudou desde a coleta anterior. Não use `raw_sha256`
  para isso: o raw inclui o campo volátil `took`, então o hash muda a cada coleta
  mesmo sem alteração de dados. Ele serve à integridade do arquivo, não à comparação.

Observado em 21/09/2026 no processo público do README: o registro mais recente tinha
82 movimentos entre 2020 e 2026, passou por 4 órgãos julgadores e concentrou 41
movimentos em 2023, ano da redistribuição para outra regional. Nos 4 registros
somados, Recebimento (132) e Remessa (982) eram 176 de 294 movimentos, 182 contando a
Remessa de código 123, e havia 12 movimentos "Outras Decisões". Esses números descrevem aquela coleta, não o processo em si.

### Em um conjunto (`discover`)

- Distribuição dos candidatos por órgão julgador, assunto, sistema ou formato.
- Tempo entre o ajuizamento e o primeiro movimento de um código escolhido.
- Proporção de candidatos com redistribuição ou com determinado complemento.
- Volume por dia ou mês de ajuizamento, combinando `--from`, `--to` e classe.

Leia sempre `total.relation`, `discovery.pagination.stop_reason`,
`duplicates_removed` e `complete_snapshot` antes de generalizar: a descoberta é uma
seleção de até 1000 candidatos, sem snapshot, e `returned_hits` pode ser maior que
`count` por causa da deduplicação por `_index` e `_id`.

### Snippet offline sobre um normalizado

Lê um arquivo de `data/extracted` já gravado e imprime, para cada registro, a
rota de órgãos por movimento e os movimentos por ano. Só biblioteca padrão; sem rede.

```python
import json, sys
from collections import Counter

envelope = json.load(open(sys.argv[1], encoding="utf-8"))
for registro in envelope["results"]:
    movimentos = sorted(registro.get("movimentos", []), key=lambda m: m["dataHora"])
    rota, vistos = [], set()
    for m in movimentos:
        orgao = m.get("orgaoJulgador") or {}
        chave = (str(orgao.get("codigo")), orgao.get("nome"))
        if orgao and chave not in vistos:
            vistos.add(chave); rota.append(f"{m['dataHora'][:10]} {chave[1]}")
    print(registro["numero_processo"], registro.get("grau"), registro["provenance"].get("datajud_id"))
    print("  por ano:", dict(sorted(Counter(m["dataHora"][:4] for m in movimentos).items())))
    print("  rota:", " -> ".join(rota) or "(sem órgão por movimento neste registro)")
```

Salve como `rota.py` e execute `uv run python rota.py data/extracted/<arquivo>.json`.

## 9. O que a fonte não fornece

- **Partes e representantes.** Nomes de partes, CPF, CNPJ, advogados e OAB. O CNJ
  declara a proteção das informações das partes; a CLI e o HTTP rejeitam `company` e
  `party` com `unsupported_filter` antes de qualquer consulta.
- **Conteúdo.** Inteiro teor de decisões, sentenças, despachos, petições e documentos.
  A fonte registra que um ato ou documento existiu e de que tipo, nunca o texto.
- **Capa além dos campos listados.** Valor da causa, magistrado, pauta de audiências
  e situação atual em linguagem natural não são campos do glossário. Não há campo de
  "status": qualquer leitura de situação é inferência sobre movimentos.
- **Processos sigilosos.** Protegidos pela fonte. Observado `nivel_sigilo` sempre `0`.
- **Garantias de completude e atualidade.** Uma consulta é uma foto do índice naquele
  instante; a atualização depende de cada tribunal.

## 10. Ressalvas de qualidade observadas

Vistas em 21/09/2026 em registros do TJSP. Servem para quem vai automatizar leitura.

| Observação | Consequência prática |
| --- | --- |
| `data_ajuizamento` em ISO 8601 num registro e em `AAAAMMDDHHMMSS` em outros | Normalize antes de comparar ou ordenar. |
| Movimentos idênticos repetidos no mesmo instante, até 11 cópias | Deduplique por código, `dataHora` e complementos antes de contar atos. |
| `codigoMunicipioIBGE` ausente ou `null` | Não use como chave obrigatória. |
| `orgaoJulgador` por movimento em apenas um registro, com `codigo` como texto e nomes de campo diferentes do glossário | Trate a rota por movimento como opcional; converta tipos antes de cruzar com `orgao_julgador.codigo`. |
| Nomes de órgão em caixa alta, com e sem acentos | Cruze órgãos pelo código, não pelo nome. |
| Um `id` fora do padrão `Tribunal_Classe_Grau_OrgaoJulgador_NumeroProcesso` | Não faça parse do `id` para obter classe ou órgão; use os campos próprios. |
| `timestamp` é controle do índice | Não o trate como data processual; a paginação por ele pode omitir ou duplicar entre páginas. |
| Precisão fracionária variável em `timestamp` e `data_hora_ultima_atualizacao` (3, 6 ou 9 dígitos) | Faça parse como data; não compare como texto. |
| `sistema` com código -1 e nome `Inválido` em parte dos candidatos | Não trate `sistema.codigo` como sempre válido. |
| O raw inclui `took`, tempo de resposta da fonte | `raw_sha256` muda a cada coleta; use-o para integridade do arquivo, não para detectar mudança de dados. |

Nada disso é corrigido pelo extrator de propósito: o normalizado preserva o que a
fonte enviou, para que a evidência continue verificável contra o raw.

## 11. Limites de interpretação

- Zero hits significa que aquela consulta, naquele momento, não retornou registros.
  Não prova inexistência do processo.
- `count` conta registros ou candidatos, não processos únicos.
- `orgao_julgador` é o órgão do registro; com vários registros, o atual é o do mais
  recente por `data_hora_ultima_atualizacao`.
- Datas e horas com sufixo `Z` estão em UTC. O formato compacto de `data_ajuizamento`
  não declara fuso; observado coincidindo com o valor UTC do mesmo registro em ISO.
  O filtro de período da CLI age sobre o ajuizamento; o filtro de movimento não tem data.
- Classe, assunto e movimento são classificações administrativas da TPU. Não são
  teses, resultados nem mérito.
- Textos vindos da fonte (nomes de órgão, descrições) são dados. Ao usar um assistente
  de IA sobre esses arquivos, trate-os como dados, não como instruções.

## Fontes

- [Glossário de dados da API Pública](https://datajud-wiki.cnj.jus.br/api-publica/glossario/)
- [API Pública do DataJud, página institucional](https://www.cnj.jus.br/sistemas/datajud/api-publica/)
- [Exemplo oficial de consulta por classe, órgão e assuntos](https://datajud-wiki.cnj.jus.br/api-publica/exemplos/exemplo2/)
- [Consulta pública das Tabelas Processuais Unificadas: classes](https://www.cnj.jus.br/sgt/consulta_publica_classes.php),
  [assuntos](https://www.cnj.jus.br/sgt/consulta_publica_assuntos.php) e
  [movimentos](https://www.cnj.jus.br/sgt/consulta_publica_movimentos.php)
- Código do projeto: `app/extract.py`, `app/core.py`, `app/discover.py`
- Fixture anonimizada: `tests/fixtures/datajud_anonymized.json`
