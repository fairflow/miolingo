"""Quick Practice view — the vertical-slice UI (Milestone 3).

Flow: pick language -> category -> file -> phrase, play target audio (Piper via
the TTS dispatcher), record the user's attempt, transcribe + score off the UI
thread, show the result, and persist it via the controller.

All blocking work (TTS synth, mic capture, transcription) runs on a
``QThreadPool`` worker so the UI never freezes. The view holds no business
logic — it delegates to ``PracticeController`` (core, UI-free).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThreadPool, QUrl
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core.audio_capture import record_wav
from ..core.controller import PracticeController
from ..core.tts import generate_target_audio
from .workers import Worker


class PracticeView(QWidget):
    """The Quick Practice tab."""

    def __init__(self, controller: PracticeController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._pool = QThreadPool.globalInstance()
        self._phrases: list[dict] = []
        self._player = None  # lazily created (QtMultimedia is optional)
        self._audio_out = None
        self._temp_audio: Path | None = None

        self._build_ui()
        self._load_languages()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        selectors = QHBoxLayout()
        self.language_combo = QComboBox()
        self.language_combo.setObjectName("languageCombo")
        self.category_combo = QComboBox()
        self.category_combo.setObjectName("categoryCombo")
        self.file_combo = QComboBox()
        self.file_combo.setObjectName("fileCombo")
        selectors.addWidget(QLabel("Language:"))
        selectors.addWidget(self.language_combo)
        selectors.addWidget(QLabel("Category:"))
        selectors.addWidget(self.category_combo)
        selectors.addWidget(QLabel("Set:"))
        selectors.addWidget(self.file_combo)
        root.addLayout(selectors)

        self.phrase_list = QListWidget()
        self.phrase_list.setObjectName("phraseList")
        root.addWidget(self.phrase_list, stretch=1)

        actions = QHBoxLayout()
        self.play_button = QPushButton("Play target audio")
        self.play_button.setObjectName("playButton")
        self.record_button = QPushButton("Record && score")
        self.record_button.setObjectName("recordButton")
        actions.addWidget(self.play_button)
        actions.addWidget(self.record_button)
        root.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setObjectName("progressBar")
        self.progress.setRange(0, 0)  # indeterminate
        self.progress.hide()
        root.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        root.addWidget(self.status_label)

        self.result_label = QLabel("")
        self.result_label.setObjectName("resultLabel")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        root.addWidget(self.result_label)

        self.language_combo.currentTextChanged.connect(self._on_language_changed)
        self.category_combo.currentTextChanged.connect(self._on_category_changed)
        self.file_combo.currentTextChanged.connect(self._on_file_changed)
        self.play_button.clicked.connect(self.play_target_audio)
        self.record_button.clicked.connect(self.record_and_score)

    # -- population --------------------------------------------------------

    def _load_languages(self) -> None:
        self.language_combo.clear()
        self.language_combo.addItems(self._controller.available_languages())

    def _on_language_changed(self, lang: str) -> None:
        self.category_combo.clear()
        if not lang:
            return
        categories = self._controller.language_categories(lang)
        self.category_combo.addItems(sorted(categories.keys()))

    def _on_category_changed(self, category: str) -> None:
        self.file_combo.clear()
        lang = self.language_combo.currentText()
        if not lang or not category:
            return
        categories = self._controller.language_categories(lang)
        self.file_combo.addItems(categories.get(category, []))

    def _on_file_changed(self, filename: str) -> None:
        self.phrase_list.clear()
        self._phrases = []
        lang = self.language_combo.currentText()
        category = self.category_combo.currentText()
        if not (lang and category and filename):
            return
        try:
            self._phrases = self._controller.phrases_for(lang, category, filename)
        except Exception as e:  # noqa: BLE001 - bad file shouldn't crash the UI
            self.status_label.setText(f"Could not load set: {e}")
            return
        for phrase in self._phrases:
            text = phrase.get("text", "")
            trans = phrase.get("translation")
            label = f"{text}  —  {trans}" if trans else text
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, phrase)
            self.phrase_list.addItem(item)
        if self.phrase_list.count():
            self.phrase_list.setCurrentRow(0)

    # -- selection helpers -------------------------------------------------

    def selected_phrase_text(self) -> str | None:
        item = self.phrase_list.currentItem()
        if item is None:
            return None
        phrase = item.data(Qt.UserRole)
        return phrase.get("text") if isinstance(phrase, dict) else None

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.progress.setVisible(busy)
        self.play_button.setDisabled(busy)
        self.record_button.setDisabled(busy)
        self.status_label.setText(message)

    # -- actions -----------------------------------------------------------

    def play_target_audio(self) -> None:
        text = self.selected_phrase_text()
        if not text:
            self.status_label.setText("Select a phrase first.")
            return
        settings = self._controller.effective_settings()
        self._set_busy(True, "Synthesizing audio...")
        worker = Worker(generate_target_audio, text, settings)
        worker.signals.finished.connect(self._on_audio_ready)
        worker.signals.error.connect(self._on_worker_error)
        self._pool.start(worker)

    def _on_audio_ready(self, payload: object) -> None:
        self._set_busy(False)
        try:
            audio_bytes, _fmt = payload  # type: ignore[misc]
        except Exception:
            self.status_label.setText("No audio produced.")
            return
        if not audio_bytes:
            self.status_label.setText("No audio produced (TTS unavailable offline?).")
            return
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.write(audio_bytes)
        tmp.close()
        self._temp_audio = Path(tmp.name)
        if not self._ensure_player():
            self.status_label.setText("Audio playback unavailable (QtMultimedia missing).")
            return
        self._player.setSource(QUrl.fromLocalFile(tmp.name))
        self._player.play()

    def _ensure_player(self) -> bool:
        """Lazily construct the media player; QtMultimedia is an optional module."""
        if self._player is not None:
            return True
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except Exception:  # noqa: BLE001 - QtMultimedia not bundled
            return False
        self._player = QMediaPlayer(self)
        self._audio_out = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_out)
        return True

    def record_and_score(self) -> None:
        text = self.selected_phrase_text()
        if not text:
            self.status_label.setText("Select a phrase first.")
            return
        language = self.language_combo.currentText()
        settings = self._controller.effective_settings()
        duration = float(settings.get("duration", 3))
        self._set_busy(True, "Recording...")

        def _capture_and_score(progress_fn=None) -> dict[str, Any] | None:
            if progress_fn:
                progress_fn("Recording...")
            audio_bytes = record_wav(duration=duration)
            if progress_fn:
                progress_fn("Transcribing...")
            return self._controller.run_practice(
                target_text=text,
                audio_bytes=audio_bytes,
                language=language,
                progress_fn=progress_fn,
            )

        worker = Worker(_capture_and_score, pass_progress=True)
        worker.signals.progress.connect(self.status_label.setText)
        worker.signals.finished.connect(self._on_score_ready)
        worker.signals.error.connect(self._on_worker_error)
        self._pool.start(worker)

    def _on_score_ready(self, result: object) -> None:
        self._set_busy(False)
        if not isinstance(result, dict):
            self.result_label.setText("No result.")
            return
        pct = round(float(result.get("similarity", 0.0)) * 100, 1)
        verdict = "perfect" if result.get("exact_match") else f"edits: {result.get('edit_distance')}"
        self.result_label.setText(
            f"Target: {result.get('target', '')}\n"
            f"Heard:  {result.get('recognized', '')}\n"
            f"Score:  {pct}%  ({verdict})\n"
            f"Target IPA: {result.get('correct_ipa', '')}\n"
            f"Your IPA:   {result.get('user_ipa', '')}"
        )
        self.status_label.setText("Saved to history.")

    def _on_worker_error(self, message: str) -> None:
        self._set_busy(False)
        self.status_label.setText(f"Error: {message}")
