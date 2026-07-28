"""
LaTeX 数学表达式 → Nemeth Code 盲文转换模块

支持：
  - 行内 $...$ 和独立 $$...$$ 检测
  - 分式 \\frac{num}{den}
  - 上下标 ^ 和 _
  - 求和 \\sum、积分 \\int、根号 \\sqrt
  - 希腊字母
  - 未知 LaTeX 命令保留原文作 fallback

Nemeth Code 参考：
  - 数字指示符: ⠼ (dots 3-4-5-6)
  - 上标指示符: ⠈ (dot 4)
  - 下标指示符: ⠁ (dot 1)
  - 分式起始: ⠐⠣
  - 分式线:   ⠐⠤
  - 分式结束: ⠐⠜
  - 根号起始: ⠐⠶
  - 根号结束: ⠶⠄
  - 求和:     ⠠⠎
  - 积分:     ⠮ (or more precisely ⠑⠮⠘)
"""

import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ── Nemeth Code 符号映射 ─────────────────────────────────────────

_NEMETH_SYMBOLS = {
    # 运算符
    '+': '⠐⠖',
    '-': '⠐⠤',
    '=': '⠐⠶',
    '<': '⠐⠣',
    '>': '⠐⠜',
    '±': '⠐⠖⠤',
    '×': '⠐⠦',
    '÷': '⠐⠌',
    # 括号
    '(': '⠐⠣',
    ')': '⠐⠜',
    '[': '⠐⠶',
    ']': '⠐⠶⠄',
    '{': '⠐⠷',
    '}': '⠐⠾',
    # Nemeth 特殊
    'NEMETH_FRAC_START': '⠐⠣',
    'NEMETH_FRAC_LINE': '⠐⠤',
    'NEMETH_FRAC_END': '⠐⠜',
    'NEMETH_SUP': '⠈',     # superscript indicator
    'NEMETH_SUB': '⠁',     # subscript indicator
    'NEMETH_NUM': '⠼',     # numeric indicator
    'NEMETH_SQRT_START': '⠐⠶',
    'NEMETH_SQRT_END': '⠶⠄',
}

# ASCII 字母 → Braille 映射（数学模式下标识符应输出 Braille 字母）
_ASCII_TO_BRAILLE = {
    'a': '⠁', 'b': '⠃', 'c': '⠉', 'd': '⠙', 'e': '⠑',
    'f': '⠋', 'g': '⠛', 'h': '⠓', 'i': '⠊', 'j': '⠚',
    'k': '⠅', 'l': '⠇', 'm': '⠍', 'n': '⠝', 'o': '⠕',
    'p': '⠏', 'q': '⠟', 'r': '⠗', 's': '⠎', 't': '⠞',
    'u': '⠥', 'v': '⠧', 'w': '⠺', 'x': '⠭', 'y': '⠽', 'z': '⠵',
    'A': '⠠⠁', 'B': '⠠⠃', 'C': '⠠⠉', 'D': '⠠⠙', 'E': '⠠⠑',
    'F': '⠠⠋', 'G': '⠠⠛', 'H': '⠠⠓', 'I': '⠠⠊', 'J': '⠠⠚',
    'K': '⠠⠅', 'L': '⠠⠇', 'M': '⠠⠍', 'N': '⠠⠝', 'O': '⠠⠕',
    'P': '⠠⠏', 'Q': '⠠⠟', 'R': '⠠⠗', 'S': '⠠⠎', 'T': '⠠⠞',
    'U': '⠠⠥', 'V': '⠠⠧', 'W': '⠠⠺', 'X': '⠠⠭', 'Y': '⠠⠽', 'Z': '⠠⠵',
}

# ASCII 数字 → Braille 数字映射（在 Nemeth 中数字 = 数字指示符 ⠼ + a-j）
_DIGIT_TO_BRAILLE = {
    '0': '⠚', '1': '⠁', '2': '⠃', '3': '⠉', '4': '⠙',
    '5': '⠑', '6': '⠋', '7': '⠛', '8': '⠓', '9': '⠊',
}

