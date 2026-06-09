# Arquitetura

## Visão Geral

O projeto é organizado em camadas simples, com foco em regra de negócio e baixo acoplamento com a UI.

1. Entrada visual: `frontend/` (Vite React + shadcn/ui).
2. API local: `kindle_extractor/api.py` (FastAPI).
3. Núcleo de processamento: `extractor.py`.
4. Serviços de domínio: parser, deduplicação, seleção, persistência e exportadores.
5. Saída: ZIP exportado e store local JSON.

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

### API FastAPI (`kindle_extractor/api.py`)

Responsabilidades:
- Receber upload e configuração de processamento.
- Manter cache local em memória por `analysisId`.
- Chamar os serviços existentes para análise, seleção e exportação.
- Retornar ZIP e erros de reanálise obrigatória quando o cache não existir.

### Frontend React (`frontend/`)

Responsabilidades:
- Renderizar upload, configurações, métricas, filtros, tabela e exportação.
- Manter estado local de seleção e filtros.
- Usar componentes shadcn/ui e ícones lucide para controles.
- Delegar regra de negócio e persistência para a API.

## Responsabilidades por Camada

- Frontend: interação e estado visual.
- API: contrato HTTP, cache transitório e adaptação de requests.
- Serviços: regra de negócio e classificação.
- Infra local: persistência em arquivo JSON.

Esse desenho facilita evolução incremental e testes focados em domínio, API e comportamento visual essencial.
