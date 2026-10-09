"""ICEB UEB 2024 的精确样例；native 用例必须实际启用 liblouis。

规则原文：https://iceb.org/Rules%20of%20Unified%20English%20Braille%202024.pdf
§§6、7.6、8、10.1、10.2。降级路径只验证其基本映射，不声称 Grade 2。
"""

import pytest

from src.converter import english_conv as en
from src.converter.braille_converter import convert_text


@pytest.fixture
def native_english():
    if not en._check_louis():
        pytest.skip('未启用 liblouis，不能验证 UEB Grade 2')
    return en


@pytest.mark.parametrize('source, expected', [
    ('hello', '⠓⠑⠇⠇⠕'),
    ('the', '⠮'), ('and', '⠯'), ('with', '⠾'),
    ('123', '⠼⠁⠃⠉'),
    ('"hello"', '⠦⠓⠑⠇⠇⠕⠴'),
    ("can't", '⠉⠄⠞'),
    ('HELLO', '⠠⠠⠓⠑⠇⠇⠕'),
    ('Hello world.', '⠠⠓⠑⠇⠇⠕ ⠸⠺⠲'),
])
def test_native_ueb_exact_cells(native_english, source, expected):
    actual = ''.join(native_english.english_to_braille(source)).replace('\u2800', ' ')
    assert actual == expected


@pytest.mark.parametrize('source, expected', [
    ('中文 "hello"', '⠦⠓⠑⠇⠇⠕⠴'),
    ("中文 can't", '⠉⠄⠞'),
])
def test_mixed_text_preserves_english_context(native_english, source, expected):
    assert ''.join(convert_text(source)).endswith(expected)


def test_fallback_is_explicitly_uncontracted(monkeypatch):
    monkeypatch.setattr(en, '_LOUIS_AVAILABLE', False)
    assert ''.join(en.english_to_braille('the')) == '⠞⠓⠑'
    assert ''.join(en.english_to_braille('the')) != '⠮'


def test_native_failure_logs_and_uses_fallback(native_english, monkeypatch, caplog):
    monkeypatch.setattr(en, '_louis_translate_native', lambda text: None)
    assert ''.join(en.english_to_braille('the')) == '⠞⠓⠑'
    assert '降级' in caplog.text