# 希腊字母到 Nemeth Code 的映射
_GREEK_LOWER = {
    'alpha': '⠁', 'beta': '⠃', 'gamma': '⠛', 'delta': '⠙',
    'epsilon': '⠑', 'zeta': '⠵', 'eta': '⠱', 'theta': '⠹',
    'iota': '⠊', 'kappa': '⠅', 'lambda': '⠇', 'mu': '⠍',
    'nu': '⠝', 'xi': '⠭', 'omicron': '⠕', 'pi': '⠏',
    'rho': '⠗', 'sigma': '⠎', 'tau': '⠞', 'upsilon': '⠥',
    'phi': '⠋', 'chi': '⠓', 'psi': '⠟', 'omega': '⠺',
}

_GREEK_UPPER = {
    'Alpha': '⠠⠁', 'Beta': '⠠⠃', 'Gamma': '⠠⠛', 'Delta': '⠠⠙',
    'Epsilon': '⠠⠑', 'Zeta': '⠠⠵', 'Eta': '⠠⠱', 'Theta': '⠠⠹',
    'Iota': '⠠⠊', 'Kappa': '⠠⠅', 'Lambda': '⠠⠇', 'Mu': '⠠⠍',
    'Nu': '⠠⠝', 'Xi': '⠠⠭', 'Omicron': '⠠⠕', 'Pi': '⠠⠏',
    'Rho': '⠠⠗', 'Sigma': '⠠⠎', 'Tau': '⠠⠞', 'Upsilon': '⠠⠥',
    'Phi': '⠠⠋', 'Chi': '⠠⠓', 'Psi': '⠠⠟', 'Omega': '⠠⠺',
}

# Nemeth 特殊命令映射
_NEMETH_COMMANDS = {
    'sum': '⠠⠎',
    'prod': '⠏⠗',
    'int': '⠮',
    'iint': '⠮⠮',
    'iiint': '⠮⠮⠮',
    'oint': '⠮⠕',
    'infty': '⠈⠾',
    'partial': '⠏⠙',
    'nabla': '⠠⠝',
    'forall': '⠐⠧',
    'exists': '⠐⠑',
    'emptyset': '⠐⠕',
    'subset': '⠐⠣',
    'supset': '⠐⠜',
    'cup': '⠠⠥',
    'cap': '⠠⠉',
    'rightarrow': '⠐⠒⠒',
    'leftarrow': '⠐⠂⠂',
    'Rightarrow': '⠐⠶⠶',
    'Leftarrow': '⠐⠶⠂',
    'cdot': '⠐⠄',
    'cdots': '⠐⠄⠐⠄⠐⠄',
    'ldots': '⠐⠄⠐⠄⠐⠄',
    'times': '⠐⠦',
    'div': '⠐⠌',
    'pm': '⠐⠖⠤',
    'mp': '⠐⠤⠖',
    'neq': '⠐⠶⠤',
    'leq': '⠐⠣⠤',
    'geq': '⠐⠜⠤',
    'approx': '⠐⠶⠶',
    'equiv': '⠐⠶⠤',
    'sin': '⠎⠊⠝',
    'cos': '⠉⠕⠎',
    'tan': '⠞⠁⠝',
    'log': '⠇⠕⠛',
    'ln': '⠇⠝',
    'lim': '⠇⠊⠍',
    'to': '⠐⠒',
}

# ── LaTeX 解析器 ─────────────────────────────────────────────────


