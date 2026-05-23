"""Settings view — language, voice, Whisper model, scoring, TTS (Milestone 4).

A form bound to the ``SettingsRepository`` via the controller. Values load from
stored settings (over defaults) on construction and persist immediately on
``save()``; ``effective_settings()`` restores them on relaunch. Option lists
come from ``core.config`` so the UI holds no domain choices itself.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core import config
from ..core.controller import PracticeController


class SettingsView(QWidget):
    """Edit and persist user settings."""

    def __init__(self, controller: PracticeController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.source_language_combo = QComboBox()
        self.source_language_combo.setObjectName("settingsSourceLanguage")
        self.source_language_combo.addItems(config.SOURCE_LANGUAGE_OPTIONS)

        self.voice_combo = QComboBox()
        self.voice_combo.setObjectName("settingsVoice")
        self.voice_combo.setEditable(True)
        # Populate with the union of all configured voices.
        all_voices: list[str] = []
        for name in config.LANGUAGE_CONFIG:
            for v in config.voices_for_language(name):
                if v not in all_voices:
                    all_voices.append(v)
        self.voice_combo.addItems(all_voices)

        self.whisper_combo = QComboBox()
        self.whisper_combo.setObjectName("settingsWhisperModel")
        self.whisper_combo.addItems(config.WHISPER_MODEL_SIZES)

        self.tts_combo = QComboBox()
        self.tts_combo.setObjectName("settingsTtsEngine")
        self.tts_combo.addItems(config.TTS_ENGINES)

        self.algorithm_combo = QComboBox()
        self.algorithm_combo.setObjectName("settingsAlgorithm")
        self.algorithm_combo.addItems(config.COMPARISON_ALGORITHMS)

        self.duration_spin = QSpinBox()
        self.duration_spin.setObjectName("settingsDuration")
        self.duration_spin.setRange(1, 30)

        form.addRow("Source language:", self.source_language_combo)
        form.addRow("Voice:", self.voice_combo)
        form.addRow("Whisper model size:", self.whisper_combo)
        form.addRow("TTS engine:", self.tts_combo)
        form.addRow("Scoring algorithm:", self.algorithm_combo)
        form.addRow("Recording seconds:", self.duration_spin)
        root.addLayout(form)

        self.save_button = QPushButton("Save settings")
        self.save_button.setObjectName("settingsSaveButton")
        self.save_button.clicked.connect(self.save)
        root.addWidget(self.save_button)

        self.load()

    def load(self) -> None:
        """Populate widgets from effective (stored over default) settings."""
        s = self._controller.effective_settings()
        self._set_combo(self.source_language_combo, str(s.get("source_language", "English")))
        self._set_combo(self.voice_combo, str(s.get("voice", "pt-br")))
        self._set_combo(self.whisper_combo, str(s.get("whisper_model_size", "medium")))
        self._set_combo(self.tts_combo, str(s.get("tts_engine", "piper")))
        self._set_combo(
            self.algorithm_combo, str(s.get("comparison_algorithm", "edit_distance"))
        )
        self.duration_spin.setValue(int(s.get("duration", 3)))

    def save(self) -> None:
        """Persist the current form values to SQLite."""
        self._controller.settings_repo.update_many(
            {
                "source_language": self.source_language_combo.currentText(),
                "voice": self.voice_combo.currentText(),
                "whisper_model_size": self.whisper_combo.currentText(),
                "tts_engine": self.tts_combo.currentText(),
                "comparison_algorithm": self.algorithm_combo.currentText(),
                "duration": self.duration_spin.value(),
            }
        )

    @staticmethod
    def _set_combo(combo: QComboBox, value: str) -> None:
        idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.isEditable():
            combo.setEditText(value)
