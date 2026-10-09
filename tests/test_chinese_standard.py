"""GF 0019—2018 原例和点位表的精确回归测试（不是 Unicode 范围检查）。"""

import pytest

from src.converter import chinese_conv as cn
from src.converter.braille_converter import convert_text


@pytest.mark.parametrize('reading, expected', [
    # §10.2.1–4：按声母省写；保留 tóu、lè、zì 的声调。
    ('fen1', '⠋⠴'), ('fen2', '⠋⠴⠂'),
    ('min2', '⠍⠣'), ('tou2', '⠞⠷⠂'),
    ('dian4', '⠙⠩'), ('le4', '⠇⠢⠆'), ('zi4', '⠵⠆'),
    ('ai4', '⠪'), ('yong4', '⠹'),
    # §10.2.5–6：韵母自成音节的例外。
    ('yi1', '⠊'), ('yi2', '⠊⠂'), ('yi3', '⠊⠄'), ('yi4', '⠊⠆'),
    ('yu2', '⠬⠂'), ('yu4', '⠬'),
    ('er2', '⠗'), ('er4', '⠗⠆'),
    ('wo3', '⠕'), ('wo4', '⠕⠆'),
    ('ye3', '⠑'), ('ye4', '⠑⠆'),
    ('you3', '⠳'), ('you4', '⠳⠆'),
    ('o1', '⠢'), ('o2', '⠢'), ('o3', '⠢'), ('o4', '⠢'),
    ('e4', '⠢⠆'), ('wen4', '⠒⠆'),
    # §6、9.2：复韵母、拼音缩写、舌尖韵母。
    ('liu2', '⠇⠳⠂'), ('gui1', '⠛⠺⠁'), ('jun1', '⠛⠸⠁'),
    ('zhi1', '⠌⠁'), ('chi2', '⠟'), ('shi4', '⠱'),
    ('zi5', '⠵'), ('er5', '⠗'),
])
def test_standard_syllable_rules(reading, expected):
    assert cn.translate_syllable(reading) == expected


@pytest.mark.parametrize('text, expected', [
    ('你的', '⠝⠙'),                              # §11.1
    ('他', '⠞'), ('她', '⠞⠁'), ('它', '⠈⠞'),
    ('他用', '⠞⠔⠹'),                            # §11.2
    ('怎么样', '⠵⠴⠄⠍⠢⠭'),
    ('慈爱', '⠉⠂⠪'), ('事业', '⠱⠆⠑⠆'),        # §10.2.7
    ('问', '⠒⠆'), ('再', '⠵⠪⠆'), ('在', '⠵⠪'),  # §10.2.8
    ('地道', '⠙⠊⠆⠙⠖⠆'),
])
def test_standard_spelling_and_context_exceptions(text, expected):
    assert ''.join(cn.chinese_to_braille(text)) == expected


@pytest.mark.parametrize('mode, expected', [
    ('standard', '⠝⠙'),
    ('tone_reduced', '⠝⠊⠄⠙⠢'),
    ('full', '⠝⠊⠄⠙⠢'),
])
def test_modes_have_defined_semantics(mode, expected):
    assert ''.join(cn.chinese_to_braille('你的', mode=mode)) == expected


def test_full_mode_still_uses_special_pronoun_spelling():
    assert ''.join(cn.chinese_to_braille('他 她 它', mode='full')) == '⠞⠔ ⠞⠔⠁ ⠈⠞⠔'


@pytest.mark.parametrize('text, words', [
    ('我爱北京', ['我爱', '北京']),
    ('中华人民共和国', ['中华', '人民', '共和国']),
    ('环境保护规划', ['环境', '保护', '规划']),
    ('生产关系', ['生产', '关系']),
    ('研究生院', ['研究生院']),
    ('古生物学家', ['古生物学家']),
    ('图书馆', ['图书馆']),
    ('来来往往', ['来来往往']),
    ('研究研究', ['研究', '研究']),
    ('雪白雪白', ['雪白', '雪白']),
    ('非业务人员', ['非业务', '人员']),
    ('孩子们', ['孩子们']),
    ('艺术家', ['艺术家']),
    ('十七八岁', ['十七八岁']),
    ('每年', ['每年']), ('山上', ['山上']), ('很好', ['很好']),
])
def test_word_boundaries_follow_chapter_12(text, words):
    assert cn.segment_chinese(text) == words


def test_word_space_is_emitted():
    assert ''.join(cn.chinese_to_braille('我爱北京')) == '⠕⠪ ⠃⠮⠄⠛⠡⠁'


def test_manual_words_readings_and_tone_preservation():
    words = [cn.ChineseWord('地道', ('di4', 'dao5'), frozenset({0}))]
    assert ''.join(cn.translate_words(words)) == '⠙⠊⠆⠙⠖'
    assert cn.chinese_to_braille('地道', words=words) == cn.translate_words(words)


def test_explicit_word_boundary_changes_shortening():
    joined = cn.translate_words([cn.ChineseWord('他用', ('ta1', 'yong4'))])
    separate = cn.translate_words([
        cn.ChineseWord('他', ('ta1',)), cn.ChineseWord('用', ('yong4',)),
    ])
    assert ''.join(joined) == '⠞⠔⠹'
    assert ''.join(separate) == '⠞ ⠹'


@pytest.mark.parametrize('punct, expected', [
    ('，', '⠐'), ('。', '⠐⠆'), ('、', '⠈'), ('；', '⠰'),
    ('？', '⠐⠄'), ('！', '⠰⠂'), ('：', '⠤'),
    ('“”', '⠘⠘'), ('‘’', '⠘⠘⠘⠘'),
    ('（）', '⠰⠄⠠⠆'), ('【】', '⠰⠆⠰⠆'),
    ('《》', '⠐⠤⠤⠂'), ('〈〉', '⠐⠄⠠⠂'),
    ('——', '⠠⠤'), ('……', '⠐⠐⠐'), ('·', '⠠⠄'),
])
def test_chinese_punctuation_is_chinese_braille(punct, expected):
    assert ''.join(cn.chinese_to_braille(punct)) == expected
    assert ''.join(convert_text(punct)) == expected


def test_app_dispatcher_keeps_mode_in_mixed_and_math_text():
    full = ''.join(cn.chinese_to_braille('人民', mode='full'))
    reduced = ''.join(cn.chinese_to_braille('人民', mode='standard'))
    assert full != reduced
    for source in ['人民', 'Hello人民', '人民 $x^2$']:
        assert full in ''.join(convert_text(source, mode='full'))
        assert reduced in ''.join(convert_text(source, mode='standard'))


def test_numbers_have_one_numeric_indicator():
    assert ''.join(convert_text('12345')) == '⠼⠁⠃⠉⠙⠑'
    assert '⠼⠁⠃' in ''.join(convert_text('编号12'))


def test_invalid_manual_input_is_rejected():
    with pytest.raises(ValueError):
        cn.chinese_to_braille('中国', words=[cn.ChineseWord('中华')])
    with pytest.raises(ValueError):
        cn.translate_words([cn.ChineseWord('中国', ('zhong1',))])
    with pytest.raises(ValueError):
        cn.chinese_to_braille('中国', mode='unknown')


def test_unsupported_character_does_not_discard_surrounding_text():
    assert cn.chinese_to_braille('你\U000323af好').count('⠿') == 1
    assert '⠝' in cn.chinese_to_braille('你\U000323af好')
    assert '⠓' in cn.chinese_to_braille('你\U000323af好')
