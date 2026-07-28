"""中文→盲文转换测试。"""

import pytest
from src.converter.chinese_conv import chinese_to_braille, is_chinese_char


class TestChineseToBraille:
    """chinese_to_braille 单元测试。"""

    def test_empty_string(self):
        """空字符串应返回空列表。"""
        assert chinese_to_braille('') == []

    def test_simple_chinese(self):
        """简单中文字符转换。"""
        result = chinese_to_braille('你好')
        # 每个汉字对应 1-2 个 Braille 点阵字符（声母+韵母）
        assert len(result) >= 2
        # pypinyin 返回 Braille 字符，确认是 Braille Unicode 范围
        for ch in result:
            code = ord(ch)
            assert 0x2800 <= code <= 0x28FF, f"{ch} (U+{code:04X}) 不是 Braille 字符"

    def test_with_punctuation(self):
        """标点符号保持原样或转为对应 Braille。"""
        result = chinese_to_braille('你好！')
        assert len(result) >= 2  # 至少两个汉字

    def test_mixed_chinese_ascii(self):
        """中英混合输入。"""
        result = chinese_to_braille('Hello世界')
        # "Hello" 保持原样，"世界" 转 Braille
        assert len(result) >= 2

    def test_toned_false(self):
        """无调模式。"""
        toned = chinese_to_braille('中国', toned=True)
        untoned = chinese_to_braille('中国', toned=False)
        # 两者都是有效的 Braille 字符列表
        for ch in toned:
            assert 0x2800 <= ord(ch) <= 0x28FF
        for ch in untoned:
            assert 0x2800 <= ord(ch) <= 0x28FF

    def test_all_non_chinese(self):
        """纯非中文输入保持原样。"""
        result = chinese_to_braille('abc 123!')
        assert len(result) > 0

    def test_newline(self):
        """换行符处理。"""
        result = chinese_to_braille('你好\n世界')
        assert len(result) >= 4  # 至少四个字符


class TestIsChineseChar:
    """is_chinese_char 单元测试。"""

    def test_chinese_chars(self):
        """标准中文字符应返回 True。"""
        assert is_chinese_char('你')
        assert is_chinese_char('我')
        assert is_chinese_char('中')
        assert is_chinese_char('国')

    def test_non_chinese(self):
        """非中文字符应返回 False。"""
        assert not is_chinese_char('a')
        assert not is_chinese_char('1')
        assert not is_chinese_char('.')
        assert not is_chinese_char(' ')

    def test_empty_string(self):
        """空字符串应返回 False。"""
        assert not is_chinese_char('')
        assert not is_chinese_char('ab')
