"""
主窗口：菜单栏、Braille 画布、状态栏。

快捷键:
  Ctrl+O  打开文件    Ctrl+G  跳页
  Left    上一页       Right   下一页
  Ctrl+R  重新载入
"""

import os
import sys
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QInputDialog,
    QLabel, QStatusBar, QMessageBox, QMenuBar, QMenu, QPushButton,
    QApplication,
)
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import (
    QAction, QDragEnterEvent, QDropEvent,
    QPalette, QColor,
)

from src.lazy_document import LazyBrailleDocument
from src.gui.braille_canvas import BrailleCanvas
from src.gui.file_dialog import (
    open_file_dialog, read_file_content, FileDropHandler
)

logger = logging.getLogger(__name__)
DEFAULT_LINES_PER_PAGE = 10

# ── 主题 ──────────────────────────────────────────────────────

THEME_SYSTEM = 0
THEME_LIGHT = 1
THEME_DARK = 2

THEME_LABELS = {THEME_SYSTEM: '自动', THEME_LIGHT: '浅色', THEME_DARK: '深色'}
THEME_TIPS = {THEME_SYSTEM: '跟随系统', THEME_LIGHT: '浅色模式', THEME_DARK: '深色模式'}


def _detect_system_theme() -> int:
    """检测 Windows 系统主题。"""
    if sys.platform != 'win32':
        return THEME_LIGHT
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
        )
        value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
        winreg.CloseKey(key)
        return THEME_LIGHT if value == 1 else THEME_DARK
    except Exception:
        return THEME_LIGHT


def _make_light_palette() -> QPalette:
    """浅色调色板。"""
    p = QPalette()
    p.setColor(QPalette.Window, QColor(0xF5, 0xF5, 0xF5))
    p.setColor(QPalette.WindowText, QColor(0x1A, 0x1A, 0x2E))
    p.setColor(QPalette.Base, QColor(0xFF, 0xFF, 0xFF))
    p.setColor(QPalette.AlternateBase, QColor(0xF0, 0xF0, 0xF0))
    p.setColor(QPalette.Text, QColor(0x1A, 0x1A, 0x2E))
    p.setColor(QPalette.Button, QColor(0xE8, 0xE8, 0xE8))
    p.setColor(QPalette.ButtonText, QColor(0x1A, 0x1A, 0x2E))
    p.setColor(QPalette.Highlight, QColor(0x3A, 0x7C, 0xBF))
    p.setColor(QPalette.HighlightedText, QColor(0xFF, 0xFF, 0xFF))
    return p


def _make_dark_palette() -> QPalette:
    """深色调色板。"""
    p = QPalette()
    p.setColor(QPalette.Window, QColor(0x1E, 0x1E, 0x2E))
    p.setColor(QPalette.WindowText, QColor(0xE0, 0xE0, 0xE0))
    p.setColor(QPalette.Base, QColor(0x26, 0x26, 0x36))
    p.setColor(QPalette.AlternateBase, QColor(0x2D, 0x2D, 0x3D))
    p.setColor(QPalette.Text, QColor(0xE0, 0xE0, 0xE0))
    p.setColor(QPalette.Button, QColor(0x35, 0x35, 0x45))
    p.setColor(QPalette.ButtonText, QColor(0xE0, 0xE0, 0xE0))
    p.setColor(QPalette.Highlight, QColor(0x5A, 0x9C, 0xDF))
    p.setColor(QPalette.HighlightedText, QColor(0xFF, 0xFF, 0xFF))
    return p