class Token:
    """LaTeX 数学表达式的一个词法单元。"""
    __slots__ = ('type', 'value')

    # 类型常量
    NUMBER = 'NUMBER'
    IDENT = 'IDENT'        # 标识符（变量名、命令名）
    COMMAND = 'COMMAND'    # LaTeX 命令如 \frac
    SYMBOL = 'SYMBOL'      # 运算符 + - = ( ) [ ] { } ^ _
    LBRACE = 'LBRACE'      # {
    RBRACE = 'RBRACE'      # }
    CARET = 'CARET'        # ^
    UNDERSCORE = 'UNDERSCORE'  # _
    BACKSLASH = 'BACKSLASH'    # \
    DOLLAR = 'DOLLAR'      # $
    TEXT = 'TEXT'          # 普通文本
    EOF = 'EOF'

    def __init__(self, type_: str, value: str = ''):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f'Token({self.type}, {self.value!r})'


def tokenize_latex(s: str) -> List[Token]:
    """将 LaTeX 字符串分词为 Token 列表。"""
    tokens = []
    i = 0
    n = len(s)

    while i < n:
        ch = s[i]

        # 空格 → 跳过（LaTeX 数学模式下空格被忽略）
        if ch in ' \t\n\r':
            i += 1
            continue

        # 注释 %
        if ch == '%':
            i += 1
            while i < n and s[i] != '\n':
                i += 1
            continue

        # 命令 \command
        if ch == '\\':
            i += 1
            # 特殊符号 \ 后跟单个非字母字符
            if i < n and not s[i].isalpha():
                tokens.append(Token(Token.COMMAND, ch + s[i]))
                i += 1
                continue
            # 命令名（字母序列）
            start = i
            while i < n and s[i].isalpha():
                i += 1
            cmd_name = s[start:i]
            tokens.append(Token(Token.COMMAND, '\\' + cmd_name))
            continue

        # 花括号
        if ch == '{':
            tokens.append(Token(Token.LBRACE, '{'))
            i += 1
            continue
        if ch == '}':
            tokens.append(Token(Token.RBRACE, '}'))
            i += 1
            continue

        # 上下标
        if ch == '^':
            tokens.append(Token(Token.CARET, '^'))
            i += 1
            continue
        if ch == '_':
            tokens.append(Token(Token.UNDERSCORE, '_'))
            i += 1
            continue

        # 数字
        if ch.isdigit() or (ch == '.' and i + 1 < n and s[i + 1].isdigit()):
            start = i
            # 允许小数点
            dot_seen = ch == '.'
            i += 1
            while i < n and (s[i].isdigit() or (s[i] == '.' and not dot_seen)):
                if s[i] == '.':
                    dot_seen = True
                i += 1
            tokens.append(Token(Token.NUMBER, s[start:i]))
            continue

        # 字母标识符（变量名如 x, y, sin 等由命令处理）
        if ch.isalpha():
            start = i
            while i < n and s[i].isalpha():
                i += 1
            tokens.append(Token(Token.IDENT, s[start:i]))
            continue

        # 符号
        tokens.append(Token(Token.SYMBOL, ch))
        i += 1

    tokens.append(Token(Token.EOF, ''))
    return tokens


