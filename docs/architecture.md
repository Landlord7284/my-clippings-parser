# Arquitetura

## Visão Geral

O projeto é organizado em camadas simples, com foco em regra de negócio e baixo acoplamento com a UI.

1. Entrada: `ui.py` (Streamlit).
2. Núcleo de processamento: `extractor.py`.
3. Serviços de domínio: parser, deduplicação, seleção, persistência e exportadores.
4. Saída: arquivos exportados e store local JSON.

## Módulos Principais

### Parser (`kindle_extractor/parser.py`)

Responsabilidades:
- Extrair título/autor.
- Extrair página/posição/data da linha de metadados.
- Tratar formatos UTF-8 e legados comuns.

Saída esperada:
- Campos normalizados consumidos por `extractor.py`.

### Deduplicação (`kindle_extractor/dedup.py`)

Responsabilidades:
- Detectar duplicatas por estratégia em camadas.
- Aplicar fallback por similaridade de forma conservadora.
- Retornar decisão explícita (`is_duplicate`, `reason`, `replace_existing`).

Observação:
- As regras são orientadas a preservar o registro mais completo.

### Persistência / Histórico (`kindle_extractor/processing_store.py`)

Responsabilidades:
- Ler/gravar `.kindle_processing_store.json`.
- Sanitizar payload incompleto/corrompido com fallback seguro.
- Armazenar histórico de processamento e exportação por livro.
- Manter separação entre `last_analysis_at` e `last_export_at`.

### Seleção e Status (`kindle_extractor/book_selection_service.py`)

Responsabilidades:
- Gerar snapshot por livro.
- Classificar status para decisão de exportação.
- Ordenar por prioridade de ação.
- Aplicar filtros, busca e ações em lote.

Status atuais:
- `novo`
- `nunca_exportado`
- `com_novidades`
- `sem_novidades`

### Exportadores (`kindle_extractor/exporters.py`)

Responsabilidades:
- Gerar conteúdo em Markdown, HTML e TXT.
- Respeitar flags de metadados e bookmarks.
- Ordenar entradas antes da serialização.

### UI Streamlit (`kindle_extractor/ui.py`)

Responsabilidades:
- Orquestrar upload, análise, seleção e exportação.
- Persistir estado de sessão para seleção intermediária.
- Delegar regra de negócio aos serviços, sem lógica pesada na camada visual.

## Responsabilidades por Camada

- UI: interação e estado de sessão.
- Serviços: regra de negócio e classificação.
- Infra local: persistência em arquivo JSON.

Esse desenho facilita evolução incremental e testes focados em domínio, sem depender da renderização visual do Streamlit.
