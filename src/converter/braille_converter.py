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
from typing import List

from src.converter.chinese_conv import chinese_to_braille, is_chinese_char
from src.converter.english_conv import english_to_braille
from src.converter.math_conv import extract_math_segments, latex_to_nemeth

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

# 中文全角标点 → Braille 映射
_CHINESE_PUNCT_TO_BRAILLE = {
    '，': '⠂',   '。': '⠲',   '！': '⠖',
    '？': '⠦',   '：': '⠒',   '；': '⠆',
    '、': '⠐',   '“': '⠦',   '”': '⠴',
    '‘': '⠦',   '’': '⠴',   '（': '⠐⠣',
    '）': '⠐⠜', '【': '⠐⠶', '】': '⠐⠶⠄',
    '《': '⠐⠣', '》': '⠐⠜', '—': '⠐⠤⠐⠤',
    '…': '⠐⠄⠐⠄⠐⠄', '·': '⠐⠄',
}

# 合并所有符号映射（ASCII 符号优先）
_ALL_PUNCT_MAP: dict = {}
_ALL_PUNCT_MAP.update(_CHINESE_PUNCT_TO_BRAILLE)
_ALL_PUNCT_MAP.update(_ASCII_SYMBOL_TO_BRAILLE)

# 正则：识别连续数字
_DIGITS_RE = re.compile(r'(\d+(?:\.\d+)?)')

# Markdown 标记 — 行首清洗
_MD_HEADING_RE = re.compile(r'^#{1,6}\s+')
_MD_LIST_RE = re.compile(r'^[-*+]\s+')
_MD_ORDERED_LIST_RE = re.compile(r'^\d+[.、]\s+')
_MD_BOLD_ITALIC_RE = re.compile(r'\*{1,3}([^*]+)\*{1,3}')
_MD_CODE_RE = re.compile(r'`([^`]+)`')
_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]+\)')


def _emit_braille_number(digits: str) -> List[str]:
    """将连续数字串转为 Braille（一个 ⠼ 后跟每位数字的 Braille 字母）。"""
    result: List[str] = [NUMERIC_INDICATOR]
    for d in digits:
        result.append(_DIGIT_TO_BRAILLE_LETTER.get(d, d))
    return result


def _map_digit_sequences(text: str) -> List[str]:
    """将文本中的连续数字序列替换为 Braille 数字。"""
    # 用正则扫描，数字序列转为 Braille，其他保持原样
    result: List[str] = []
    last_end = 0
    for m in _DIGITS_RE.finditer(text):
        # 数字前的内容
        if m.start() > last_end:
            result.append(text[last_end:m.start()])
        # 数字序列
        result.extend(_emit_braille_number(m.group(1)))
        last_end = m.end()
    # 尾部内容
    if last_end < len(text):
        result.append(text[last_end:])
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
    if '$' in stripped:
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

def _convert_chinese_block(text: str, toned: bool = False) -> List[str]:
    """转换中文块。"""
    text = _strip_markdown(text)
    # 先将数字序列转为 Braille，再送 pypinyin
    digit_mapped = _map_digit_sequences(text)
    # digit_mapped 是 Braille 数字 + 中文文本的混合列表
    # 把中文部分重新拼回字符串
    chinese_parts: List[str] = []
    for part in digit_mapped:
        # 如果以 ⠼ 开头，是 Braille 数字 — 保留
        # 否则是含中文的文本 — 送 pypinyin
        chinese_parts.append(part)
    # 不能简单拼接，因为 Braille 数字是 Braille 字符
    # 更好的方法：分段处理
    result: List[str] = []
    for part in digit_mapped:
        if part.startswith(NUMERIC_INDICATOR):
            # 已经是 Braille 数字，直接加入
            for ch in part:
                result.append(ch)
        else:
            # 含中文的文本
            if any(is_chinese_char(c) for c in part):
                braille = chinese_to_braille(part, toned=toned)
                for ch in braille:
                    # 符号映射
                    mapped = _try_map_symbol(ch)
                    if mapped != ch:
                        for c in mapped:
                            result.append(c)
                    else:
                        result.append(ch)
            else:
                # 纯非中文（空格、符号等）
                for ch in part:
                    mapped = _try_map_symbol(ch)
                    if mapped != ch:
                        for c in mapped:
                            result.append(c)
                    else:
                        result.append(ch)
    return result


def _convert_english_block(text: str) -> List[str]:
    """转换英文块。"""
    text = _strip_markdown(text)
    return english_to_braille(text)


