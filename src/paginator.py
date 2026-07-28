"""
分页器：将 Braille 字符序列按画布容量切分为行和页。

输入：Braille 字符列表、每行字符数(列数)、每页行数
输出：list[list[list[str]]] — 页码 → 行 → Braille 字符
"""

from typing import List


def split_lines(chars: List[str], chars_per_line: int) -> List[List[str]]:
    """将 Braille 字符列表按每行字符数分行。

    规则：
      - 尽量在空格处换行（保持单词完整）
      - 若一行不含空格，在最大列数处硬截断
      - 连续空格合并为单个空格
      - 前导空格去除

    Args:
        chars: Braille 字符列表。
        chars_per_line: 每行最大字符数（列数）。

    Returns:
        行列表，每行是一个 Braille 字符列表。
    """
    if not chars or chars_per_line <= 0:
        return []

    lines: List[List[str]] = []
    current_line: List[str] = []
    # 用于断词的位置
    last_space_idx = -1

    for i, ch in enumerate(chars):
        # 空格处理：合并连续空格
        if ch == ' ':
            if current_line and current_line[-1] != ' ':
                current_line.append(ch)
                # 记录最后一个空格在行内的位置
                last_space_idx = len(current_line) - 1
            continue

        current_line.append(ch)

        # 超过行宽时换行
        if len(current_line) >= chars_per_line:
            if last_space_idx >= 0 and last_space_idx < len(current_line) - 1:
                # 在最后一个空格处断开
                line_part = current_line[:last_space_idx]
                remainder = current_line[last_space_idx + 1:]
                if line_part:
                    _strip_trailing_spaces(line_part)
                    lines.append(line_part)
                current_line = remainder
            else:
                # 无可换行位置，硬截断
                lines.append(current_line)
                current_line = []
            last_space_idx = -1

    # 剩余内容
    if current_line:
        _strip_trailing_spaces(current_line)
        if current_line:
            lines.append(current_line)

    return lines


def _strip_trailing_spaces(line: List[str]) -> None:
    """去除行尾空格（原地修改）。"""
    while line and line[-1] == ' ':
        line.pop()


def paginate(chars: List[str],
             chars_per_line: int,
             lines_per_page: int) -> List[List[List[str]]]:
    """将 Braille 字符序列分页。

    Args:
        chars: Braille 字符列表。
        chars_per_line: 每行字符数。
        lines_per_page: 每页行数。

    Returns:
        list[list[list[str]]]
        外层是页码，中层是行，内层是 Braille 字符列表。

    如果输入为空，返回 [[]]（一页空内容）。
    如果 chars_per_line <= 0 或 lines_per_page <= 0，返回按单行分页的结果。
    """
    if not chars:
        return [[[]]]

    if chars_per_line <= 0 or lines_per_page <= 0:
        # 无效参数：每行/每页以1为限
        cpl = max(chars_per_line, 1)
        lpp = max(lines_per_page, 1)
    else:
        cpl = chars_per_line
        lpp = lines_per_page

    lines = split_lines(chars, cpl)

    # 按页分组
    pages: List[List[List[str]]] = []
    for i in range(0, len(lines), lpp):
        page_lines = lines[i:i + lpp]
        pages.append(page_lines)

    if not pages:
        return [[[]]]

    return pages


class Paginator:
    """Braille 分页器，管理分页状态和重排。"""

    def __init__(self, braille_chars: List[str],
                 chars_per_line: int = 40,
                 lines_per_page: int = 10):
        """
        Args:
            braille_chars: Braille 字符列表（由 Converter 产生）。
            chars_per_line: 每行字符数。
            lines_per_page: 每页行数。
        """
        self._raw_chars = braille_chars
        self._chars_per_line = chars_per_line
        self._lines_per_page = lines_per_page
        self._pages = paginate(braille_chars, chars_per_line, lines_per_page)
        self._current_page = 0

    @property
    def total_pages(self) -> int:
        """总页数。"""
        return len(self._pages)

    @property
    def current_page(self) -> int:
        """当前页码（从 0 开始）。"""
        return self._current_page

    @current_page.setter
    def current_page(self, page: int) -> None:
        """设置当前页码（自动 clamp）。"""
        if self.total_pages > 0:
            self._current_page = max(0, min(page, self.total_pages - 1))
        else:
            self._current_page = 0

    def get_page(self, page_num: int) -> List[List[str]]:
        """获取指定页码的行列表。"""
        if 0 <= page_num < self.total_pages:
            return self._pages[page_num]
        return [[]]

    def next_page(self) -> bool:
        """翻到下一页。返回 True 如果成功。"""
        if self._current_page < self.total_pages - 1:
            self._current_page += 1
            return True
        return False

    def prev_page(self) -> bool:
        """翻到上一页。返回 True 如果成功。"""
        if self._current_page > 0:
            self._current_page -= 1
            return True
        return False

    def resize(self, chars_per_line: int, lines_per_page: int) -> None:
        """窗口缩放时重新分页。

        Args:
            chars_per_line: 新每行字符数。
            lines_per_page: 新每页行数。
        """
        if chars_per_line < 1:
            chars_per_line = 1
        if lines_per_page < 1:
            lines_per_page = 1

        self._chars_per_line = chars_per_line
        self._lines_per_page = lines_per_page
        self._pages = paginate(self._raw_chars, chars_per_line, lines_per_page)
        self._current_page = min(self._current_page, max(0, self.total_pages - 1))

    def has_next(self) -> bool:
        """是否有下一页。"""
        return self._current_page < self.total_pages - 1

    def has_prev(self) -> bool:
        """是否有上一页。"""
        return self._current_page > 0

    @property
    def current_page_label(self) -> str:
        """页码标签，如 '3 / 42'。"""
        total = self.total_pages if self.total_pages > 0 else 1
        return f"{self._current_page + 1} / {total}"
