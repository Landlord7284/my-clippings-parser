# Kindle Notes Extractor

App local com FastAPI + Vite React para analisar `My Clippings.txt` do Kindle, agrupar entradas por livro, permitir seleção intermediária e exportar apenas os livros escolhidos.

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

Pré-requisitos: Python 3.11+ e Node.js 20+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Backend:

```powershell
uvicorn kindle_extractor.api:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

## Como Executar Testes

Rodar suíte completa:

```powershell
pytest
cd frontend
npm run test
npm run build
```

Rodar um módulo específico:

```powershell
pytest tests/test_parser.py -q
```

## Estrutura Principal

```text
kindle_extractor/
  api.py
  parser.py
  dedup.py
  processing_store.py
  book_selection_service.py
  exporters.py
  datetime_utils.py
  extractor.py

frontend/
  src/
  tests/

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
- `api.py`: endpoints FastAPI para análise e exportação.
- `frontend/`: interface Vite React com componentes shadcn/ui.
- `extractor.py`: orquestra parser + dedup + export.

## Limitações Conhecidas

- Parser focado em padrões comuns do `My Clippings.txt` em português; variações muito fora do padrão podem cair em fallback.
- Deduplicação usa heurísticas conservadoras; ainda pode haver casos limítrofes.
- Store local é arquivo JSON único, com lock local por processo e escrita atômica; não há banco nem lock distribuído.
- O cache de análise é local e em memória; após reiniciar o backend, é necessário analisar novamente antes de exportar.

## Persistência Local

- O arquivo `.kindle_processing_store.json` segue sendo o store v2 e deve ficar em diretório persistente.
- As mutações do store serializam `load -> merge -> save` dentro do processo backend para evitar perda de atualização em requisições concorrentes locais.
- Em uma implantação futura em NAS, manter um único backend/container escritor sobre o volume de histórico. Docker, compose e scripts de deploy serão definidos apenas quando o projeto estiver completo.
