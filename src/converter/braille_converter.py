"""
中文/英文/数学 Braille 转换总调度器

按行扫描输入文本，自动识别内容类型并分流到对应的转换模块：
  - 中文 → chinese_conv
  - 英文 → english_conv
  - LaTeX 数学 → math_conv

数学优先级最高，同类型连续块合并为批次转换。
"""

import re
import logging
from typing import List, Optional

from src.converter.chinese_conv import chinese_to_braille, is_chinese_char
from src.converter.chinese_rules import ChineseBrailleMode, CHINESE_PUNCTUATION, resolve_mode
from src.converter.english_conv import english_to_braille
from src.converter.math_conv import find_math_segments, nemeth_passage, needs_space_after_math

logger = logging.getLogger(__name__)

# ── 字符到 Braille 的映射 ─────────────────────────────────────

# 数字 → Braille 字母（不加 ⠼ 前缀，多个数字共享一个 ⠼）
_DIGIT_TO_BRAILLE_LETTER = {
    '0': '⠚', '1': '⠁', '2': '⠃', '3': '⠉', '4': '⠙',
    '5': '⠑', '6': '⠋', '7': '⠛', '8': '⠓', '9': '⠊',
}
NUMERIC_INDICATOR = '⠼'  # 数字指示符，放在一组数字前

# ASCII 符号 → Braille 映射
_ASCII_SYMBOL_TO_BRAILLE = {
    '$': '⠈⠎',   '%': '⠼⠉',   '°': '⠐⠴',
    '@': '⠈⠁',   '&': '⠈⠯',   '*': '⠐⠔',
    '#': '⠼⠼',   '~': '⠈⠔',   '^': '⠈',
    '_': '⠐⠤',   '|': '⠐⠶',   '\\': '⠐⠌',
    '<': '⠐⠣',   '>': '⠐⠜',   '+': '⠐⠖',
    '-': '⠐⠤',   '=': '⠐⠶',   '/': '⠐⠌',
    '.': '⠲',     ',': '⠂',     '?': '⠦',
    '!': '⠖',     ':': '⠒',     ';': '⠆',
    '"': '⠦',     "'": '⠄',     '(': '⠐⠣',
    ')': '⠐⠜',   '[': '⠐⠶',   ']': '⠐⠶⠄',
    '{': '⠐⠷',   '}': '⠐⠾',
}

# GF 0019—2018 §8，中文标点与 UEB 英文标点分别处理。
_CHINESE_PUNCT_TO_BRAILLE = CHINESE_PUNCTUATION

# 合并所有符号映射（ASCII 符号优先）
_ALL_PUNCT_MAP: dict = {}
_ALL_PUNCT_MAP.update(_CHINESE_PUNCT_TO_BRAILLE)
_ALL_PUNCT_MAP.update(_ASCII_SYMBOL_TO_BRAILLE)

# 正文只实现 GF 0019 附录 B 的整数；识别小数以避免误转为中文句号。
_NUMBER_RE = re.compile(r'[0-9]+(?:\.[0-9]+)?')
_ENGLISH_PUNCT = frozenset('.,!?;:-\'"()[] \t')

# Markdown 标记 — 行首清洗
_MD_HEADING_RE = re.compile(r'^#{1,6}\s+')
_MD_LIST_RE = re.compile(r'^[-*+]\s+')
_MD_ORDERED_LIST_RE = re.compile(r'^\d+[.、]\s+')
_MD_BOLD_ITALIC_RE = re.compile(r'\*{1,3}([^*]+)\*{1,3}')
_MD_CODE_RE = re.compile(r'`([^`]+)`')
_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]+\)')
_TEX_MATH_START_RE = re.compile(
    r'\\\(|\\\[|'
    r'\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}'
)


def _emit_braille_number(digits: str) -> List[str]:
    """附录 B 的数字；未实现的正文小数点显式占位，不冒充句号。"""
    result: List[str] = [NUMERIC_INDICATOR]
    if '.' in digits:
        logger.warning('正文小数点尚未实现中国盲文数学规则，使用占位符')
    for d in digits:
        result.append(_DIGIT_TO_BRAILLE_LETTER.get(d, '⠿'))
    return result


