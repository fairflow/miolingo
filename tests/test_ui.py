"""
Tests for ui package: import smoke tests for all exported names.

Functions requiring a live Streamlit runtime, database, or audio pipeline
are not exercised here — only module importability and export completeness.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# ui.practice_tab
# ---------------------------------------------------------------------------

class TestPracticeTabImports:
    """Verify ui.practice_tab is importable and exports expected names."""

    def test_import_practice_word_from_audio(self):
        from ui.practice_tab import practice_word_from_audio
        assert callable(practice_word_from_audio)

    def test_import_save_current_session(self):
        from ui.practice_tab import save_current_session
        assert callable(save_current_session)

    def test_import_render_practice_interface(self):
        from ui.practice_tab import render_practice_interface
        assert callable(render_practice_interface)

    def test_import_render_practice_results(self):
        from ui.practice_tab import render_practice_results
        assert callable(render_practice_results)


# ---------------------------------------------------------------------------
# ui.story_tab
# ---------------------------------------------------------------------------

class TestStoryTabImports:
    """Verify ui.story_tab is importable and exports expected names."""

    def test_import_render_story_reader(self):
        from ui.story_tab import render_story_reader
        assert callable(render_story_reader)

    def test_import_render_full_story(self):
        from ui.story_tab import render_full_story
        assert callable(render_full_story)

    def test_import_render_scene_by_scene(self):
        from ui.story_tab import render_scene_by_scene
        assert callable(render_scene_by_scene)

    def test_import_render_scene_practice_mode(self):
        from ui.story_tab import render_scene_practice_mode
        assert callable(render_scene_practice_mode)


# ---------------------------------------------------------------------------
# ui.statistics_tab
# ---------------------------------------------------------------------------

class TestStatisticsTabImports:
    """Verify ui.statistics_tab is importable and exports expected names."""

    def test_import_render_statistics_tab(self):
        from ui.statistics_tab import render_statistics_tab
        assert callable(render_statistics_tab)


# ---------------------------------------------------------------------------
# ui.history_tab
# ---------------------------------------------------------------------------

class TestHistoryTabImports:
    """Verify ui.history_tab is importable and exports expected names."""

    def test_import_load_history(self):
        from ui.history_tab import load_history
        assert callable(load_history)

    def test_import_save_history(self):
        from ui.history_tab import save_history
        assert callable(save_history)

    def test_import_render_history_tab(self):
        from ui.history_tab import render_history_tab
        assert callable(render_history_tab)


# ---------------------------------------------------------------------------
# ui package __init__
# ---------------------------------------------------------------------------

class TestUiPackage:
    """Verify the ui package itself is importable."""

    def test_import_ui_package(self):
        import ui
        assert ui is not None


# ---------------------------------------------------------------------------
# save_history — pure-function behaviour (no-op legacy)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# ui.quick_practice_tab
# ---------------------------------------------------------------------------

class TestQuickPracticeTabImports:
    """Verify ui.quick_practice_tab is importable and exports expected names."""

    def test_import_render_quick_practice_tab(self):
        from ui.quick_practice_tab import render_quick_practice_tab
        assert callable(render_quick_practice_tab)

    def test_import_render_materials_loader(self):
        from ui.quick_practice_tab import _render_materials_loader
        assert callable(_render_materials_loader)

    def test_import_render_practice_area(self):
        from ui.quick_practice_tab import _render_practice_area
        assert callable(_render_practice_area)

    def test_import_render_guided_mode(self):
        from ui.quick_practice_tab import _render_guided_mode
        assert callable(_render_guided_mode)

    def test_import_render_free_text_mode(self):
        from ui.quick_practice_tab import _render_free_text_mode
        assert callable(_render_free_text_mode)


class TestSaveHistory:
    """save_history is a legacy no-op — should accept any list without error."""

    def test_save_history_empty(self):
        from ui.history_tab import save_history
        result = save_history([])
        assert result is None  # No-op returns None

    def test_save_history_nonempty(self):
        from ui.history_tab import save_history
        dummy = [{"date": "2024-01-01", "practices": []}]
        result = save_history(dummy)
        assert result is None
