"""Guarda os uploads analisados para a analise sobreviver a um restart.

O `ANALYSIS_CACHE` da api vive so na memoria do processo: reiniciar o backend
invalidava todo link `/clip/` e fazia export e painel devolverem 409. Aqui
ficam os bytes crus do arquivo, nao a estrutura ja parseada -- `parse_content`
e funcao pura de (conteudo + config) e reprocessar o `My Clippings.txt` inteiro
leva menos de um quinto de segundo, enquanto as entradas parseadas carregam
`datetime` e um cache interno da dedup que nao serializam direto.

Mesmas garantias do `processing_store`: escrita por arquivo temporario unico
mais `replace`, e um `RLock` por caminho resolvido. Projetado para um unico
processo escritor.
"""

import json
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from .datetime_utils import to_utc_iso

STORE_VERSION = 1
MAX_STORED_ANALYSES = 5
INDEX_FILENAME = "index.json"

_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: Dict[Path, threading.RLock] = {}


def _default_index() -> Dict[str, object]:
    return {"version": STORE_VERSION, "analyses": []}


class AnalysisStore:
    """Uploads analisados, do mais recente para o mais antigo."""

    def __init__(self, directory: Path, max_analyses: int = MAX_STORED_ANALYSES):
        self.directory = directory
        self.max_analyses = max_analyses
        self._lock = self._lock_for_path(directory)

    @staticmethod
    def _lock_for_path(path: Path) -> threading.RLock:
        lock_key = path.expanduser().resolve(strict=False)
        with _LOCKS_GUARD:
            if lock_key not in _PATH_LOCKS:
                _PATH_LOCKS[lock_key] = threading.RLock()
            return _PATH_LOCKS[lock_key]

    @property
    def index_path(self) -> Path:
        return self.directory / INDEX_FILENAME

    def _content_path(self, analysis_id: str) -> Path:
        return self.directory / f"{analysis_id}.txt"

    def _load_index(self) -> Dict[str, object]:
        if not self.index_path.exists():
            return _default_index()

        try:
            with open(self.index_path, "r", encoding="utf-8") as file:
                raw = json.load(file)
        except (json.JSONDecodeError, OSError):
            return _default_index()

        if not isinstance(raw, dict) or raw.get("version") != STORE_VERSION:
            return _default_index()

        entries = raw.get("analyses")
        if not isinstance(entries, list):
            return _default_index()

        return {
            "version": STORE_VERSION,
            "analyses": [entry for entry in entries if _is_usable_entry(entry)],
        }

    def _write_index(self, index: Dict[str, object]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp_path = self.index_path.with_name(f"{INDEX_FILENAME}.{uuid.uuid4().hex}.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as file:
                json.dump(index, file, ensure_ascii=False, indent=2)
            tmp_path.replace(self.index_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def save(
        self,
        analysis_id: str,
        raw_content: bytes,
        filename: Optional[str],
        config: dict,
    ) -> None:
        """Grava o upload e o promove a mais recente do indice."""
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)

            content_path = self._content_path(analysis_id)
            tmp_path = content_path.with_name(f"{content_path.name}.{uuid.uuid4().hex}.tmp")
            try:
                tmp_path.write_bytes(raw_content)
                tmp_path.replace(content_path)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

            index = self._load_index()
            entries = [
                entry for entry in index["analyses"] if entry.get("id") != analysis_id
            ]
            entries.insert(
                0,
                {
                    "id": analysis_id,
                    "filename": filename or "My Clippings.txt",
                    "uploaded_at": to_utc_iso(None),
                    "size": len(raw_content),
                    "config": config,
                },
            )

            index["analyses"] = entries[: self.max_analyses]
            self._write_index(index)
            self._drop_orphan_files({entry["id"] for entry in index["analyses"]})

    def _drop_orphan_files(self, keep_ids: set) -> None:
        """Sem isto, cada upload deixaria ~530 KB para tras no volume."""
        for path in self.directory.glob("*.txt"):
            if path.stem not in keep_ids:
                path.unlink(missing_ok=True)

    def get(self, analysis_id: str) -> Optional[dict]:
        """Entrada do indice mais o conteudo, ou None se algum lado sumiu."""
        with self._lock:
            entry = next(
                (
                    entry
                    for entry in self._load_index()["analyses"]
                    if entry.get("id") == analysis_id
                ),
                None,
            )
            if entry is None:
                return None

            content = self._read_content(analysis_id)
            if content is None:
                return None

            return {**entry, "content": content}

    def get_latest(self) -> Optional[dict]:
        with self._lock:
            for entry in self._load_index()["analyses"]:
                content = self._read_content(entry["id"])
                if content is not None:
                    return {**entry, "content": content}
            return None

    def _read_content(self, analysis_id: str) -> Optional[str]:
        path = self._content_path(analysis_id)
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def list_analyses(self) -> List[dict]:
        with self._lock:
            return list(self._load_index()["analyses"])


def _is_usable_entry(entry) -> bool:
    return isinstance(entry, dict) and isinstance(entry.get("id"), str) and entry["id"]