class NemethConverter:
    """LaTeX → Nemeth Code 转换器（递归下降）。"""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, *types: str) -> Token:
        tok = self.peek()
        if tok.type in types:
            return self.advance()
        raise ValueError(f'期望 {types}，得到 {tok.type}({tok.value!r}) 在位置 {self.pos}')

    def convert(self) -> str:
        """转换整个表达式。"""
        parts = []
        while self.peek().type != Token.EOF:
            parts.append(self._parse_expr())
        return ''.join(parts)

    def _parse_expr(self) -> str:
        """解析一个表达式或子表达式。"""
        tok = self.peek()

        if tok.type == Token.LBRACE:
            return self._parse_braced_group()

        if tok.type == Token.COMMAND:
            return self._parse_command()

        if tok.type == Token.CARET:
            return self._parse_superscript()

        if tok.type == Token.UNDERSCORE:
            return self._parse_subscript()

        if tok.type == Token.NUMBER:
            return self._parse_number()

        if tok.type == Token.IDENT:
            return self._parse_ident()

        if tok.type == Token.SYMBOL:
            self.advance()  # 必须消费 token！
            ch = tok.value
            if ch in _NEMETH_SYMBOLS:
                return _NEMETH_SYMBOLS[ch]
            else:
                return ch

        # 未知类型跳过
        return self.advance().value

    def _parse_braced_group(self) -> str:
        """解析 { ... } 分组，返回 Nemeth 结果。"""
        self.expect(Token.LBRACE)
        parts = []
        depth = 1
        while self.peek().type != Token.EOF and depth > 0:
            tok = self.peek()
            if tok.type == Token.LBRACE:
                depth += 1
                parts.append(self.advance().value)
            elif tok.type == Token.RBRACE:
                depth -= 1
                if depth == 0:
                    self.advance()  # consume RBRACE
                    break
                else:
                    parts.append(self.advance().value)
            else:
                parts.append(self._parse_expr())
        return ''.join(parts)

    def _parse_command(self) -> str:
        """解析 LaTeX 命令。"""
        tok = self.advance()
        cmd = tok.value  # 格式: \name

        # 分式 \frac{a}{b}
        if cmd == '\\frac':
            num = self._parse_braced_group()
            # 分式线
            den = self._parse_braced_group()
            return (_NEMETH_SYMBOLS['NEMETH_FRAC_START'] + num +
                    _NEMETH_SYMBOLS['NEMETH_FRAC_LINE'] + den +
                    _NEMETH_SYMBOLS['NEMETH_FRAC_END'])

        # 根号 \sqrt 或 \sqrt[n]{x}
        if cmd == '\\sqrt':
            tok2 = self.peek()
            if tok2.type == Token.SYMBOL and tok2.value == '[':
                # \sqrt[n]{x} — n 次根
                self.advance()  # consume [
                n = self._parse_until(']')
                self.advance()  # consume ]
                radicand = self._parse_braced_group()
                return (_NEMETH_SYMBOLS['NEMETH_SQRT_START'] +
                        n + _NEMETH_SYMBOLS['NEMETH_SUP'] + radicand +
                        _NEMETH_SYMBOLS['NEMETH_SQRT_END'])
            else:
                radicand = self._parse_braced_group()
                return (_NEMETH_SYMBOLS['NEMETH_SQRT_START'] +
                        radicand +
                        _NEMETH_SYMBOLS['NEMETH_SQRT_END'])

        # 上下标跟在命令后（如 \sum_{i=1}^{n}）
        if cmd in ('\\sum', '\\prod', '\\int', '\\iint', '\\iiint', '\\oint',
                   '\\lim', '\\limsup', '\\liminf'):
            nemeth = _NEMETH_COMMANDS.get(cmd[1:], '⠿')
            # 检查是否有下标/上标
            parts = [nemeth]
            while self.peek().type in (Token.UNDERSCORE, Token.CARET):
                parts.append(self._parse_expr())
            return ''.join(parts)

        # 希腊字母
        greek_name = cmd[1:]  # 去掉反斜杠
        if greek_name in _GREEK_LOWER:
            return _GREEK_LOWER[greek_name]
        if greek_name in _GREEK_UPPER:
            return _GREEK_UPPER[greek_name]

        # Nemeth 命令
        if cmd[1:] in _NEMETH_COMMANDS:
            return _NEMETH_COMMANDS[cmd[1:]]

        # 未知命令：保留原文作为 fallback
        logger.debug("未知 LaTeX 命令: %s，保留原文", cmd)
        return cmd

    def _parse_superscript(self) -> str:
        """解析上标 ^..."""
        self.advance()  # consume ^
        sub = self._parse_single_or_group()
        return _NEMETH_SYMBOLS['NEMETH_SUP'] + sub

    def _parse_subscript(self) -> str:
        """解析下标 _..."""
        self.advance()  # consume _
        sub = self._parse_single_or_group()
        return _NEMETH_SYMBOLS['NEMETH_SUB'] + sub

    def _parse_single_or_group(self) -> str:
        """解析单个字符或花括号分组。"""
        tok = self.peek()
        if tok.type == Token.LBRACE:
            return self._parse_braced_group()
        return self._parse_expr()

    def _parse_number(self) -> str:
        """解析数字（带数字指示符 ⠼，后面跟 Braille 数字 a-j）。"""
        num = self.advance().value
        # 每个 ASCII 数字转为 Braille 数字
        braille_digits = ''.join(_DIGIT_TO_BRAILLE.get(ch, ch) for ch in num)
        return _NEMETH_SYMBOLS['NEMETH_NUM'] + braille_digits

    def _parse_ident(self) -> str:
        """解析字母标识符（转为 Braille 字母）。"""
        ident = self.advance().value
        # 逐个字母转 Braille，不认识的保持原样
        return ''.join(_ASCII_TO_BRAILLE.get(ch, ch) for ch in ident)

    def _parse_until(self, stop_char: str) -> str:
        """解析直到遇到指定字符（用于 [...] 内）。"""
        parts = []
        while self.peek().type != Token.EOF:
            tok = self.peek()
            if tok.type == Token.SYMBOL and tok.value == stop_char:
                break
            parts.append(self._parse_expr())
        return ''.join(parts)


