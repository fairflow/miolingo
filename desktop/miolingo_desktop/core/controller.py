"""Application controller: wires core logic to storage, UI-free.

This is the seam between the Qt views (M3+) and the rest of the system. It is
deliberately framework-free (no PySide6) so the whole practice flow can be
driven and asserted in a headless integration test. Qt workers call these
methods off the UI thread.

Responsibilities:
- expose available languages / phrases from bundled materials,
- run a practice attempt (transcribe + score) and persist the result,
- read back recent history.

Settings are read from the SQLite ``SettingsRepository``, falling back to
``DEFAULT_SETTINGS`` for any key not yet stored.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import config, materials
from .asr import ProgressFn
from .practice import practice_word_from_audio
from ..data import Database, PracticeRepository, SettingsRepository


class PracticeController:
    """Coordinates materials, the practice pipeline, and persistence."""

    def __init__(self, db: Database) -> None:
        self._db = db
        self.settings_repo = SettingsRepository(db)
        self.practice_repo = PracticeRepository(db)

    # -- settings ----------------------------------------------------------

    def effective_settings(self) -> dict[str, Any]:
        """Stored settings merged over defaults (stored wins)."""
        merged = config.default_settings()
        merged.update(self.settings_repo.get_all())
        return merged

    # -- materials ---------------------------------------------------------

    def available_languages(self) -> list[str]:
        return materials.get_available_languages()

    def phrases_for(self, language: str, category: str, filename: str) -> list[dict]:
        meta = materials.get_file_metadata(language, category, filename)
        path = meta.get("path")
        if path is None:
            return []
        if category.startswith("unified-"):
            # Project the unified file for (target=language, source=en).
            return list(materials.load_unified_phrase_file(str(path), language, "en"))
        return materials.load_phrase_file(str(path))

    def language_categories(self, language: str) -> dict[str, list[str]]:
        return materials.get_language_structure(language)

    # -- practice ----------------------------------------------------------

    def run_practice(
        self,
        *,
        target_text: str,
        audio_bytes: bytes,
        language: str,
        progress_fn: ProgressFn | None = None,
        warn_fn: Callable[[str], None] | None = None,
        transcribe_fn: Callable[..., str] | None = None,
    ) -> dict[str, Any] | None:
        """Score *audio_bytes* against *target_text* and persist the attempt.

        Returns the result dict (also containing the saved ``attempt_id``), or
        ``None`` on error. ``transcribe_fn`` is injectable for tests so the flow
        runs without a Whisper model.
        """
        settings = self.effective_settings()
        language_code = config.get_language_code(language)

        saved_id: dict[str, str] = {}

        def _persist(result: dict[str, Any]) -> None:
            saved_id["id"] = self.practice_repo.save_from_result(language_code, result)

        result = practice_word_from_audio(
            target_text,
            audio_bytes,
            settings,
            language=language,
            on_result=_persist,
            warn_fn=warn_fn,
            progress_fn=progress_fn,
            transcribe_fn=transcribe_fn,
        )
        if result is not None and "id" in saved_id:
            result["attempt_id"] = saved_id["id"]
        return result

    # -- history -----------------------------------------------------------

    def recent_history(
        self, *, language: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        code = config.get_language_code(language) if language else None
        return self.practice_repo.list_history(language_code=code, limit=limit)
