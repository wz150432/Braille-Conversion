"""Exact fixtures from BANA Nemeth 2022, plus TeX parsing regressions.

Expected cells are independent literals; clauses refer to the official code.
"""

import pytest

from src.converter.math_conv import latex_to_nemeth, convert_text_with_math
from src.converter.braille_converter import convert_text


@pytest.mark.parametrize('source, expected, rule', [
    ('1+2', '⠼⠂⠬⠆', '3.3, 3.4, 20'),
    ('0123456789', '⠼⠴⠂⠆⠒⠲⠢⠖⠶⠦⠔', '3.1.2'),
    ('3.14', '⠼⠒⠨⠂⠲', '3-6'),
    ('.35', '⠼⠨⠒⠢', '3-5'),
    ('-1', '⠤⠼⠂', '3-11'),
    ('+3', '⠬⠒', '3-13'),
    ('x-5', '⠭⠤⠢', '3-53'),
    ('x5', '⠭⠐⠢', '24-1'),
    ('x.6', '⠭⠐⠨⠖', '24-2'),
    ('a+b', '⠁⠬⠃', '20'),
    ('a-b', '⠁⠤⠃', '20'),
    ('x=y', '⠭ ⠨⠅ ⠽', '21-26'),
    ('1+x+y=0', '⠼⠂⠬⠭⠬⠽ ⠨⠅ ⠼⠴', '3-14'),
    ('x<3', '⠭ ⠐⠅ ⠼⠒', '21.13'),
    ('x>3', '⠭ ⠨⠂ ⠼⠒', '21.13'),
    (r'x\leq 3', '⠭ ⠐⠅⠒ ⠼⠒', '21'),
    (r'x\neq 0', '⠭ ⠌⠨⠅ ⠼⠴', '21'),
    (r'2\times 4', '⠼⠆⠈⠡⠲', '3-54'),
    (r'a\cdot b', '⠁⠡⠃', '20'),
    (r'6\div 3', '⠼⠖⠨⠌⠒', '20'),
    ('x^2', '⠭⠘⠆', '14-3'),
    ('x^{-2}', '⠭⠘⠤⠆', '14-6'),
    ('x_a', '⠭⠰⠁', '14-7'),
    ('x_1', '⠭⠂', '14-36'),
    ('x_{11}', '⠭⠂⠂', '14-37'),
    ('x_{1.2}', '⠭⠂⠨⠆', '14-53'),
    ('12_7', '⠼⠂⠆⠰⠶', '14-42'),
    ('x_{2+k}', '⠭⠰⠆⠬⠅', '14-48'),
    ('x^2+1', '⠭⠘⠆⠐⠬⠂', '14-64'),
    ('(x_1+1)', '⠷⠭⠂⠬⠂⠾', '14-116'),
    ('x_1y_1+x_2y_2', '⠭⠂⠽⠂⠬⠭⠆⠽⠆', '14-117'),
    ('x_a^n', '⠭⠰⠁⠘⠝', '14-121'),
    ('x^n_a', '⠭⠰⠁⠘⠝', '14-121; TeX simultaneous scripts'),
    ('x_1^2', '⠭⠂⠘⠆', '14-123'),
    ('e^{x^2}', '⠑⠘⠭⠘⠘⠆', '14.4'),
    ('x_{i_1}', '⠭⠰⠊⠰⠰⠂', '14-40'),
    ('x_{i,j,k}', '⠭⠰⠊⠻⠚⠻⠅', '14-58'),
    ('x^2=y^2', '⠭⠘⠆ ⠨⠅ ⠽⠘⠆', '14-91'),
    (r'\frac{1}{3}', '⠹⠂⠌⠒⠼', '13-1'),
    (r'\frac{1}{x^2}', '⠹⠂⠌⠭⠘⠆⠐⠼', '14-97'),
    (r'\frac{\frac{1}{2}}{3}', '⠠⠹⠹⠂⠌⠆⠼⠠⠌⠒⠠⠼', '13.6'),
    (r'\sqrt{2}', '⠜⠆⠻', '16-1'),
    (r'\sqrt{x+y}', '⠜⠭⠬⠽⠻', '16-2'),
    (r'\sqrt{x^2+y^2}', '⠜⠭⠘⠆⠐⠬⠽⠘⠆⠐⠻', '16-4'),
    (r'\sqrt[3]{2}', '⠣⠒⠜⠆⠻', '16-10'),
    (r'\sqrt{\sqrt[3]{x}}', '⠜⠨⠣⠒⠜⠭⠨⠻⠻', '16-16'),
    (r'\sqrt{x+\sqrt{y+\sqrt{z}}}', '⠜⠭⠬⠨⠜⠽⠬⠨⠨⠜⠵⠨⠨⠻⠨⠻⠻', '16-17'),
    (r'\alpha', '⠨⠁', '6-1'),
    (r'\Sigma', '⠨⠠⠎', '6-1'),
    (r'\eta\chi\psi', '⠨⠱⠨⠯⠨⠽', '6.1.4'),
    (r'\vartheta', '⠨⠈⠹', '6.1.5'),
    (r'\mathbb{R}', '⠠⠸⠰⠠⠗', '7-2'),
    (r'\mathbf{jT}', '⠸⠰⠚⠸⠰⠠⠞', '7-3'),
    (r'\mathcal{A}', '⠈⠰⠠⠁', '7-4'),
    (r'\sin x', '⠎⠊⠝ ⠭', '18-2'),
    (r'\cos^2 x', '⠉⠕⠎⠘⠆ ⠭', '18-8'),
    (r'\log_2 x', '⠇⠕⠛⠆ ⠭', '14-41, 18.4'),
    (r'\int_a^b f(x)dx', '⠮⠰⠁⠘⠃⠐⠋⠷⠭⠾⠙⠭', '23-16'),
    ('{a{b}c}', '⠁⠃⠉', 'TeX grouping'),
    (r'\frac 123', '⠹⠂⠌⠆⠼⠒', 'TeX single-token arguments'),
    ('x^12', '⠭⠘⠂⠐⠆', 'TeX single-token argument'),
    ('x^{12}', '⠭⠘⠂⠆', 'TeX braced argument'),
    ('x^ab', '⠭⠘⠁⠐⠃', 'TeX single-token argument'),
])
def test_exact_nemeth_cells(source, expected, rule):
    assert latex_to_nemeth(source) == expected, rule


