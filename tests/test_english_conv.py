"""英文→盲文 Grade 2 转换测试。"""

import pytest
from src.converter.english_conv import english_to_braille, _FALLBACK_MAP


class TestEnglishToBraille:
    """english_to_braille 单元测试。"""

    def test_empty_string(self):
        """空字符串应返回空列表。"""
        assert english_to_braille('') == []

    def test_simple_letter_fallback(self):
        """基本字母映射测试（通过降级路径）。"""
        # 所有 Braille 字符在 U+2800-U+28FF 范围
        result = english_to_braille('a')
        assert len(result) == 1
        code = ord(result[0])
        assert 0x2800 <= code <= 0x28FF, f"U+{code:04X} 不是 Braille 字符"

    def test_word(self):
        """短词转换。"""
        result = english_to_braille('hello')
        assert len(result) >= 1

    def test_sentence(self):
        """句子转换。"""
        result = english_to_braille('Hello world.')
        assert len(result) >= 1

    def test_with_numbers(self):
        """含数字的文本。"""
        result = english_to_braille('Test 123')
        assert len(result) >= 1

    def test_all_caps(self):
        """全大写。"""
        result = english_to_braille('HELLO')
        assert len(result) >= 1

    def test_punctuation(self):
        """标点符号。"""
        result = english_to_braille('Hello, world!')
        assert len(result) >= 1

    def test_special_chars(self):
        """特殊字符。"""
        result = english_to_braille('@#$%')
        # 未知字符替换为占位符
        assert len(result) >= 1


class TestFallbackMap:
    """降级映射测试。"""

    @pytest.mark.parametrize("char,expected_prefix", [
        ('a', '⠀'), ('z', '⠀'),
        ('A', '⠀'), ('Z', '⠀'),
        ('0', '⠀'), ('9', '⠀'),
    ])
    def test_fallback_chars_in_braille_range(self, char, expected_prefix):
        """所有降级映射的输出应在 Braille Unicode 范围。"""
        result = _FALLBACK_MAP.get(char, '⠿')
        code = ord(result[0]) if result else 0
        assert 0x2800 <= code <= 0x28FF, f"{char!r} → U+{code:04X} 不在 Braille 范围"

    def test_fallback_space(self):
        """空格映射。"""
        assert _FALLBACK_MAP.get(' ') == ' '