# ── 公开 API ──────────────────────────────────────────────────────

_INLINE_MATH_RE = re.compile(r'\$([^$]+)\$')
_DISPLAY_MATH_RE = re.compile(r'\$\$([^$]+)\$\$')


def extract_math_segments(text: str) -> List[Tuple[str, str]]:
    """从文本中提取所有数学片段。

    Args:
        text: 含 LaTeX 数学的原始文本。

    Returns:
        List[(type, expr)]:
          type = 'inline' ($...$) 或 'display' ($$...$$)
          expr = 去掉分隔符后的 LaTeX 表达式
        按在原文中出现顺序返回。
    """
    segments: List[Tuple[str, str]] = []
    pos = 0
    # 先匹配 $$（优先级高），再匹配 $
    combined = re.finditer(
        r'\$\$(.+?)\$\$|\$(.+?)\$',
        text,
        re.DOTALL
    )
    for m in combined:
        if m.group(1) is not None:
            segments.append(('display', m.group(1)))
        else:
            segments.append(('inline', m.group(2)))
    return segments


def latex_to_nemeth(latex_str: str) -> str:
    """将 LaTeX 数学表达式转换为 Nemeth Code 盲文字符串。

    Args:
        latex_str: LaTeX 数学表达式（不含 $ 分隔符）。

    Returns:
        Nemeth Code 盲文字符串。
    """
    if not latex_str:
        return ''

    try:
        tokens = tokenize_latex(latex_str)
        converter = NemethConverter(tokens)
        return converter.convert()
    except Exception as e:
        logger.error("LaTeX→Nemeth 转换失败: %s, 输入: %r", e, latex_str)
        # 降级：保留原文
        return latex_str


def inline_to_nemeth(latex_inline: str) -> str:
    """转换行内数学 $...$ 片段（包含检测 $ 边界）。"""
    return latex_to_nemeth(latex_inline)


def convert_text_with_math(text: str) -> str:
    """将文本中的 $...$ / $$...$$ 数学片段替换为 Nemeth Code。

    Args:
        text: 含 $...$ 数学标记的完整文本。

    Returns:
        数学片段被替换后的文本。
    """
    result = text

    # 先替换 $$...$$ (显示数学)
    result = re.sub(
        r'\$\$(.+?)\$\$',
        lambda m: latex_to_nemeth(m.group(1)),
        result,
        flags=re.DOTALL
    )

    # 再替换 $...$ (行内数学)
    result = re.sub(
        r'\$(.+?)\$',
        lambda m: latex_to_nemeth(m.group(1)),
        result
    )

    return result
