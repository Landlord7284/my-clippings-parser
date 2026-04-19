# Contribuindo

## Convenção de Commits

Formato sugerido:

```text
tipo(escopo): resumo curto
```

Tipos comuns:
- `feat`: nova funcionalidade
- `fix`: correção de bug
- `test`: inclusão/ajuste de testes
- `docs`: documentação
- `refactor`: refatoração sem mudança funcional

## Fluxo Simples de Branches

1. Criar branch curta por objetivo (ex.: `codex/test-parser-dedup`).
2. Fazer mudanças pequenas e coesas.
3. Abrir PR com contexto, escopo e riscos.

## Validação Antes do Commit

```powershell
pytest
```

Se a mudança afetar fluxo de uso, também validar manualmente:
- upload do arquivo
- análise
- seleção
- exportação

## Como Adicionar Novos Testes

- Preferir testes `pytest` no arquivo de domínio correspondente em `tests/`.
- Reutilizar fixtures do `tests/conftest.py`.
- Cobrir comportamento essencial e casos de borda relevantes.

## Mudanças em Parser / Deduplicação

- Sempre incluir casos de regressão (preferencialmente inspirados em clippings reais).
- Evitar heurísticas agressivas sem cobertura de teste.
- Verificar impacto em:
  - agrupamento por livro
  - contagem de highlights
  - seleção por status
  - exportação final
