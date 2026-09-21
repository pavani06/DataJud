# Revisão independente — cliente, queries, CNJ e discovery

Resultado atual após rodada 2: **PASS no escopo revisado**; RCD-01 e RCD-02 resolvidos e
revalidados. O histórico da primeira rodada e suas reproduções permanece abaixo.

Resultado da rodada 1: **FAIL — dois findings P2 em discovery**. Nenhum P0/P1 observado.
Cliente, configuração, registry, queries e CNJ: **PASS no escopo verificado**.

Revisor: trabalhador evidence, que não produziu os módulos revisados. Os próprios
`storage.py` e `extract.py` estão excluídos desta revisão/aprovação.

Início UTC: `2026-09-21T18:54:23Z`. Verificações encerradas UTC:
`2026-09-21T18:56:46Z`. Nenhuma alteração em código ou testes; somente este relatório.

## Escopo e critérios

Lidos o plano `.omo/plans/2026-09-21-qi-loop-datajud.md`, contrato T002 e issues locais
de validação/discovery. Revisados `app/config.py`, `datajud.py`, `queries.py`, `cnj.py`,
`tribunals.py`, `discover.py`, `pagination.py` e seus testes. `models.py` e o caminho
de integração em `core.py` foram lidos para conferir as fronteiras desses módulos.

Critérios aplicados: limites 1000 candidatos/100 por página/100 páginas, preservação
de graus distintos, loops limitados, erros e respostas parciais explícitos, provenance
por página/candidato, endpoint fixo, autenticação sem vazamento, scripts recusados e
inferência conservadora do tribunal de origem. Nenhum requisito novo foi acrescentado.

## Findings reproduzidos

### RCD-01 — P2 — Limite de candidatos depende de resposta upstream obedecer size

- Requisito: T002/REC-005 determina limite total de candidatos 1..1000 e `limit`
  solicitado pelo chamador.
- Localização: `app/discover.py:43` (loop de inclusão), `app/discover.py:46`
  (`candidates.append`) e `app/discover.py:52` (limite verificado depois da inclusão).
- Mecanismo: todos os hits distintos da página entram em `candidates`; não há
  rejeição de uma página com mais registros que `query['size']`. O validador do
  cliente aceita esse shape, portanto um upstream inesperado consegue exceder o
  limite local e ainda produzir `query_status=success`, `stop_reason=limit`.
- Reprodução offline, com `DataJudClient`/`httpx.MockTransport` e core reais:
  `DiscoverRequest(tribunal='TJSP', limit=1, page_size=1)`, resposta HTTP 200 válida
  com dois hits distintos. Resultado observado:

  ```json
  {"requested_limit":1,"sent_sizes":[1],"count":2,"returned_hits":2,"stop_reason":"limit"}
  ```

- Correção sugerida: rejeitar explicitamente página que exceda o tamanho solicitado
  conservando sua evidência; alternativamente, limitar inclusão e registrar com
  precisão os hits não incluídos, sem contá-los como duplicatas removidas. A primeira
  opção evita ambiguidade do cursor de continuação.
- Aceite do delta: regressão com dois hits para size=1 não pode retornar sucesso
  com count=2 para limit=1; raw da resposta deve continuar preservado.

### RCD-02 — P2 — Identidade incompleta pode apagar candidato de outro grau

- Requisito: T002/REC-005 deduplica por `_index`/`_id`, usa fallback de fonte quando
  a identidade não existe e preserva registros de graus distintos.
- Localização: `app/discover.py:16` e `app/discover.py:17`.
- Mecanismo: basta `datajud_id` existir para usar a identidade primária. Quando
  `_index` está ausente, todos os registros de mesmo `_id` usam `[null, id]`, sem
  considerar o grau nem o restante da fonte. O schema do cliente permite ausência
  de `_index`, e o extractor não inventa esse campo; portanto o fallback existente
  deveria ser usado quando a dupla não estiver completa.
- Reprodução offline: resposta válida com dois hits `_id='same'`, ambos sem
  `_index`, um `_source.grau='G1'` e outro `'G2'`; segunda página vazia. Resultado:

  ```json
  {"requested_limit":2,"sent_sizes":[2,1],"count":1,"grades":["G1"],"returned_hits":2,"stop_reason":"empty_page"}
  ```

- Correção sugerida: só usar a dupla primária se ambos os componentes estiverem
  presentes; caso contrário usar o hash da fonte já implementado.
- Aceite do delta: dois registros sem `_index`, mesmo `_id` e graus distintos devem
  permanecer como dois candidatos. A deduplicação da dupla completa deve continuar.

## Verificação executada

```powershell
& .\.tools\bin\uv.exe run --cache-dir .uv-cache --no-sync pytest tests/test_config.py tests/test_tribunals.py tests/test_cnj.py tests/test_queries.py tests/test_datajud.py tests/test_discover.py tests/test_pagination.py -q
```

Resultado: **225 passed in 0.39s**. Foi necessário `require_escalated` para acessar
o Python/cache instalado; não houve chamada real ao DataJud nesses testes.

Reproduções adicionais foram executadas por Python stdin com o mesmo uv, mocks e
`TemporaryDirectory`, sem modificar arquivos do produto nem evidência real. Esqueleto
reproduzível dos dois findings:

