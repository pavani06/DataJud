# Revisão independente — interfaces, storage e extração

- Revisora: worker core; não produziu os módulos revisados nesta rodada.
- Início UTC: 2026-09-21T18:54:13Z.
- Fim UTC: 2026-09-21T18:57:40Z (aproximado ao registrar o relatório).
- Escopo: `app/storage.py`, `app/extract.py`, `app/models.py`, `app/core.py`,
  `app/main.py`, `app/cli.py` e respectivos testes.
- Referência: missão V0, correção SEARCH → DISCOVER → EXTRACT e contrato T002.
- Exclusões de independência: config/datajud/queries/cnj/tribunals, produzidos pela
  própria revisora, não foram revisados nem aprovados por este relatório.
- Resultado: **FAIL — um blocker de aceite do tratamento estruturado de erros**.
  A suíte existente passa; o blocker foi demonstrado por probe adversarial adicional.

## R1 — P2: erro de profundidade da normalização escapa do contrato das interfaces

**Requisito:** contrato das interfaces exige erro HTTP estruturado e erro CLI seguro;
a missão §§12 e 20 exige tratar JSON inesperado explicitamente. O raw já preservado
deve continuar identificável quando a normalização falha.

**Local:** `app/core.py:86` captura somente `ValueError`, `TypeError` e `KeyError`
após a preservação. `app/extract.py:52` usa `deepcopy` para campos desconhecidos.
Uma profundidade JSON aceita pelo parser pode exceder a profundidade suportada por
`deepcopy`. `RecursionError` não é capturado nesse limite nem em `app/cli.py:93`.

**Reprodução:** resposta HTTP 200, com shape DataJud válido, contendo:

```python
raw = (
    '{"timed_out":false,"_shards":{"failed":0},'
    '"hits":{"total":{"value":1,"relation":"eq"},'
    '"hits":[{"_source":{"futureField":'
    + '[' * 600 + '0' + ']' * 600
    + '}}]}}'
).encode()
```

O probe utilizou `httpx.MockTransport`, diretório temporário exclusivo,
`DataJudService.search`, `TestClient(..., raise_server_exceptions=False)` e
`CliRunner`, sem chamadas externas e sem alterar código.

**Evidência observada:**

```text
DEEP_CORE: RecursionError None
DEEP_HTTP: 500 Internal Server Error
DEEP_CLI: 1 RecursionError
DEEP_RAW_FILES: 6
```

São três tentativas, cada uma preservando raw e sidecar. A CLI não produz o documento
JSON de erro; o HTTP devolve texto genérico 500. A evidência permanece no disco, mas
seu caminho não acompanha um erro estruturado. A severidade é P2 porque depende de
conteúdo profundamente aninhado; é blocker do aceite adversarial deste contrato,
não uma alegação de perda de raw nem de vazamento de chave demonstrado.

**Correção mínima:** envolver também `RecursionError` no ramo `extraction_error`,
mantendo `raw_path` e `provenance`, e adicionar regressão de HTTP/CLI. Não é necessário
reimplementar o extractor ou aceitar normalização ilimitada. A orquestradora recebeu
o finding e confirmou que fará esse delta; este relatório não antecipa o reteste.

## Verificações que passaram

Comando executado com escalonamento necessário ao Python/uv instalado:

```text
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync pytest tests/test_core.py tests/test_http.py tests/test_cli.py tests/test_storage.py tests/test_extract.py -q
102 passed, 1 skipped, 2 warnings in 1.61s
```

- Raw é escrito como bytes originais, com SHA-256 desses bytes, nomes exclusivos e
  sidecar antes do retorno; repetição não substitui arquivos anteriores.
- Offline exige raw direto em `data_dir/raw`, sidecar com campos esperados, endpoint
  consistente com registry, timestamp UTC e hash correspondente. Recusa sidecar
  ausente, metadados divergentes, raw alterado e resposta parcial/inválida.
- Inspeção de caminhos verificou containment por caminhos resolvidos, restrição de
  prefixos de manifestos, criação exclusiva e recusa de symlinks de arquivos.
- A extração preserva campos desconhecidos em `extra_fields`, não inventa campos
  ausentes, isola provenance por resultado e não modifica o payload de entrada.
- Validação HTTP omite valores de entrada/contexto Pydantic; mensagens operacionais
  verificadas não incluíram a credencial fictícia nem o corpo upstream.
- Probe adicional de CLI com raw em UTF-8, acentos, espaços e CRLF demonstrou
  `stdout_bytes == raw` e exit 0.
- Probe adicional de offline bloqueou os construtores `app.core.DataJudClient` e
  `httpx.Client`: reextração passou, provenance original permaneceu idêntica e raw
  permaneceu byte a byte inalterado.

## Limites da verificação

- O teste real de criação de symlink foi ignorado porque o host não permite criá-lo.
  Não se declara validação dinâmica dessa parte; houve inspeção do mecanismo.
- Os dois avisos pytest são de depreciação em dependências do TestClient.
- Reutilizar `CliRunner` e em seguida o serviço no mesmo probe deixou o handler
  global de logging apontando para o stream fechado do runner; ocorreu um aviso
  de logging do harness. As três asserções de bytes/offline passaram. Isso não foi
  classificado como falha da execução normal da CLI em processo separado.
- Nenhum teste real CNJ foi realizado nesta revisão; canário pertence à integração.
- A implementação de discovery não integra o ownership desta revisão independente.

## Rodada 2 — reteste do delta, 2026-09-21T19:00:03Z–19:00:30Z

**Resultado final deste escopo: PASS. R1 resolvido.** O histórico FAIL da primeira
rodada permanece acima para rastreabilidade; não há blocker pendente desta revisão.

Foi relido o trecho atualizado de `app/core.py`. A linha 91 agora inclui
`RecursionError` no limite de normalização; as linhas 92–96 produzem
`extraction_error` com `raw_path` e provenance da evidência já salva.

Regressões executadas:

```text
.tools/bin/uv.exe run --cache-dir .uv-cache --no-sync pytest tests/test_http.py::test_deep_upstream_json_gets_structured_error_and_raw tests/test_cli.py::test_deep_upstream_json_cli_has_safe_error tests/test_discover.py::test_upstream_oversized_page_is_error_with_raw_preserved tests/test_core.py -q
15 passed, 2 warnings in 0.51s
```

- `tests/test_http.py:49` reproduz o JSON com 600 níveis e confirma HTTP 502 com
  documento estruturado `extraction_error` e raw exatamente preservado.
- `tests/test_cli.py:69` reproduz o mesmo caso e confirma exit 1, stderr JSON
  estruturado e raw exatamente preservado. O erro deixa de escapar como
  `RecursionError` da CLI.
- As regressões de core verificam offline, hash/provenance, zero hits, erro parcial,
  repetição, inferência/override e falha de I/O sem alteração indevida desses fluxos.

Também foi revisado o delta RCD01 solicitado pela orquestradora:
`app/core.py:60` preserva raw antes da comparação, e as linhas 61–65 recusam mais
hits que o `size` efetivamente enviado, com `unexpected_page_size`, HTTP 502,
raw_path e provenance. O erro ocorre antes de normalização/persistência extraída.
`tests/test_discover.py:81` passou, comprovando que dois hits para página de tamanho
um são recusados, os dois hits permanecem no raw e não há manifesto discovery de
sucesso. Esse reteste não constitui revisão integral de `app/discover.py`.

Nenhuma chamada live nem alteração de código foi feita. Somente este relatório foi
atualizado. Continuam válidos os limites anteriores sobre symlink e depreciações.
