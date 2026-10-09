"""以 GF 0019—2018 为规则依据的中文盲文转写。

pypinyin 仅生成本调读音；盲文点位、省写、简写和词界在本项目中处理。
自动语义分析不能代替专业编校，ChineseWord 可明确指定词界、读音和保调。
"""

import logging
from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Sequence, Tuple

from pypinyin import pinyin, Style

from src.converter.chinese_rules import (
    ChineseBrailleMode, CHINESE_PUNCTUATION, SHORTHAND, SPECIAL_SPELLINGS,
    SELF_INITIAL_SYLLABLES, resolve_mode, split_reading, translate_syllable,
)
from src.converter.chinese_segmentation import segment_chinese

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChineseWord:
    """校订后的连写单位；readings 为逐字本调拼音，keep_tones 为从 0 起的字序。"""
    text: str
    readings: Optional[Tuple[str, ...]] = None
    keep_tones: FrozenSet[int] = frozenset()


def is_chinese_char(ch: str) -> bool:
    """CJK 统一表意文字（含扩展 A–I）、兼容字及汉字数字〇。"""
    if len(ch) != 1:
        return False
    cp = ord(ch)
    return cp == 0x3007 or any(start <= cp <= end for start, end in (
        (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF),
        (0x20000, 0x2EE5F), (0x2F800, 0x2FA1F), (0x30000, 0x323AF),
    ))


def _word_readings(word: ChineseWord):
    if not word.text or not all(is_chinese_char(ch) for ch in word.text):
        raise ValueError('ChineseWord 必须是非空的连续中文连写单位')
    if any(not isinstance(index, int) or index < 0 or index >= len(word.text)
           for index in word.keep_tones):
        raise ValueError('keep_tones 的字序超出连写单位')
    if word.readings is not None:
        if len(word.readings) != len(word.text):
            raise ValueError('readings 必须与连写单位逐字对应')
        for reading in word.readings:
            split_reading(reading)
        return tuple(reading.lower().replace('ü', 'v').replace('0', '5') for reading in word.readings)
    raw = pinyin(word.text, style=Style.TONE3, neutral_tone_with_five=True,
                 errors=lambda chars: list(chars))
    return tuple(item[0] for item in raw)


def translate_words(words: Sequence[ChineseWord],
                    mode: ChineseBrailleMode = ChineseBrailleMode.STANDARD) -> List[str]:
    """按校订词界转写，以一方空格分隔；不跨词判断简写/声调省写例外。"""
    mode = ChineseBrailleMode(mode)
    rendered = []
    for word in words:
        readings = _word_readings(word)
        cells = []
        for index, (char, reading) in enumerate(zip(word.text, readings)):
            try:
                base, initial, final, _ = split_reading(reading)
            except ValueError:
                logger.warning('无法取得规范拼音：%s，使用单字占位符', char)
                cells.append('⠿')
                continue
            next_is_final = False
            if index + 1 < len(readings):
                try:
                    _, next_initial, next_final, _ = split_reading(readings[index + 1])
                    next_is_final = not next_initial and bool(next_final)
                except ValueError:
                    pass
            # §10.2.7–8：保调发生在连写单位内部；语义例外允许人工补充。
            keep = (index in word.keep_tones or char == '再' or word.text == '地道'
                    or (base in SELF_INITIAL_SYLLABLES and next_is_final))
            short = SHORTHAND.get((char, reading))
            # §11.2 不限制“她”；他/它仍遵循 §9.4 的特殊完整拼写。
            forbid_short = char in '的么你他它' and next_is_final
            if mode == ChineseBrailleMode.STANDARD and short and not forbid_short and not keep:
                cells.append(short)
            else:
                cells.append(SPECIAL_SPELLINGS.get((char, reading)) or
                             translate_syllable(reading, mode, keep_tone=keep))
        rendered.append(''.join(cells))
    return list(' '.join(rendered))


def chinese_to_braille(text: str, toned: Optional[bool] = None, *,
                      mode: Optional[ChineseBrailleMode] = None,
                      words: Optional[Sequence[ChineseWord]] = None) -> List[str]:
    """转写中文段和中文标点，其他字符保留给总调度器。

    默认 standard；full 字字标调；tone_reduced 省写而不定字简写。
    兼容旧 toned 参数：True→full，False→standard（不再全部去调）。
    words 用于人工校订，必须覆盖全部 text，且 text 必须是连续中文段。
    """
    resolved = resolve_mode(toned, mode)
    if words is not None:
        if ''.join(word.text for word in words) != text:
            raise ValueError('人工词界必须完整覆盖原文，不得增删字符')
        return translate_words(words, resolved)
    result = []
    index = 0
    while index < len(text):
        if is_chinese_char(text[index]):
            end = index + 1
            while end < len(text) and is_chinese_char(text[end]):
                end += 1
            result.extend(translate_words([
                ChineseWord(word) for word in segment_chinese(text[index:end])
            ], resolved))
            index = end
            continue
        # 汉语破折号、省略号的成对印刷形式各对应一个盲文符号。
        pair = text[index:index + 2]
        symbol = pair if pair in CHINESE_PUNCTUATION else text[index]
        result.extend(CHINESE_PUNCTUATION.get(symbol, symbol))
        index += len(symbol)
    return result
