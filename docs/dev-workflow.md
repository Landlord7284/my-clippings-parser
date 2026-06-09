# Evolução com Agente de Código

## Objetivo

Evoluir o projeto em etapas pequenas, com baixo risco de regressão e alta legibilidade.

## Estratégia Recomendada

1. Fazer mudanças pequenas e isoladas por tema (parser, dedup, store, seleção, export).
2. Adicionar/ajustar testes no mesmo PR/commit da mudança.
3. Evitar refatorações amplas sem necessidade funcional clara.
4. Manter compatibilidade do fluxo atual da UI React.

## Convenção de Prompt Sugerida

Use prompts com o seguinte formato:

```text
Contexto:
- ...

Objetivo da etapa:
- ...

Escopo permitido:
- ...

Critérios de aceite:
- ...

O que não fazer:
- ...
```

## Boas Práticas para Mudanças Incrementais

- Preferir testes pequenos, legíveis e estáveis.
- Validar comportamento por conteúdo essencial, não por detalhes cosméticos.
- Garantir que parser/dedup tenham testes de regressão com exemplos reais.
- Tratar compatibilidade de dados legados no store com fallback seguro.

## Áreas Sensíveis

- `parser.py`: qualquer alteração pode impactar classificação e agrupamento.
- `dedup.py`: ajustes podem remover dados válidos se regras ficarem agressivas.
- `processing_store.py`: mudanças de schema exigem sanitização de legado.
- `book_selection_service.py`: status errados afetam seleção padrão e exportações.

## Checklist Antes de Fechar uma Etapa

1. Rodar `pytest`.
2. Rodar `npm run test` e `npm run build` em `frontend/`.
3. Validar fluxo principal: upload -> análise -> seleção -> exportação.
4. Revisar se a mudança preservou simplicidade de código.
5. Atualizar documentação técnica quando houver mudança de comportamento.

## Recomendações para Evitar Regressões

- Sempre adicionar ao menos um teste de regressão para bugs corrigidos.
- Não acoplar testes a detalhes cosméticos da interface.
- Priorizar testes de funções e serviços puros.
- Em mudanças no parser/dedup, usar também casos inspirados em `My Clippings.txt` real.
