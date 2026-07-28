"""
Braille 点阵渲染画布。

每个 Braille 字符渲染为 2×3 点阵，使用 QPainter 绘制。
支持自适应窗口宽度、上下翻页。
"""

from typing import List, Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QPalette
from PySide6.QtCore import Qt, QRect


# Braille Unicode 范围：U+2800 (⠀) ~ U+28FF (⣿)
# 每个字符代表 2×3 点的组合

# 浅色模式颜色
_LIGHT_DOT_ON = QColor(0x1A, 0x1A, 0x2E)
_LIGHT_DOT_OFF = QColor(0xE0, 0xE0, 0xE0)
_LIGHT_BG = QColor(0xFF, 0xFF, 0xFF)
_LIGHT_LINE = QColor(0xF0, 0xF0, 0xF0)
_LIGHT_MARGIN = QColor(0xFA, 0xFA, 0xFA)

# 深色模式颜色
_DARK_DOT_ON = QColor(0xE0, 0xE0, 0xE0)
_DARK_DOT_OFF = QColor(0x50, 0x50, 0x60)
_DARK_BG = QColor(0x1E, 0x1E, 0x2E)
_DARK_LINE = QColor(0x35, 0x35, 0x45)
_DARK_MARGIN = QColor(0x26, 0x26, 0x36)

# 点阵布局常量
DOT_RADIUS = 5.0               # 点半径 (px)
DOT_SPACING_X = 14             # 两列中心距 (px) — 左右两点的横向距离
DOT_SPACING_Y = 14             # 三行中心距 (px) — 上下两点的纵向距离
CELL_INNER_MARGIN = 5          # 单元内边距
CELL_GAP = 6                   # 相邻盲文字符之间的间距
LINE_SPACING = 2.0             # 行间距倍数
PAGE_MARGIN = 30               # 页边距 (px)


