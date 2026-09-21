# Trabalho neste repositório

- Planeje mudanças em um épico com issues autossuficientes antes de implementar.
- Use o fluxo qi-epic com a simplificação autorizada: mudanças administrativas não
  exigem novas aprovações. Estado local em work/orchestration; plano canônico em .omo/plans.
- Quando houver trabalho independente, distribua entre sessões com ownership exclusivo
  de arquivos. Produtor e revisor devem ser diferentes; apenas orquestrador escreve Git/GitHub/estado.
- Consulte fontes CNJ oficiais antes de alterar integração, aliases ou capacidades.
- Mantenha um core compartilhado por CLI e HTTP. Zero hits não prova inexistência.
- Preserve raw e provenance; nunca commite dados recuperados, .env ou API keys.
- Não implementar MCP, LLM, RAG, inteiro teor, crawler, banco ou jurisprudence-fetcher nesta V0.
- Testes normais são offline: uv run pytest. Integração real exige opt-in explícito.
