# Chave pública vigente por consulta

Épico #11; runtime #12; documentação #13; revisão independente #14.

Origem: pedido do usuário e página oficial CNJ acessada em 21/09/2026:
https://datajud-wiki.cnj.jus.br/api-publica/acesso/

Gap: o cliente exige uma chave estática no ambiente; rotações exigem intervenção.
Aceite: cada chamada de busca resolve a chave publicada, inclusive páginas de
discovery. Health e extração de raw permanecem sem rede. Chave não é persistida.

## Contrato de implementação

- `Settings.auth_mode` / `DATAJUD_AUTH_MODE`: `auto` (padrão) ou `manual`.
- Auto consulta exclusivamente a URL HTTPS oficial, antes de cada `search`.
  Uma chave antiga no ambiente não substitui a vigente no modo auto.
- Manual é override explícito para diagnóstico/ambientes controlados e exige
  `DATAJUD_API_KEY`. Sem fallback silencioso do auto para credencial antiga.
- GET da wiki não recebe Authorization. A chave fica em memória e é enviada
  somente ao POST do endpoint DataJud permitido pelo registry.
- Parser HTML stdlib, sem executar conteúdo; rejeitar chave ausente/ambígua,
  corpo excessivo e redirects não validados. Falhas têm mensagens seguras.
- Timeout e retries limitados; após 401/403 em auto, uma atualização e uma nova
  tentativa por chamada, sem laço infinito. Não refazer parser/requisição em retries
  transitórios sem necessidade. Sem cache global ou gravação da chave/HTML.
- Entrada inválida é recusada antes de qualquer rede, como na V0.

## Paralelismo e ownership

1. Core: app/config.py, app/datajud.py, novo app/public_key.py, tests/test_config.py,
   tests/test_datajud.py e tests/test_public_key.py. Implementação + testes próprios.
2. Docs: README.md, docs/GUIA_DE_USO.md, .env.example. Atualizar instalação e exemplos
   para auto por padrão; config/manual opcionais e falhas da wiki documentadas.
3. Evidence: revisão independente, tests/test_auth_review.py e relatório próprio.
   Primeiro auditar riscos/contrato; depois verificar implementação e correções.
4. Root: Git/GitHub/plano/estado, conftest/test_cli/test_integration, smoke e evidências.

Criar épico e issues antes do código. Execução qi-epic simplificada, push_mode
autonomous-approved herdado; sem novos gates administrativos. Instrumentação
task-wrapper/close-check indisponível: checagem equivalente local e GitHub readback.

## Verificação e fechamento

- Mocks: chave rotacionada entre chamadas, HTML com spans, ausente/ambígua, excesso,
  timeout/status/redirect, 401/403 limitado, override manual, ausência de leaks.
- CLI/HTTP/discovery adotam auto; health/offline não chamam wiki nem API.
- Suite offline completa; canário real opt-in desta tarefa: uma consulta size=1
  pelo fluxo automático, sem injetar/persistir chave, registrando só resultado e paths.
- Revisão independente; correções e rechecagem direcionada. Publicar código/docs,
  comentários de handoff e estados encerrados; preservar recibos históricos da V0.

## Execução verificada

Runtime, documentação e revisão independente concluídos. Resultado final de testes,
canário real, hashes e limites em `work/orchestration/support/public-key-acceptance.json`.
PKR-01 (lifecycle de resposta HTTP) e distinção do placeholder oficial foram
corrigidos no escopo #12 antes do aceite; revisão #14 PASS. A precisão editorial
da preservação do raw apenas da API DataJud foi aplicada no README.
Estado de publicação/fechamento autoritativo: `work/orchestration/public-key-state.json`.