@pytest.mark.parametrize('source', [
    r'\unknown{x}', r'\eps', r'\text{速度}', r'\begin{matrix}a&b\end{matrix}',
    '{x', 'x}', 'x^', 'x^^2', 'x^2^3', r'\frac{1}', r'\sqrt[3{x}',
    '(x]', 'x&y', r'x\\y', '２+３', r'\frac{1}{2+\frac{1}{3+\frac{1}{4}}}',
])
def test_unsupported_or_malformed_formula_is_explicit(source, caplog):
    assert latex_to_nemeth(source) == '⠿'
    assert caplog.records


def test_inline_sum_uses_side_scripts():
    assert latex_to_nemeth(r'\sum_{i=1}^n a_i') == '⠨⠠⠎⠰⠊ ⠰⠨⠅ ⠼⠂⠘⠝⠐⠁⠰⠊'


def test_display_sum_uses_below_and_above_modifiers():
    assert latex_to_nemeth(r'\sum_{n=1}^\infty\frac{1}{2^n}', display=True) == (
        '⠐⠨⠠⠎⠩⠝ ⠨⠅ ⠼⠂⠣⠠⠿⠻⠹⠂⠌⠆⠘⠝⠐⠼')


def test_explicit_limits_override_inline_style():
    assert latex_to_nemeth(r'\sum\limits_{i=1}^n') == '⠐⠨⠠⠎⠩⠊ ⠨⠅ ⠼⠂⠣⠝⠻'


def test_explicit_nolimits_override_display_style():
    assert latex_to_nemeth(r'\sum\nolimits_1^2', display=True) == '⠨⠠⠎⠂⠘⠆'


def test_math_passage_switches_and_spacing():
    assert convert_text_with_math('A $1+2$ B') == 'A ⠸⠩ ⠼⠂⠬⠆ ⠸⠱ B'


def test_main_converter_preserves_nemeth_passage():
    assert ''.join(convert_text('$x^2+1$')) == '⠸⠩ ⠭⠘⠆⠐⠬⠂ ⠸⠱'


def test_main_converter_passes_display_style():
    assert ''.join(convert_text(r'$$\sum\limits_{i=1}^n$$')) == (
        '⠸⠩ ⠐⠨⠠⠎⠩⠊ ⠨⠅ ⠼⠂⠣⠝⠻ ⠸⠱')


