# Formato do Store de Processamento

Arquivo local padrão: `.kindle_processing_store.json`

## Estrutura (resumo)

```json
{
  "version": 2,
  "meta": {
    "updated_at": "2026-04-18T20:10:00+00:00"
  },
  "books": {
    "<book_key>": {
      "book_key": "...",
      "title": "...",
      "author": "...",
      "entry_signature_hashes": ["sha1", "..."],
      "highlight_signature_hashes": ["sha1", "..."],
      "content_signature_hash": "sha1",
      "highlight_signature_hash": "sha1",
      "highlight_count": 12,
      "note_count": 3,
      "bookmark_count": 4,
      "last_analysis_at": "ISO-8601 UTC",
      "last_export_at": "ISO-8601 UTC",
      "last_export_formats": ["markdown", "html"],
      "last_detected_processing": {
        "process_id": "sha1",
        "processed_at": "ISO-8601 UTC",
        "forced": false,
        "detected_status": "novo|atualizado|sem_mudancas",
        "new_highlights_count": 0,
        "content_signature_hash": "sha1",
        "highlight_signature_hash": "sha1"
      },
      "last_export": {
        "export_id": "sha1",
        "exported_at": "ISO-8601 UTC",
        "formats": ["markdown"],
        "content_signature_hash": "sha1",
        "processed_at": "ISO-8601 UTC",
        "reexport_without_changes": false
      },
      "processing_history": ["..."],
      "export_history": ["..."]
    }
  }
}
```

## Observações

- Store em JSON local e legível.
- Loader tolerante a arquivo inexistente, corrompido ou incompleto.
- Campos legados são normalizados para hashes estáveis (`sha1`).
- `last_analysis_at` e `last_export_at` permanecem separados por responsabilidade.
- Datas são serializadas em UTC; a exibição em UI é convertida para `America/Sao_Paulo`.
- Histórico limitado aos últimos 200 eventos por tipo.
