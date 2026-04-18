# Formato do Store de Processamento

Arquivo local padrão: `.kindle_processing_store.json`

## Estrutura

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
      "last_processed_at": "ISO-8601",
      "last_exported_at": "ISO-8601",
      "last_export_formats": ["markdown", "html"],
      "last_detected_processing": {
        "process_id": "sha1",
        "processed_at": "ISO-8601",
        "forced": false,
        "detected_status": "novo|atualizado|sem mudanças",
        "new_highlights_count": 0,
        "content_signature_hash": "sha1",
        "highlight_signature_hash": "sha1",
        "highlight_count": 0,
        "note_count": 0,
        "bookmark_count": 0
      },
      "last_export": {
        "export_id": "sha1",
        "exported_at": "ISO-8601",
        "formats": ["markdown"],
        "content_signature_hash": "sha1",
        "processed_at": "ISO-8601",
        "reexport_without_changes": false
      },
      "processing_history": ["...eventos de processamento..."],
      "export_history": ["...eventos de export..."]
    }
  }
}
```

## Observações

- O arquivo continua em JSON local e legível.
- O loader é tolerante a arquivo inexistente, corrompido ou incompleto.
- Campos legados (`entry_signatures`, `highlight_signatures`) são convertidos para hashes estáveis (`sha1`).
- `last_processed_at` e `last_exported_at` são mantidos separadamente.
- `export_history[].reexport_without_changes=true` identifica reexportação sem alteração de conteúdo.
- `processing_history[].forced=true` identifica reprocessamento forçado.
- Histórico é limitado aos últimos 200 eventos por tipo para evitar crescimento ilimitado.
