"""Vocabulary view — per-language word tracker (Milestone 5).

Add, edit, soft-delete, IPA autofill, CSV export, and "practice from vocab"
(emits ``practiceRequested`` so the main window hands the word to the Practice
tab). All persistence goes through ``VocabularyRepository`` via the controller;
CSV rendering uses the UI-free ``vocab_service``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..core import config, vocab_service
from ..core.controller import PracticeController


class VocabularyView(QWidget):
    """Manage the user's saved vocabulary for a language."""

    practiceRequested = Signal(str, str)  # (language_code, word)

    def __init__(self, controller: PracticeController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.language_combo = QComboBox()
        self.language_combo.setObjectName("vocabLanguageCombo")
        self.language_combo.addItems(sorted(config.MATERIAL_TO_TRAINING.keys()))
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("vocabSearchEdit")
        self.search_edit.setPlaceholderText("Search word or translation...")
        top.addWidget(QLabel("Language:"))
        top.addWidget(self.language_combo)
        top.addWidget(self.search_edit, stretch=1)
        root.addLayout(top)

        add_row = QHBoxLayout()
        self.word_edit = QLineEdit()
        self.word_edit.setObjectName("vocabWordEdit")
        self.word_edit.setPlaceholderText("New word")
        self.translation_edit = QLineEdit()
        self.translation_edit.setObjectName("vocabTranslationEdit")
        self.translation_edit.setPlaceholderText("Translation (optional)")
        self.add_button = QPushButton("Add")
        self.add_button.setObjectName("vocabAddButton")
        add_row.addWidget(self.word_edit, stretch=1)
        add_row.addWidget(self.translation_edit, stretch=1)
        add_row.addWidget(self.add_button)
        root.addLayout(add_row)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("vocabList")
        root.addWidget(self.list_widget, stretch=1)

        buttons = QHBoxLayout()
        self.edit_button = QPushButton("Edit translation")
        self.edit_button.setObjectName("vocabEditButton")
        self.autofill_button = QPushButton("Autofill IPA")
        self.autofill_button.setObjectName("vocabAutofillButton")
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("vocabDeleteButton")
        self.export_button = QPushButton("Export CSV")
        self.export_button.setObjectName("vocabExportButton")
        self.practice_button = QPushButton("Practice this word")
        self.practice_button.setObjectName("vocabPracticeButton")
        for b in (
            self.edit_button, self.autofill_button, self.delete_button,
            self.export_button, self.practice_button,
        ):
            buttons.addWidget(b)
        root.addLayout(buttons)

        self.status_label = QLabel("")
        self.status_label.setObjectName("vocabStatusLabel")
        root.addWidget(self.status_label)

        self.language_combo.currentTextChanged.connect(self.refresh)
        self.search_edit.textChanged.connect(self.refresh)
        self.add_button.clicked.connect(self.add_word)
        self.edit_button.clicked.connect(self.edit_translation)
        self.autofill_button.clicked.connect(self.autofill_ipa)
        self.delete_button.clicked.connect(self.delete_selected)
        self.export_button.clicked.connect(self.export_csv)
        self.practice_button.clicked.connect(self.practice_selected)

        self.refresh()

    # -- helpers -----------------------------------------------------------

    def current_language_code(self) -> str:
        return self.language_combo.currentText()

    def selected_row(self) -> dict | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        data = item.data(Qt.UserRole)
        return data if isinstance(data, dict) else None

    # -- actions -----------------------------------------------------------

    def refresh(self) -> None:
        self.list_widget.clear()
        lang = self.current_language_code()
        if not lang:
            return
        rows = self._controller.vocab_repo.list(
            language_code=lang, search=self.search_edit.text().strip()
        )
        for row in rows:
            label = row["word"]
            if row.get("translation"):
                label += f"  —  {row['translation']}"
            if row.get("ipa"):
                label += f"   [{row['ipa']}]"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, row)
            self.list_widget.addItem(item)

    def add_word(self) -> None:
        word = self.word_edit.text().strip()
        if not word:
            self.status_label.setText("Enter a word first.")
            return
        self._controller.vocab_repo.capture(
            language_code=self.current_language_code(),
            word=word,
            translation=self.translation_edit.text().strip() or None,
        )
        self.word_edit.clear()
        self.translation_edit.clear()
        self.status_label.setText(f"Added '{word}'.")
        self.refresh()

    def edit_translation(self) -> None:
        row = self.selected_row()
        if row is None:
            self.status_label.setText("Select a word first.")
            return
        new_value, ok = QInputDialog.getText(
            self, "Edit translation", "Translation:", text=row.get("translation") or ""
        )
        if ok:
            self._controller.vocab_repo.update(row["id"], translation=new_value or None)
            self.refresh()

    def autofill_ipa(self) -> None:
        row = self.selected_row()
        if row is None:
            self.status_label.setText("Select a word first.")
            return
        ipa = vocab_service.autofill_ipa(row["word"], self.current_language_code())
        if ipa is None:
            self.status_label.setText("IPA unavailable (espeak missing?).")
            return
        self._controller.vocab_repo.update(row["id"], ipa=ipa)
        self.status_label.setText(f"IPA: {ipa}")
        self.refresh()

    def delete_selected(self) -> None:
        row = self.selected_row()
        if row is None:
            self.status_label.setText("Select a word first.")
            return
        self._controller.vocab_repo.soft_delete(row["id"])
        self.status_label.setText(f"Deleted '{row['word']}'.")
        self.refresh()

    def export_csv(self) -> None:
        lang = self.current_language_code()
        rows = list(self._controller.vocab_repo.export_csv_rows(language_code=lang))
        csv_text = vocab_service.rows_to_csv(rows)
        path, _ = QFileDialog.getSaveFileName(
            self, "Export vocabulary", f"vocabulary_{lang}.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(csv_text)
        self.status_label.setText(f"Exported {len(rows)} words to {path}.")

    def practice_selected(self) -> None:
        row = self.selected_row()
        if row is None:
            self.status_label.setText("Select a word first.")
            return
        self.practiceRequested.emit(self.current_language_code(), row["word"])
