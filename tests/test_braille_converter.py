"""总调度器集成测试。"""

import pytest
from src.converter.braille_converter import convert_text


class TestBrailleConverter:
    """convert_text 集成测试。"""

    def test_empty(self):
        """空文本。"""
        assert convert_text('') == []

    def test_chinese_only(self):
        """纯中文。"""
        result = convert_text('你好世界')
        assert len(result) >= 4  # 至少四个 Braille 字符
        for ch in result:
            # 中文转 Braille 后应在 Braille Unicode 范围或为空格
            code = ord(ch)
            assert 0x2800 <= code <= 0x28FF or ch == ' ', f"U+{code:04X} 不在 Braille 范围"

    def test_english_only(self):
        """纯英文。"""
        result = convert_text('Hello world')
        assert len(result) >= 1

    def test_chinese_and_english(self):
        """中英混合。"""
        result = convert_text('Hello世界')
        assert len(result) >= 2

    def test_with_math_inline(self):
        """含行内数学。"""
        result = convert_text('公式 $x^2$ 测试')
        assert len(result) >= 3

    def test_with_math_display(self):
        """含显示数学。"""
        result = convert_text(r'公式 $$\frac{1}{2}$$ 测试')
        assert len(result) >= 3

    def test_newlines(self):
        """含换行符。"""
        result = convert_text('第一行\n第二行')
        assert len(result) >= 4

    def test_mixed_complex(self):
        """复杂的混合内容。"""
        text = """# 标题
这是一个测试
Hello world! 你好
公式 $E=mc^2$
结束"""
        result = convert_text(text)
        assert len(result) > 0

    def test_toned_mode(self):
        """带调模式。"""
        result_toned = convert_text('中国', toned=True)
        result_untoned = convert_text('中国', toned=False)
        # 两者都是有效 Braille
        for ch in result_toned:
            assert 0x2800 <= ord(ch) <= 0x28FF or ch == ' '
        for ch in result_untoned:
            assert 0x2800 <= ord(ch) <= 0x28FF or ch == ' '

    def test_numbers_only(self):
        """纯数字。"""
        result = convert_text('12345')
        # 数字会被原样保留或映射
        assert len(result) == 5

    def test_special_chars(self):
        """特殊字符。"""
        result = convert_text('@#$%^&*()')
        assert len(result) >= 1

    def test_long_text(self):
        """长文本性能测试。"""
        text = '你好世界 ' * 100
        result = convert_text(text)
        assert len(result) > 0

    def test_mixed_encoding_safety(self):
        """混合编码安全性。"""
        text = '中文 English 123 $x+y$'
        result = convert_text(text)
        assert len(result) > 0