def _strip_markdown(text: str) -> str:
    """清洗 Markdown 语法标记，保留纯文本。"""
    text = _MD_HEADING_RE.sub('', text)
    text = _MD_LIST_RE.sub('', text)
    text = _MD_ORDERED_LIST_RE.sub('', text)
    text = _MD_BOLD_ITALIC_RE.sub(r'\1', text)
    text = _MD_CODE_RE.sub(r'\1', text)
    text = _MD_LINK_RE.sub(r'\1', text)
    # 逐行清洗行首标记（多行场景）
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        line = _MD_HEADING_RE.sub('', line)
        line = _MD_LIST_RE.sub('', line)
        line = _MD_ORDERED_LIST_RE.sub('', line)
        cleaned.append(line)
    return '\n'.join(cleaned)


def _try_map_symbol(ch: str) -> str:
    """尝试将单个字符映射为 Braille，无映射则返回原字符。"""
    return _ALL_PUNCT_MAP.get(ch, ch)


# ── 内容块类型 ────────────────────────────────────────────────

BLOCK_CHINESE = 'chinese'
BLOCK_ENGLISH = 'english'
BLOCK_MATH = 'math'
BLOCK_MIXED = 'mixed'
BLOCK_EMPTY = 'empty'
BLOCK_OTHER = 'other'

BRAILLE_SPACE = ' '  # 空格保持为普通空格
PLACEHOLDER = '⠿'


def _classify_line(line: str) -> str:
    """判断一行文本的内容类型。"""
    stripped = line.strip()
    if not stripped:
        return BLOCK_EMPTY
    if '$' in stripped or _TEX_MATH_START_RE.search(stripped):
        return BLOCK_MATH
    chinese_count = sum(1 for ch in stripped if is_chinese_char(ch))
    english_count = sum(1 for ch in stripped if ch.isascii() and ch.isalpha())
    if chinese_count > 0 and english_count == 0:
        return BLOCK_CHINESE
    elif english_count > 0 and chinese_count == 0:
        return BLOCK_ENGLISH
    elif chinese_count > 0 and english_count > 0:
        return BLOCK_MIXED
    else:
        return BLOCK_OTHER


# ── 各类型转换器 ──────────────────────────────────────────────

def _convert_chinese_block(text: str, mode: ChineseBrailleMode) -> List[str]:
    """中文、数字和标点采用同一条转写路径。"""
    return _convert_text_segment(_strip_markdown(text), mode)


def _convert_english_block(text: str) -> List[str]:
    """转换英文块。"""
    text = _strip_markdown(text)
    return english_to_braille(text)


def _convert_math_block(text: str, mode: ChineseBrailleMode) -> List[str]:
    """转换含数学公式的文本块。

    按常见 LaTeX 数学定界符切分：数学段走带切换符的 nemeth_passage，
    非数学段走 _convert_text_segment。
    """
    result: List[str] = []
    last_end = 0

    for start, end, kind, math_expr in find_math_segments(text):
        if start > last_end:
            plain = text[last_end:start]
            result.extend(_convert_text_segment(plain, mode))
        nemeth = nemeth_passage(math_expr, display=kind == 'display')
        if start > 0 and not text[start - 1].isspace():
            result.append(' ')
        result.append(nemeth)
        if needs_space_after_math(text, end):
            result.append(' ')
        last_end = end

    if last_end < len(text):
        plain = text[last_end:]
        result.extend(_convert_text_segment(plain, mode))

    return _flatten(result)


