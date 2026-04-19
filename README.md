# Kindle Notes Extractor

App Python + Streamlit para analisar `My Clippings.txt` do Kindle, agrupar entradas por livro, permitir seleção intermediária e exportar apenas os livros escolhidos.

## Objetivo

- Ler highlights, notas e bookmarks do Kindle.
- Aplicar deduplicação para reduzir ruído.
- Persistir histórico de análise/exportação por livro.
- Guiar a seleção antes da exportação final.

## Fluxo Geral do App

1. Upload do arquivo `My Clippings.txt`.
2. Parser + deduplicação + agrupamento por livro.
3. Classificação por status (`novo`, `nunca exportado`, `com novidades`, `sem novidades`).
4. Seleção de livros (filtros, busca e ações em lote).
5. Exportação dos livros selecionados em `markdown`, `html` e/ou `txt`.
6. Atualização do histórico local em `.kindle_processing_store.json`.

## Como Rodar Localmente

Pré-requisito: Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Executar app:

```powershell
streamlit run app.py
```

## Como Executar Testes

Rodar suíte completa:

```powershell
pytest
```

Rodar um módulo específico:

```powershell
pytest tests/test_parser.py -q
```

## Estrutura Principal

```text
kindle_extractor/
  parser.py
  dedup.py
  processing_store.py
  book_selection_service.py
  exporters.py
  datetime_utils.py
  ui.py
  extractor.py

tests/
  conftest.py
  fixtures/
  test_parser.py
  test_dedup.py
  test_history.py
  test_selection_service.py
  test_exporters.py
  test_time_utils.py

docs/
  architecture.md
  dev-workflow.md
  processing_store_format.md
```

## Visão Geral dos Módulos

- `parser.py`: parsing de título/autor, localização, página e data.
- `dedup.py`: estratégia em camadas para deduplicação.
- `processing_store.py`: persistência e histórico de processamento/exportação.
- `book_selection_service.py`: classificação de status, ordenação e seleção.
- `exporters.py`: geração de conteúdo em Markdown/HTML/TXT.
- `datetime_utils.py`: utilitários UTC e exibição em `America/Sao_Paulo`.
- `ui.py`: fluxo Streamlit (upload, análise, seleção, exportação).
- `extractor.py`: orquestra parser + dedup + export.

## Limitações Conhecidas

- Parser focado em padrões comuns do `My Clippings.txt` em português; variações muito fora do padrão podem cair em fallback.
- Deduplicação usa heurísticas conservadoras; ainda pode haver casos limítrofes.
- Store local é arquivo JSON único (sem banco e sem lock distribuído).
- Testes evitam acoplamento visual com Streamlit e priorizam regra de negócio.
