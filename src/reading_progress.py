"""Persist the last reading page for each opened document."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

try:
    from PySide6.QtCore import QSettings
except ImportError:  # pragma: no cover - GUI dependency is optional for pure tests
    QSettings = None


_SETTINGS_KEY = 'reading_positions'


class ReadingProgressStore:
    """Store zero-based page numbers keyed by normalized file path."""

    def __init__(self, settings: Any = None):
        if settings is None:
            if QSettings is None:
                raise RuntimeError('PySide6 is required for persistent reading progress')
            settings = QSettings()
        self._settings = settings

    @staticmethod
    def normalize_path(file_path: str) -> str:
        return os.path.normcase(os.path.realpath(os.path.expanduser(file_path)))

    def _load_all(self) -> Dict[str, int]:
        raw = self._settings.value(_SETTINGS_KEY, '')
        if isinstance(raw, dict):
            data = raw
        elif isinstance(raw, str) and raw:
            try:
                data = json.loads(raw)
            except (TypeError, ValueError):
                return {}
        else:
            return {}

        if not isinstance(data, dict):
            return {}

        positions: Dict[str, int] = {}
        for path, page in data.items():
            try:
                page_num = int(page)
            except (TypeError, ValueError):
                continue
            if page_num >= 0:
                positions[str(path)] = page_num
        return positions

    def _save_all(self, positions: Dict[str, int]) -> None:
        self._settings.setValue(_SETTINGS_KEY, json.dumps(positions, ensure_ascii=True))
        sync = getattr(self._settings, 'sync', None)
        if callable(sync):
            sync()

    def get_page(self, file_path: str) -> Optional[int]:
        return self._load_all().get(self.normalize_path(file_path))

    def set_page(self, file_path: str, page_num: int) -> None:
        positions = self._load_all()
        positions[self.normalize_path(file_path)] = max(0, int(page_num))
        self._save_all(positions)

    def clear(self, file_path: str) -> None:
        positions = self._load_all()
        if positions.pop(self.normalize_path(file_path), None) is not None:
            self._save_all(positions)