class BrailleCanvas(QWidget):
    """Braille 点阵渲染画布。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 100)
        self.setFocusPolicy(Qt.StrongFocus)

        # 内容
        self._lines: List[List[str]] = []  # 当前页的行列表
        self._page_label: str = ''

        # 状态
        self._chars_per_line = 40
        self._cell_width = int(DOT_SPACING_X + 2 * (DOT_RADIUS + CELL_INNER_MARGIN))
        self._cell_pitch = self._cell_width + CELL_GAP  # 含间距的步进
        self._cell_height = int(2 * DOT_SPACING_Y + 2 * (DOT_RADIUS + CELL_INNER_MARGIN))
        self._line_height = int(self._cell_height * LINE_SPACING)

    def set_lines(self, lines: List[List[str]], page_label: str = '') -> None:
        """设置当前页要显示的行。"""
        self._lines = lines
        self._page_label = page_label
        self.update()

    def set_font_size(self, factor: float = 1.0) -> None:
        """设置 Braille 点阵大小缩放。"""
        global DOT_RADIUS, DOT_SPACING_X, DOT_SPACING_Y
        DOT_RADIUS = 4.5 * factor
        DOT_SPACING_X = 10 * factor
        DOT_SPACING_Y = 10 * factor
        self._cell_width = int(DOT_SPACING_X + 2 * (DOT_RADIUS + CELL_INNER_MARGIN))
        self._cell_pitch = self._cell_width + CELL_GAP  # 含间距的步进
        self._cell_height = int(2 * DOT_SPACING_Y + 2 * (DOT_RADIUS + CELL_INNER_MARGIN))
        self._line_height = int(self._cell_height * LINE_SPACING)
        self.update()

    def calculate_chars_per_line(self) -> int:
        """根据当前窗口宽度计算每行可容纳字符数。"""
        available_width = self.width() - 2 * PAGE_MARGIN
        pitch = self._cell_pitch if hasattr(self, '_cell_pitch') else self._cell_width
        if pitch <= 0:
            return 40
        return max(1, available_width // pitch)

    def clear(self) -> None:
        """清空画布。"""
        self._lines = []
        self._page_label = ''
        self.update()

    def _is_dark_mode(self) -> bool:
        """检测当前是否为深色模式。"""
        bg = self.palette().color(QPalette.Window)
        return bg.lightness() < 128

    def _colors(self):
        """返回当前主题对应的颜色 (dot_on, dot_off, bg, line, margin)。"""
        if self._is_dark_mode():
            return (_DARK_DOT_ON, _DARK_DOT_OFF, _DARK_BG, _DARK_LINE, _DARK_MARGIN)
        return (_LIGHT_DOT_ON, _LIGHT_DOT_OFF, _LIGHT_BG, _LIGHT_LINE, _LIGHT_MARGIN)

    def paintEvent(self, event) -> None:
        """绘制画布。"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        dot_on, dot_off, bg, line_color, margin_color = self._colors()

        # 背景
        painter.fillRect(self.rect(), bg)

        # 如果没有内容
        if not self._lines:
            painter.end()
            return

        # 计算起始偏移
        x_offset = PAGE_MARGIN
        y_offset = PAGE_MARGIN

        # 逐行绘制
        for line_idx, line_chars in enumerate(self._lines):
            y_pos = y_offset + line_idx * self._line_height

            if y_pos + self._cell_height > self.height() - PAGE_MARGIN:
                break  # 超出绘图区域

            # 绘制该行每个 Braille 字符
            pitch = self._cell_pitch if hasattr(self, '_cell_pitch') else self._cell_width
            for char_idx, braille_char in enumerate(line_chars):
                x_pos = x_offset + char_idx * pitch

                if x_pos + self._cell_width > self.width() - PAGE_MARGIN:
                    break  # 超出绘图区域

                self._draw_braille_char(
                    painter, braille_char,
                    x_pos, y_pos,
                    self._cell_width, self._cell_height,
                    dot_on, dot_off,
                )

        painter.end()

    def _draw_braille_char(self, painter: QPainter, braille_char: str,
                           x: int, y: int, w: int, h: int,
                           dot_on: QColor, dot_off: QColor) -> None:
        """绘制单个 Braille 字符的 2×3 点阵。

        Braille 点阵布局（2 列 × 3 行）：
          列 0    列 1
          ┌──┐  ┌──┐
        R0│•1│  │•4│
          └──┘  └──┘
          ┌──┐  ┌──┐
        R1│•2│  │•5│
          └──┘  └──┘
          ┌──┐  ┌──┐
        R2│•3│  │•6│
          └──┘  └──┘

        每个点对应 Unicode Braille 中的一个 bit：
          bit 0 = dot 1 (左上)
          bit 1 = dot 2 (左中)
          bit 2 = dot 3 (左下)
          bit 3 = dot 4 (右上)
          bit 4 = dot 5 (右中)
          bit 5 = dot 6 (右下)
        """
        if not braille_char or len(braille_char) != 1:
            return

        code_point = ord(braille_char)

        # 非 Braille 字符 (U+2800..U+28FF) — 用系统字体显示
        if code_point < 0x2800 or code_point > 0x28FF:
            painter.setFont(QFont('Arial', int(h * 0.7)))
            painter.setPen(dot_on)
            painter.drawText(x, y, w, h, Qt.AlignCenter, braille_char)
            return

        dots_bits = code_point - 0x2800

        # 标准 Braille 2×3 网格中心位置
        # 列中心：单元宽度的 1/4 和 3/4
        cx0 = x + w * 0.25
        cx1 = x + w * 0.75
        # 行中心：单元高度的 1/6, 1/2, 5/6 (三等分)
        cy0 = y + h * (1.0 / 6.0)
        cy1 = y + h * 0.5
        cy2 = y + h * (5.0 / 6.0)

        dot_r = max(2.5, DOT_RADIUS)

        dot_positions = [
            (cx0, cy0),  # dot 1
            (cx0, cy1),  # dot 2
            (cx0, cy2),  # dot 3
            (cx1, cy0),  # dot 4
            (cx1, cy1),  # dot 5
            (cx1, cy2),  # dot 6
        ]

        # 先画所有灰点（浅色的背景点）
        painter.setBrush(dot_off)
        painter.setPen(Qt.NoPen)
        for dx, dy in dot_positions:
            painter.drawEllipse(
                int(dx - dot_r), int(dy - dot_r),
                int(2 * dot_r), int(2 * dot_r)
            )

        # 再画激活的点（实心圆）
        painter.setBrush(dot_on)
        painter.setPen(Qt.NoPen)
        for i, (dx, dy) in enumerate(dot_positions):
            if dots_bits & (1 << i):
                painter.drawEllipse(
                    int(dx - dot_r), int(dy - dot_r),
                    int(2 * dot_r), int(2 * dot_r)
                )

    def _draw_empty_hint(self, painter: QPainter) -> None:
        """无内容时不显示任何提示。"""
        pass

    def minimumSizeHint(self):
        """建议的最小尺寸。"""
        return self.minimumSize()

    def sizeHint(self):
        """建议的尺寸。"""
        return self.minimumSize()
