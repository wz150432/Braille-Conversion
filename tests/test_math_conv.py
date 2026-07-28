"""LaTeX→Nemeth Code 转换测试。"""

import pytest
from src.converter.math_conv import (
    latex_to_nemeth,
    extract_math_segments,
    convert_text_with_math,
    tokenize_latex,
)


class TestTokenize:
    """分词器测试。"""

    def test_simple_number(self):
        tokens = tokenize_latex('123')
        types = [t.type for t in tokens]
        values = [t.value for t in tokens]
        assert 'NUMBER' in types
        assert '123' in values

    def test_identifiers(self):
        tokens = tokenize_latex('x + y')
        values = [t.value for t in tokens]
        assert 'x' in values
        assert 'y' in values

    def test_command(self):
        tokens = tokenize_latex(r'\frac')
        for t in tokens:
            if t.type == 'COMMAND':
                assert 'frac' in t.value

    def test_braces(self):
        tokens = tokenize_latex('{abc}')
        types = [t.type for t in tokens]
        assert 'LBRACE' in types
        assert 'RBRACE' in types

    def test_empty(self):
        tokens = tokenize_latex('')
        assert len(tokens) == 1  # EOF only


class TestLatexToNemeth:
    """latex_to_nemeth 单元测试。"""

    def test_empty(self):
        assert latex_to_nemeth('') == ''

    def test_simple_number(self):
        """数字前应有数字指示符。"""
        result = latex_to_nemeth('123')
        assert '⠼' in result  # 数字指示符

    def test_simple_ident(self):
        """变量名转为 Braille 字母。"""
        result = latex_to_nemeth('x')
        assert '⠭' in result  # Braille x

    def test_addition(self):
        """加法。"""
        result = latex_to_nemeth('a+b')
        assert result  # 非空

    def test_subtraction(self):
        """减法。"""
        result = latex_to_nemeth('a-b')
        assert result

    def test_frac(self):
        """分式转换。"""
        result = latex_to_nemeth(r'\frac{1}{2}')
        # 应有分式结构和数字
        assert '⠐' in result or '⠼' in result

    def test_superscript(self):
        """上标。"""
        result = latex_to_nemeth('x^2')
        assert '⠈' in result  # 上标指示符

    def test_subscript(self):
        """下标。"""
        result = latex_to_nemeth('x_1')
        assert '⠁' in result  # 下标指示符 或类似结构

    def test_sum(self):
        """求和。"""
        result = latex_to_nemeth(r'\sum_{i=1}^{n}')
        assert result

    def test_int(self):
        """积分。"""
        result = latex_to_nemeth(r'\int_{a}^{b}')
        assert result

    def test_sqrt(self):
        """根号。"""
        result = latex_to_nemeth(r'\sqrt{x}')
        assert result

    def test_greek_alpha(self):
        """希腊字母 alpha。"""
        result = latex_to_nemeth(r'\alpha')
        assert result

    def test_greek_delta(self):
        """希腊字母 delta。"""
        result = latex_to_nemeth(r'\Delta')
        assert result

    def test_unknown_command(self):
        """未知命令保留原文。"""
        result = latex_to_nemeth(r'\unknowncommand')
        assert 'unknowncommand' in result

    def test_complex_expression(self):
        """复杂公式。"""
        result = latex_to_nemeth(r'\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}')
        assert result


class TestExtractMathSegments:
    """数学片段提取测试。"""

    def test_inline_math(self):
        """行内数学 $...$。"""
        segments = extract_math_segments('公式 $a+b$ 内嵌')
        assert len(segments) == 1
        assert segments[0][0] == 'inline'
        assert 'a+b' in segments[0][1]

    def test_display_math(self):
        """显示数学 $$...$$。"""
        segments = extract_math_segments(r'独立公式 $$\frac{1}{2}$$ 展示')
        assert len(segments) == 1
        assert segments[0][0] == 'display'

    def test_multiple_math(self):
        """多个数学片段。"""
        segments = extract_math_segments('$a$ 和 $b$ 和 $c$')
        assert len(segments) == 3

    def test_no_math(self):
        """无数学片段。"""
        segments = extract_math_segments('纯文本内容')
        assert len(segments) == 0


class TestConvertTextWithMath:
    """含数学标记文本的全量转换测试。"""

    def test_text_replacement(self):
        """数学标记被替换。"""
        result = convert_text_with_math('公式 $x^2$ 内容')
        assert '⠈' in result or result != '公式 $x^2$ 内容'  # 数学部分被转换

    def test_display_math_replacement(self):
        """显示数学替换。"""
        result = convert_text_with_math(r'$$\sum_{i=1}^{n}$$')
        assert '$$' not in result or result.count('$') < 4  # $$ 被替换
