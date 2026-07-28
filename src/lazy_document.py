"""
懒加载 Braille 文档：逐页按需转换，边显示边翻译。

核心理念：
  逐行转换原始文本 → 累积 Braille 字符 → 够一页就停止 → 显示
  翻页时接着上次的位置继续转换，已转换完的页缓存复用。
"""

import logging
from typing import List, Dict, Tuple

from src.converter.braille_converter import convert_text
from src.paginator import split_lines

logger = logging.getLogger(__name__)


class LazyBrailleDocument:
    """懒加载盲文文档。

    用法:
        doc = LazyBrailleDocument(raw_text)
        page = doc.get_page(0, chars_per_line=40, lines_per_page=10)
    """

    def __init__(self, text: str, toned: bool = False):
        self._lines = text.split('\n') if text else []
        self._toned = toned
        self._cpl: int = 0
        self._lpp: int = 0
        # page_num → (rows, first_line_idx, last_line_idx)
        self._cache: Dict[int, Tuple[List[List[str]], int, int]] = {}

    def invalidate(self):
        """清空缓存（resize 时调用）。"""
        self._cache.clear()

    @property
    def line_count(self) -> int:
        return len(self._lines)

    def estimated_pages(self, cpl: int, lpp: int) -> int:
        """粗略估算总页数。"""
        if not self._lines:
            return 0
        cpl = max(cpl, 1)
        lpp = max(lpp, 1)
        total = sum(
            max(1, len(line) * 2 if any('一' <= c <= '鿿' for c in line) else len(line))
            for line in self._lines
        )
        return max(1, (max(1, total // cpl) + lpp - 1) // lpp)

    def cached_count(self) -> int:
        return len(self._cache)

    # ── 核心 ──────────────────────────────────────────────────────

    def get_page(self, page_num: int, cpl: int, lpp: int) -> List[List[str]]:
        """获取指定页。"""
        if not self._lines:
            return [[]]

        # resize → 清缓存
        if cpl != self._cpl or lpp != self._lpp:
            self.invalidate()
            self._cpl = cpl
            self._lpp = lpp

        # 缓存命中
        if page_num in self._cache:
            return self._cache[page_num][0]

        # 找到最大的连续缓存页作为起点
        max_cached = max(self._cache.keys()) if self._cache else -1
        if max_cached >= 0:
            _, _, last_line = self._cache[max_cached]
            start_line = last_line
            current_page = max_cached
        else:
            start_line = 0
            current_page = -1

        # 从起点逐行转换到目标页
        return self._convert_to(page_num, cpl, lpp, start_line, current_page)

    def _convert_to(self, target_page: int, cpl: int, lpp: int,
                    start_line: int, current_page: int) -> List[List[str]]:
        """从 start_line 开始逐行转换，直到到达 target_page。"""
        buf: List[str] = []
        line_idx = start_line

        while line_idx < len(self._lines):
            buf.extend(convert_text(self._lines[line_idx], toned=self._toned))
            line_idx += 1

            rows = split_lines(buf, cpl)
            while len(rows) >= lpp:
                page_rows = rows[:lpp]
                current_page += 1
                self._cache[current_page] = (page_rows, start_line, line_idx)

                if current_page == target_page:
                    return page_rows

                # 剩余行放回 buffer
                buf.clear()
                for r in rows[lpp:]:
                    buf.extend(r)
                rows = split_lines(buf, cpl)
                start_line = line_idx

        # 文件结束 — 剩余内容作最后一页
        if buf:
            current_page += 1
            remaining = split_lines(buf, cpl)
            page_rows = remaining[:lpp] if remaining else [[]]
            self._cache[current_page] = (page_rows, start_line, line_idx)
            if current_page == target_page:
                return page_rows

        return [[]]
