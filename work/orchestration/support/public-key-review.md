# Revisão independente — chave pública por consulta

**PASS no escopo revisado. Nenhum finding material aberto.**
Épico #11, revisão #14. Produtor runtime: core; documentação: trabalhador docs;
revisor independente: evidence. Plano aplicado:
`.omo/plans/2026-09-21-datajud-public-key.md`.

Início UTC: `2026-09-21T19:52:21Z`; conclusão UTC:
`2026-09-21T19:58:15Z`. Escritas do revisor restritas a
`tests/test_auth_review.py` e este relatório. Nenhuma consulta CNJ real, alteração
de código do produtor ou operação Git/GitHub.

## Evidência independente

```powershell
& .\.tools\bin\uv.exe run --cache-dir .uv-cache --no-sync pytest tests/test_auth_review.py -q --tb=short
```

Resultado final: **24 passed, 2 warnings in 0.52s**, exit 0. Warnings são
deprecações do TestClient/AnyIO, sem falha funcional. O Python/cache instalado
exigiu escalonamento de sandbox. Os testes bloquearam o transporte HTTP real
e usaram apenas `httpx.MockTransport`, chaves sintéticas e diretórios temporários.

| Requisito exercitado | Evidência |
| --- | --- |
| Mesmo cliente resolve novamente a chave a cada busca | GET/POST/GET/POST, tokens sintéticos A e B distintos |
| Serviço HTTP persistente não fixa a chave anterior | Duas requisições `/search` com o mesmo service/client usam A e B |
| CLI e FastAPI default usam auto sem chave estática | CLI e rota sem service injetado passam por Settings auto e wiki mock |
| Discovery resolve chave por página | Duas páginas, dois GETs, duas provenances preservadas |
| Chave antiga no ambiente não é fallback auto | Settings auto e busca descartam credencial antiga |
| Wiki não recebe Authorization | Inspeção de todos os GETs; headers padrão do cliente sem Authorization |
| Credencial enviada somente ao POST permitido | URL/método e header verificados no MockTransport |
| 401/403 permite uma renovação, mesmo retries=0 | GET/POST rejeitado/GET/POST; sucesso após token B |
| Rejeição da chave renovada encerra | Dois GETs e dois POSTs, authentication_error, sem loop |
| Retry transitório não resolve chave sem necessidade | GET/POST503/POST200 |
| Refresh não reinicia orçamento transitório gasto | 503,401,503 com max_retries=1 termina após três POSTs |
| Fonte ausente/ambígua/grande/redirect/HTTP/timeout falha fechada | Nenhum POST, nenhum fallback e nenhum arquivo de evidência criado |
| Corpo chunked sem Content-Length é limitado | Interrompe em até 33 chunks de 8192 bytes para limite 256 KiB e fecha response |
| Entrada inválida ou filtro não suportado antecede rede | Tribunal/CNJ/size/script/company/party não geram GET |
| Manual explícito não usa wiki | Um POST com a chave configurada |
| Health e extração offline continuam sem rede | CLI e HTTP passam mesmo proibindo construção de DataJudClient |
| Ausência de vazamento | Scan de logs DEBUG, exceções renderizadas, envelopes e todos os arquivos temporários |

As fixtures HTML incluem o placeholder documentado `Authorization: APIKey
[Chave Pública]` antes do header com token sintético e markup em spans. A condição
de ambiguidade usa duas chaves distintas; não contém credencial real.

## Histórico de finding e disposição

### PKR-01 — P1 — Response usado como context manager incompatível

**RESOLVIDO.** A orquestradora já havia identificado o risco; a primeira execução
independente confirmou **14 failed, 9 passed**, com todas as 14 falhas provenientes
do mesmo `TypeError` no `with response` então em `app/public_key.py:122`.

Requisito afetado: busca automática deve conseguir obter a chave e executar a
consulta. Mecanismo: `httpx.Response` da versão instalada não implementa o
protocolo de context manager; qualquer GET que retornasse resposta falhava antes
do parsing/status, bloqueando CLI, HTTP e discovery no modo padrão.

Correção do produtor: `with closing(response)` em `app/public_key.py:129`.
Rechecagem independente: os cenários antes afetados passaram; o teste adicional
de stream excessivo confirmou fechamento inclusive no erro. Não houve mudança
do revisor em `public_key.py`.

### Tratamento do placeholder oficial

A orquestradora informou que a página contém o header explicativo com
`[Chave Pública]`. O produtor restringiu a exceção de parsing a esse placeholder
documentado em `app/public_key.py:92`; os tokens reais continuam sujeitos à
unicidade. O revisor incluiu o placeholder em todas as fixtures de sucesso e
confirmou os fluxos end-to-end com mocks. Não restou finding aberto nesse ponto.

## Auditoria do código e da documentação

- `Settings.auth_mode` tem default auto e manual é escolha explícita; auto zera
  a credencial antiga. Não há cache global nem chave armazenada no cliente HTTP.
- `DataJudClient.search` valida tribunal/query antes de resolver a chave. O
  orçamento de retries é compartilhado entre as tentativas antes/depois do
  refresh e a atualização por 401/403 é limitada por chamada.
- O GET usa URL HTTPS fixa, `Cache-Control: no-cache`, encoding identity,
  streaming limitado e rejeição de redirects. Authorization/Proxy-Authorization
  são removidos da requisição da wiki; auth do cliente é desabilitada nesse GET.
- HTML é tratado por parser stdlib, sem executar conteúdo. Script/style/template
  não são fontes de chave. Falhas expõem códigos/mensagens seguros e não criam
  Retrieval para o HTML da wiki.
- `.env.example`, README e guia distinguem auto/manual, eliminam a chave do setup
  padrão, documentam falha da wiki sem fallback e mantêm health/offline sem rede.
  Os resultados antigos estão identificados como históricos; o canário novo tem
  relatório separado.
- Foi sugerida uma precisão editorial não bloqueante no README: esclarecer
  que a preservação de corpo HTTP 2xx refere-se à **API DataJud**, não ao HTML
  da wiki. A documentação principal já afirma que chave/HTML não são persistidos.

## Limites

A revisão independente não acessou CNJ real nem atesta disponibilidade futura da
wiki ou estabilidade de seu markup. Canário opt-in e suíte completa pertencem
à validação da orquestradora. A dependência da página oficial, a ausência de
fallback silencioso e a possibilidade de falha explícita estão documentadas.