def _convert_text_segment(text: str,
                          mode: ChineseBrailleMode = ChineseBrailleMode.STANDARD) -> List[str]:
    """扫描连续中文/英文/数字段；中文标点按最长符号匹配，模式全程传递。"""
    text = _strip_markdown(text)
    result: List[str] = []
    chinese_context = any(is_chinese_char(ch) for ch in text)
    ascii_chinese_punct = {',': '，', '.': '。', '?': '？', '!': '！',
                           ':': '：', ';': '；', '(': '（', ')': '）'}
    index = 0
    previous_kind = None

    def emit(chars, kind):
        nonlocal previous_kind
        if (result and result[-1] != ' ' and previous_kind in ('chinese', 'english', 'number')
                and kind in ('chinese', 'english', 'number') and previous_kind != kind):
            result.append(' ')
        result.extend(chars)
        previous_kind = kind

    while index < len(text):
        char = text[index]
        # UEB 的引号、撇号和缩写需要整个英文片段的上下文。
        # 纯中文段中的 ASCII 标点仍按中文标点处理。
        if char.isascii() and (char.isalpha() or char in '\'"(['):
            end = index + 1
            while end < len(text) and text[end].isascii() and (
                    text[end].isalnum() or text[end] in _ENGLISH_PUNCT):
                end += 1
            span = text[index:end]
            if any(c.isascii() and c.isalpha() for c in span):
                emit(english_to_braille(span), 'english')
                index = end
                continue
        if is_chinese_char(char):
            end = index + 1
            while end < len(text) and is_chinese_char(text[end]):
                end += 1
            emit(chinese_to_braille(text[index:end], mode=mode), 'chinese')
            index = end
        elif char.isascii() and char.isdigit():
            end = _NUMBER_RE.match(text, index).end()
            emit(_emit_braille_number(text[index:end]), 'number')
            index = end
        else:
            pair = text[index:index + 2]
            symbol = pair if pair in CHINESE_PUNCTUATION else char
            if symbol in CHINESE_PUNCTUATION:
                result.extend(CHINESE_PUNCTUATION[symbol])
            elif chinese_context and char in ascii_chinese_punct:
                result.extend(CHINESE_PUNCTUATION[ascii_chinese_punct[char]])
            else:
                result.extend(_try_map_symbol(char))
            previous_kind = None
            index += len(symbol)
    return result


def _flatten(items: list) -> list:
    """展平嵌套列表和字符串，确保每个元素是单个字符。"""
    flat = []
    for item in items:
        if isinstance(item, str):
            for ch in item:
                flat.append(ch)
        elif isinstance(item, list):
            flat.extend(_flatten(item))
        else:
            flat.append(item)
    return flat


def _convert_mixed_block(text: str, mode: ChineseBrailleMode) -> List[str]:
    """中英混合与纯中文共用模式和标点规则。"""
    return _convert_text_segment(text, mode)


# ── 主入口 ────────────────────────────────────────────────────

def convert_text(text: str, toned: Optional[bool] = None, *,
                 mode: Optional[ChineseBrailleMode] = None) -> List[str]:
    """将输入文本转换为 Braille 字符列表。

    Args:
        text: 输入文本（UTF-8）。
        toned: 兼容参数，True→full，False→standard。
        mode: 中文转写模式，默认国家通用盲文 standard。

    Returns:
        Braille 字符列表。
    """
    resolved = resolve_mode(toned, mode)
    if not text:
        return []

    lines = text.split('\n')
    result: List[str] = []
    batch_type: str = ''
    batch_lines: List[str] = []

    def flush_batch():
        nonlocal batch_type, batch_lines
        if not batch_lines:
            return
        block_text = '\n'.join(batch_lines)

        if batch_type == BLOCK_CHINESE:
            result.extend(_convert_chinese_block(block_text, resolved))
        elif batch_type == BLOCK_ENGLISH:
            result.extend(_convert_english_block(block_text))
        elif batch_type == BLOCK_MATH:
            result.extend(_convert_math_block(block_text, resolved))
        elif batch_type == BLOCK_MIXED:
            result.extend(_convert_mixed_block(block_text, resolved))
        elif batch_type == BLOCK_OTHER:
            result.extend(_convert_text_segment(block_text, resolved))

        result.append(BRAILLE_SPACE)
        batch_lines = []
        batch_type = ''

    for line in lines:
        line_type = _classify_line(line)
        if not batch_type:
            batch_type = line_type
            batch_lines.append(line)
        elif batch_type == line_type:
            batch_lines.append(line)
        else:
            flush_batch()
            batch_type = line_type
            batch_lines.append(line)

    flush_batch()
    while result and result[-1] == BRAILLE_SPACE:
        result.pop()

    # 最终出口统一保证：除空白外，所有字符都是 Unicode 盲文。
    return [
        ch if ch.isspace() or ('\u2800' <= ch <= '\u28ff') else PLACEHOLDER
        for ch in result
    ]