```python
import json, tempfile
from pathlib import Path
import httpx
from app.config import Settings
from app.core import DataJudService
from app.datajud import DataJudClient
from app.models import DiscoverRequest
import app.discover as module
module.time.sleep = lambda _: None

def payload(hits):
    return {"timed_out": False, "_shards": {"failed": 0},
            "hits": {"total": {"value": len(hits), "relation": "eq"}, "hits": hits}}

def run(pages, limit, page_size):
    responses = iter(pages)
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(api_key="mock-only", max_retries=0, data_dir=Path(directory))
        transport = httpx.MockTransport(lambda _: httpx.Response(200, json=next(responses)))
        with DataJudClient(settings, transport=transport) as client:
            result = DataJudService(settings, client).discover(
                DiscoverRequest(tribunal="TJSP", limit=limit, page_size=page_size))
        print(result["count"], [r.get("grau") for r in result["results"]])

run([payload([{"_index": "idx", "_id": str(i), "_source": {"grau": "G1"},
               "sort": [i]} for i in range(2)])], 1, 1)
run([payload([{"_id": "same", "_source": {"grau": grade}, "sort": [i]}
              for i, grade in enumerate(["G1", "G2"])]), payload([])], 2, 2)
```

Outros limites exercitados com serviço simulado e manifesto em memória:

| Entrada | Páginas observadas | Candidatos | Motivo |
| --- | ---: | ---: | --- |
| limit=1000, page_size=1 | 100 | 100 | max_pages |
| limit=1000, page_size=100 | 10 | 1000 | limit |

## Evidências positivas

- Queries são copiadas, limitadas em bytes/profundidade e restringem o envelope,
  scripts, valores não finitos e paginação incompatível antes da rede.
- Registry gera somente HTTPS para host e `_search` fixos; redirects estão
  desabilitados, e tribunal fornecido não pode injetar URL.
- Credencial não aparece no repr, logs ou mensagens dos erros cobertos. Retry é
  limitado e não se aplica a autenticação, HTTP 404 ou resposta parcial.
- JSON inválido, total/schema inválido, timed_out e shards.failed não viram zero
  hits bem-sucedidos; bytes recebidos acompanham o erro para preservação no core.
- Falha na segunda página propaga erro e não produz manifesto de sucesso; páginas
  anteriores permanecem. Resultados carregam provenance da página de origem.
- Guardas interrompem cursor/página repetida, cursor ausente e 100 páginas. Avisos
  e `complete_snapshot=false` não prometem completude.
- Normalização CNJ usa ASCII/máscara estrita, preserva zeros e implementa geração
  canônica do dígito verificador; inferência se limita a origens mapeadas e pede
  tribunal explícito para origens não cobertas.

## Fontes e limites da revisão

Registry conferido contra a [wiki oficial de endpoints](https://datajud-wiki.cnj.jus.br/api-publica/endpoints/),
incluindo o alias excepcional TRE-DF. Cálculo e ordenação dos códigos estaduais
conferidos no texto dos anexos da [Resolução 65 hospedada pelo TJPA](https://libra.tjpa.jus.br/libra/pages/downloads/rescnj_65.pdf).
O endpoint do [ato consolidado no CNJ](https://atos.cnj.jus.br/atos/detalhar/119)
respondeu HTTP403 ao navegador desta revisão; a atualização consolidada relativa
ao TRF6 não foi revalidada independentemente aqui. Screenshots PDF estavam indisponíveis
na ferramenta; a inspeção dos anexos usou a extração textual disponível.

Esta revisão não certifica todos os aliases por consulta real, nem a completude de
resultados paginados. Smoke real, CLI/HTTP e documentação final pertencem à validação
da orquestradora. Findings precisam de correção e revalidação antes de PASS global.

## Rodada 2 — disposição dos findings

**PASS no escopo desta revisão. Nenhum finding aberto.** Esta conclusão cobre os
módulos da revisão original e os dois deltas abaixo; não substitui o aceite final
de smoke real, interfaces ou armazenamento/extração por seus revisores próprios.

Início UTC: `2026-09-21T19:00:08Z`. Conclusão UTC: `2026-09-21T19:00:39Z`.
O revisor novamente não alterou código nem testes e não chamou a API real.

- **RCD-01: RESOLVIDO.** `app/core.py:60` preserva raw antes da nova checagem;
  `app/core.py:61` compara o número de hits ao `size` efetivamente enviado;
  `app/core.py:62` produz `DataJudError(code='unexpected_page_size', status_code=502)`
  com `raw_path` e `provenance`, impedindo sucesso acima do limite. A exceção
  propaga para discovery antes da construção do manifesto agregado. A regressão
  `tests/test_discover.py:81` confirmou dois hits para size=1, erro explícito,
  existência dos dois hits no raw preservado e ausência de manifesto de sucesso.
- **RCD-02: RESOLVIDO.** `app/discover.py:16` exige os dois componentes da identidade
  primária. Se `_index` faltar, o hash da fonte inclui o grau e preserva ambos os
  candidatos. `tests/test_discover.py:90` confirmou `_id='same'` sem `_index`, G1/G2,
  dois candidatos e uma única página. As regressões anteriores de deduplicação e
  parada de paginação continuaram passando.

Comando independente desta rodada:

```powershell
& .\.tools\bin\uv.exe run --cache-dir .uv-cache --no-sync pytest tests/test_discover.py tests/test_pagination.py tests/test_core.py -q
```

Resultado: **27 passed in 0.52s**, exit 0. As limitações documentais da primeira
rodada permanecem registradas; elas não introduzem requisito bloqueante novo.