def test_number_after_superscript_with_numeric_subscript_restores_once():
    assert latex_to_nemeth('x_1^22') == '⠭⠂⠘⠆⠐⠆'


def test_numeric_subscript_to_a_multiletter_typeform_group_is_explicit():
    assert latex_to_nemeth(r'\mathbf{xy}_1') == '⠸⠰⠭⠸⠰⠽⠰⠂'


def test_fraction_uses_reduced_tex_style_for_sum_limits():
    assert latex_to_nemeth(r'\frac{\sum_1^2 x}{3}', display=True) == (
        '⠹⠨⠠⠎⠂⠘⠆⠐⠭⠌⠒⠼')


def test_superscript_uses_reduced_tex_style_for_sum_limits():
    assert latex_to_nemeth(r'e^{\sum_1^2 x}', display=True) == (
        '⠑⠘⠨⠠⠎⠘⠰⠂⠘⠘⠆⠘⠭')


@pytest.mark.parametrize('source, expected', [
    ('3*4', '⠼⠒⠈⠼⠼⠲'),  # BANA example 3-36
    ('3+-4', '⠼⠒⠬⠐⠤⠲'),  # 24-9: separate operations, not plus/minus
    ('x-+2', '⠭⠤⠐⠬⠆'),
    ('{x^2}^3', '⠭⠘⠆⠐⠘⠒'),
    ('{x_a}_1', '⠭⠰⠁⠐⠰⠂'),
    ('x', '⠰⠭'),  # 6.3.1: standalone letter in a complete math passage
    ('x,y', '⠰⠭⠠ ⠰⠽'),
    ('(x)', '⠷⠭⠾'),  # 6.4.8: both grouping signs
    ('x=y', '⠭ ⠨⠅ ⠽'),  # 6.4.7: adjacent comparison sign
    (r'\sin x', '⠎⠊⠝ ⠭'),  # 18.1: after a function name
    ("x'_1", '⠭⠄⠂'),  # 14-39: numeric subscript to primed letter
    (r'x^\prime', '⠭⠄'),  # 14.12.1: prime is not preceded by a superscript
    (r'x^{\prime 2}', '⠭⠄⠘⠆'),  # 14-132: prime before script
    (r'x^{\prime\prime}', '⠭⠄⠄'),
    (r'x^{\prime\prime 2}', '⠭⠄⠄⠘⠆'),
    (r'x^{\prime\prime}_1', '⠭⠄⠄⠂'),
    (r'x_{\prime 1}', '⠭⠄⠂'),
    ('{x_1}^2', '⠭⠂⠐⠘⠆'),  # 14-128: non-simultaneous numeric subscript
])
def test_additional_context_rules(source, expected):
    assert latex_to_nemeth(source) == expected


@pytest.mark.parametrize('source', [
    r'\left(x)', r'\right(x)', r'(x\right)',
    r'\frac{}{2}', r'\frac{1}{}', r'\sqrt{}',
    r'\frac{1}{2+\frac{1}{3}}',
])
def test_unpaired_sizing_and_empty_required_arguments(source, caplog):
    assert latex_to_nemeth(source) == '⠿'
    assert caplog.records


def test_sentence_punctuation_attaches_to_nemeth_terminator():
    assert convert_text_with_math('A $x$, B') == 'A ⠸⠩ ⠰⠭ ⠸⠱, B'


def test_chinese_punctuation_attaches_to_nemeth_terminator():
    assert ''.join(convert_text('$x$，')) == '⠸⠩ ⠰⠭ ⠸⠱⠐'


@pytest.mark.parametrize('source, expected', [
    ('(a,b,c)', '⠷⠁⠠ ⠃⠠ ⠉⠾'),
    ('(1,2)', '⠷⠂⠠ ⠆⠾'),
    ('(a,2x,y=z)', '⠷⠰⠁⠠ ⠼⠆⠭⠠ ⠽ ⠨⠅ ⠵⠾'),  # 6-30
])
def test_enclosed_list_context(source, expected):
    assert latex_to_nemeth(source) == expected


def test_radical_index_uses_reduced_tex_style():
    assert latex_to_nemeth(r'\sqrt[\sum_{i=1}^n]{x}', display=True) == (
        '⠣⠨⠠⠎⠰⠊ ⠰⠨⠅ ⠼⠂⠘⠝⠐⠜⠭⠻')


def test_script_ell_preserves_its_typeform():
    assert latex_to_nemeth(r'\ell') == '⠈⠰⠇'