def _convert_math_block(text: str) -> List[str]:
    """转换含数学公式的文本块。

    按 $...$ / $$...$$ 切分：数学段走 latex_to_nemeth，
    非数学段走 _convert_text_segment。
    """
    pattern = re.compile(r'\$\$(.+?)\$\$|\$(.+?)\$', re.DOTALL)
    result: List[str] = []
    last_end = 0

    for m in pattern.finditer(text):
        if m.start() > last_end:
            plain = text[last_end:m.start()]
            result.extend(_convert_text_segment(plain))
        math_expr = m.group(1) or m.group(2)
        nemeth = latex_to_nemeth(math_expr)
        result.append(nemeth)
        last_end = m.end()

    if last_end < len(text):
        plain = text[last_end:]
        result.extend(_convert_text_segment(plain))

    return _flatten(result)


def _convert_text_segment(text: str) -> List[str]:
    """将纯文本段（不含数学标记）转为 Braille 字符列表。"""
    if not text:
        return []

    text = _strip_markdown(text)
    result: List[str] = []
    buffer_ch: List[str] = []     # 中文缓存
    buffer_digits: List[str] = []  # 数字缓存
    i = 0

    while i < len(text):
        ch = text[i]

        # 中文字符 → 入中文缓存
        if is_chinese_char(ch):
            _flush_digits(result, buffer_digits)
            buffer_ch.append(ch)
            i += 1
            continue

        # 数字 → 入数字缓存（等待分组）
        if ch.isascii() and ch.isdigit():
            _flush_chinese(result, buffer_ch)
            buffer_digits.append(ch)
            i += 1
            continue

        # 其他字符
        _flush_chinese(result, buffer_ch)
        _flush_digits(result, buffer_digits)

        # 符号映射
        mapped = _try_map_symbol(ch)
        if mapped != ch:
            for c in mapped:
                result.append(c)
        elif ch.isascii() and ch.isalpha():
            # 英文字母 → english_to_braille
            result.extend(english_to_braille(ch))
        elif ch.isspace():
            result.append(' ')
        else:
            result.append(ch)
        i += 1

    # 刷新缓存
    _flush_chinese(result, buffer_ch)
    _flush_digits(result, buffer_digits)

    return result


def _flush_chinese(result: List[str], buffer: List[str]) -> None:
    """刷新中文缓存。"""
    if buffer:
        braille = chinese_to_braille(''.join(buffer))
        for ch in braille:
            mapped = _try_map_symbol(ch)
            if mapped != ch:
                for c in mapped:
                    result.append(c)
            else:
                result.append(ch)
        buffer.clear()


def _flush_digits(result: List[str], buffer: List[str]) -> None:
    """刷新数字缓存（整组输出，共用一个 ⠼）。"""
    if buffer:
        result.extend(_emit_braille_number(''.join(buffer)))
        buffer.clear()


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


def _convert_mixed_block(text: str, toned: bool = False) -> List[str]:
    """转换中英混合块。"""
    result: List[str] = []
    buffer_ch: List[str] = []
    buffer_en: List[str] = []
    buffer_digits: List[str] = []

    def _flush_all():
        _flush_chinese(result, buffer_ch)
        if buffer_en:
            result.extend(english_to_braille(''.join(buffer_en)))
            buffer_en.clear()
        _flush_digits(result, buffer_digits)

    for ch in text:
        if is_chinese_char(ch):
            _flush_digits(result, buffer_digits)
            if buffer_en:
                result.extend(english_to_braille(''.join(buffer_en)))
                buffer_en.clear()
            buffer_ch.append(ch)
        elif ch.isascii() and ch.isdigit():
            # 数字入数字缓存
            _flush_chinese(result, buffer_ch)
            if buffer_en:
                result.extend(english_to_braille(''.join(buffer_en)))
                buffer_en.clear()
            buffer_digits.append(ch)
        elif ch.isascii() and (ch.isalpha() or ch in '.,!?;:-\'"()[] '):
            # 英文和常见标点
            _flush_chinese(result, buffer_ch)
            _flush_digits(result, buffer_digits)
            buffer_en.append(ch)
        else:
            # 其他符号
            _flush_all()
            mapped = _try_map_symbol(ch)
            if mapped != ch:
                for c in mapped:
                    result.append(c)
            else:
                result.append(ch)

    _flush_all()
    return result


# ── 主入口 ────────────────────────────────────────────────────

def convert_text(text: str, toned: bool = False) -> List[str]:
    """将输入文本转换为 Braille 字符列表。

    Args:
        text: 输入文本（UTF-8）。
        toned: 中文是否输出带调盲文。

    Returns:
        Braille 字符列表。
    """
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
            result.extend(_convert_chinese_block(block_text, toned))
        elif batch_type == BLOCK_ENGLISH:
            result.extend(_convert_english_block(block_text))
        elif batch_type == BLOCK_MATH:
            result.extend(_convert_math_block(block_text))
        elif batch_type == BLOCK_MIXED:
            result.extend(_convert_mixed_block(block_text, toned))
        elif batch_type == BLOCK_OTHER:
            result.extend(block_text)

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

    return result
