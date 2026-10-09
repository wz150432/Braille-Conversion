"""中文模式从菜单到懒加载文档的集成检查。"""

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from src.converter.chinese_rules import ChineseBrailleMode
from src.gui.main_window import MainWindow
from src.lazy_document import LazyBrailleDocument


def test_document_uses_default_standard_and_explicit_full_mode():
    assert LazyBrailleDocument('你的').get_page(0, 40, 10) == [list('⠝⠙')]
    assert LazyBrailleDocument('你的', mode='full').get_page(0, 40, 10) == [list('⠝⠊⠄⠙⠢')]


def test_source_lines_do_not_join_different_words():
    assert LazyBrailleDocument('你\n他').get_page(0, 40, 10) == [list('⠝ ⠞')]


def test_menu_has_mutually_exclusive_standard_modes():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window._chinese_mode == ChineseBrailleMode.STANDARD
        assert set(window._chinese_mode_actions) == set(ChineseBrailleMode)
        assert window._chinese_mode_actions[ChineseBrailleMode.STANDARD].isChecked()
        for mode in (ChineseBrailleMode.FULL, ChineseBrailleMode.TONE_REDUCED):
            window._chinese_mode_actions[mode].trigger()
            assert window._chinese_mode == mode
            assert sum(action.isChecked() for action in window._chinese_mode_actions.values()) == 1
    finally:
        window.close()


def test_mode_change_reloads_current_document_and_preserves_page(monkeypatch):
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    calls = []
    window._current_file = '/tmp/braille-mode-example.txt'
    window._current_page = 3
    monkeypatch.setattr(window, '_load_file', lambda path, target_page=None: calls.append(
        (path, target_page, window._chinese_mode)
    ))
    try:
        window._chinese_mode_actions[ChineseBrailleMode.FULL].trigger()
        assert calls == [('/tmp/braille-mode-example.txt', 3, ChineseBrailleMode.FULL)]
    finally:
        window._current_file = None
        window.close()