def _apply_theme(app: QApplication, theme: int):
    """应用主题到整个应用。"""
    if theme == THEME_SYSTEM:
        sys_theme = _detect_system_theme()
        palette = _make_light_palette() if sys_theme == THEME_LIGHT else _make_dark_palette()
    elif theme == THEME_LIGHT:
        palette = _make_light_palette()
    else:
        palette = _make_dark_palette()
    app.setPalette(palette)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Braille 转换阅读器")
        self.setMinimumSize(700, 500)
        self.resize(1000, 700)

        self._current_file: Optional[str] = None
        self._doc: Optional[LazyBrailleDocument] = None
        self._current_page: int = 0
        self._total_pages: int = 0
        self._is_loading: bool = False
        self._toned: bool = True
        self._theme: int = THEME_SYSTEM

        self._setup_menubar()
        self._setup_ui()
        self._setup_connections()
        self.setAcceptDrops(True)
        self._update_ui_state()

        # 应用默认主题
        self._apply_current_theme()

    # ── 菜单栏 — 解决 Windows 自动生成 File(F) 的问题 ────────────

    def _setup_menubar(self):
        """显式创建菜单栏（不依赖 self.menuBar() 的自动创建，防止 Windows 重复菜单）。"""
        mb = QMenuBar(self)
        mb.setNativeMenuBar(False)
        self.setMenuBar(mb)
        file_menu = mb.addMenu("文件(&F)")
        self._act_open = QAction("打开(&O)...\tCtrl+O", self)
        self._act_open.setShortcut("Ctrl+O")
        file_menu.addAction(self._act_open)
        file_menu.addSeparator()
        act_quit = QAction("退出(&X)\tAlt+F4", self)
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        nav_menu = mb.addMenu("导航(&N)")
        self._act_prev = QAction("上一页\tLeft", self)
        self._act_prev.setShortcut("Left")
        nav_menu.addAction(self._act_prev)
        self._act_next = QAction("下一页\tRight", self)
        self._act_next.setShortcut("Right")
        nav_menu.addAction(self._act_next)
        nav_menu.addSeparator()
        self._act_jump = QAction("跳转页数(&J)...\tCtrl+G", self)
        self._act_jump.setShortcut("Ctrl+G")
        nav_menu.addAction(self._act_jump)

        view_menu = mb.addMenu("视图(&V)")
        self._act_reload = QAction("重新载入\tCtrl+R", self)
        self._act_reload.setShortcut("Ctrl+R")
        view_menu.addAction(self._act_reload)
        self._act_tone = QAction("中文带调", self)
        self._act_tone.setCheckable(True)
        self._act_tone.setChecked(True)  # 默认开启
        view_menu.addAction(self._act_tone)

    # ── 布局 ────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._canvas = BrailleCanvas()
        main_layout.addWidget(self._canvas, 1)

        sb = QStatusBar()
        self.setStatusBar(sb)

        # 主题切换按钮（左下角）
        self._theme_btn = QPushButton(THEME_LABELS[THEME_SYSTEM])
        self._theme_btn.setFixedSize(48, 26)
        self._theme_btn.setFlat(True)
        self._theme_btn.setToolTip(THEME_TIPS[THEME_SYSTEM])
        self._theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._theme_btn.setStyleSheet('font-size: 13px; font-weight: bold;')
        self._theme_btn.clicked.connect(self._on_theme_toggle)
        sb.addWidget(self._theme_btn)

        self._status_label = QLabel("就绪")
        sb.addWidget(self._status_label)
        self._page_label = QLabel("")
        sb.addPermanentWidget(self._page_label)
        self._file_info_label = QLabel("")
        sb.addPermanentWidget(self._file_info_label)

    def _setup_connections(self):
        self._act_open.triggered.connect(self._on_open_file)
        self._act_prev.triggered.connect(self._on_prev_page)
        self._act_next.triggered.connect(self._on_next_page)
        self._act_jump.triggered.connect(self._on_jump_page)
        self._act_reload.triggered.connect(self._on_reload)
        self._act_tone.toggled.connect(self._on_tone_toggle)

    # ── 事件 ──────────────────────────────────────────────────────

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        path = FileDropHandler.get_dropped_file_path(event)
        if path:
            self._load_file(path)
        else:
            self._status_label.setText("不支持的文件格式")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._doc is not None:
            self._doc.invalidate()
            QTimer.singleShot(150, self._on_resize_done)

    def _on_resize_done(self):
        if self._doc is None:
            return
        self._recalc_total_pages()
        self._show_page(self._current_page)

    # ── 文件加载 ──────────────────────────────────────────────────

    def _on_open_file(self):
        path = open_file_dialog(self)
        if path:
            self._load_file(path)

    def _load_file(self, file_path: str, target_page: int = 0):
        if self._is_loading:
            return
        self._is_loading = True
        self._current_file = file_path
        self._current_page = target_page
        fname = os.path.basename(file_path)
        self._status_label.setText(f"读取: {fname}...")
        QTimer.singleShot(0, lambda: self._do_load(file_path, target_page))

    def _do_load(self, file_path: str, target_page: int = 0):
        try:
            content = read_file_content(file_path)
            if content is None:
                self._is_loading = False
                self._status_label.setText("读取失败")
                QMessageBox.warning(self, "错误", f"无法读取: {file_path}")
                self._update_ui_state()
                return
        except Exception as e:
            self._is_loading = False
            self._status_label.setText("读取失败")
            QMessageBox.warning(self, "错误", str(e))
            self._update_ui_state()
            return

        self._is_loading = False

        if not content.strip():
            self._status_label.setText("文件为空")
            self._canvas.clear()
            self._doc = None
            self._update_ui_state()
            return

        try:
            self._doc = LazyBrailleDocument(content, toned=self._toned)
        except Exception as e:
            self._status_label.setText("创建文档失败")
            QMessageBox.critical(self, "错误", str(e))
            self._update_ui_state()
            return

        self._recalc_total_pages()
        self._show_page(target_page)
        self._status_label.setText("就绪")

    # ── 页数 ──────────────────────────────────────────────────────

    def _recalc_total_pages(self):
        if self._doc is None:
            return
        cpl = self._canvas.calculate_chars_per_line()
        self._total_pages = self._doc.estimated_pages(cpl, DEFAULT_LINES_PER_PAGE)
        if self._total_pages < 1:
            self._total_pages = 1

    # ── 显示 ──────────────────────────────────────────────────────

    def _show_page(self, page_num: int):
        if self._doc is None:
            return
        # clamp
        page_num = max(0, min(page_num, self._total_pages - 1))
        self._current_page = page_num

        cpl = self._canvas.calculate_chars_per_line()
        try:
            rows = self._doc.get_page(page_num, cpl, DEFAULT_LINES_PER_PAGE)
        except Exception as e:
            self._status_label.setText(f"转换失败: {e}")
            return

        if not rows or rows == [[]]:
            # 可能文件结束了，回到最后一页
            cached = self._doc.cached_count()
            if cached > 0:
                last = max(self._doc._cache.keys())
                self._current_page = last
                rows = self._doc.get_page(last, cpl, DEFAULT_LINES_PER_PAGE)
            else:
                return

        self._display_page(self._current_page, rows)

    def _display_page(self, page_num: int, rows: list):
        self._canvas.set_lines(rows, f"{page_num + 1} / {self._total_pages}")
        self._page_label.setText(f"{page_num + 1} / {self._total_pages}")
        fname = os.path.basename(self._current_file or "")
        self._file_info_label.setText(
            f"{fname}  |  {self._total_pages} 页  |  第 {page_num + 1} 页"
        )
        self._update_ui_state()

    # ── 翻页 ──────────────────────────────────────────────────────

    def _on_prev_page(self):
        if self._doc is None or self._current_page <= 0:
            return
        self._current_page -= 1
        self._show_page(self._current_page)

    def _on_next_page(self):
        if self._doc is None:
            return
        if self._current_page >= self._total_pages - 1:
            return  # 到最后一页了
        self._current_page += 1
        self._show_page(self._current_page)

    def _on_jump_page(self):
        if self._doc is None:
            QMessageBox.information(self, "提示", "请先打开一个文件")
            return
        if self._total_pages < 2:
            QMessageBox.information(self, "提示", "只有一页，无需跳转")
            return

        page, ok = QInputDialog.getInt(
            self, "跳转",
            f"输入页码 (1 - {self._total_pages}):",
            value=self._current_page + 1,
            minValue=1, maxValue=self._total_pages, step=1
        )
        if ok:
            self._show_page(page - 1)

    def _on_reload(self):
        if self._current_file:
            self._load_file(self._current_file)

    def _on_tone_toggle(self, checked: bool):
        self._toned = checked
        if self._current_file:
            saved_page = self._current_page
            self._load_file(self._current_file, target_page=saved_page)

    # ── 主题 ──────────────────────────────────────────────────────

    def _apply_current_theme(self):
        """仅应用当前主题，不切换。"""
        self._theme_btn.setText(THEME_LABELS[self._theme])
        self._theme_btn.setToolTip(THEME_TIPS[self._theme])
        app = QApplication.instance()
        if app:
            _apply_theme(app, self._theme)
            # 按钮颜色手动设，确保在浅色/深色下都可见
            if self._theme == THEME_SYSTEM:
                sys_theme = _detect_system_theme()
            else:
                sys_theme = self._theme
            if sys_theme == THEME_LIGHT:
                self._theme_btn.setStyleSheet(
                    'font-size: 13px; font-weight: bold; color: #1a1a2e;'
                )
            else:
                self._theme_btn.setStyleSheet(
                    'font-size: 13px; font-weight: bold; color: #e0e0e0;'
                )
        self._canvas.update()

    def _on_theme_toggle(self):
        """切换主题：跟随系统 → 浅色 → 深色 → 跟随系统..."""
        self._theme = (self._theme + 1) % 3
        self._apply_current_theme()

    # ── 状态 ──────────────────────────────────────────────────────

    def _update_ui_state(self):
        has = self._doc is not None
        self._act_prev.setEnabled(has and self._current_page > 0)
        self._act_next.setEnabled(has and self._current_page < self._total_pages - 1)
        self._act_jump.setEnabled(has and self._total_pages > 1)
        self._act_reload.setEnabled(bool(self._current_file))
