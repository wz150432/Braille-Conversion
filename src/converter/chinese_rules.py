"""GF 0019—2018 §§5–11：点位、拼写、标调、省写和简写。

规范原文：https://www.moe.gov.cn/jyb_sjzl/ziliao/A19/201807/W020180725666187054299.pdf
只接受带数字的本调拼音；词界和读音由上层提供，避免在点位层猜语义。
"""

import re
from enum import Enum
from typing import Optional


class ChineseBrailleMode(str, Enum):
    STANDARD = 'standard'          # 声调省写 + §11 定字简写
    TONE_REDUCED = 'tone_reduced'  # 声调省写，不使用定字简写
    FULL = 'full'                  # 字字标调；仍遵循 §9.4 特殊拼写


def resolve_mode(toned: Optional[bool] = None,
                 mode: Optional[ChineseBrailleMode] = None) -> ChineseBrailleMode:
    """旧 toned=True 对应 full，False 对应 standard；显式 mode 优先。"""
    if mode is not None:
        return ChineseBrailleMode(mode)
    return ChineseBrailleMode.FULL if toned else ChineseBrailleMode.STANDARD


# §§5–7。点位表独立于 pypinyin 的输出风格。
INITIALS = dict(zip(
    ('b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h',
     'j', 'q', 'x', 'zh', 'ch', 'sh', 'r', 'z', 'c', 's'),
    '⠃⠏⠍⠋⠙⠞⠝⠇⠛⠅⠓⠛⠅⠓⠌⠟⠱⠚⠵⠉⠎',
))
FINALS = {
    'a': '⠔', 'o': '⠢', 'e': '⠢', 'i': '⠊', 'u': '⠥', 'v': '⠬',
    'er': '⠗', 'ai': '⠪', 'ei': '⠮', 'ao': '⠖', 'ou': '⠷',
    'ia': '⠫', 'iao': '⠜', 'ie': '⠑', 'iou': '⠳',
    'ua': '⠿', 'uai': '⠽', 'uei': '⠺', 'uo': '⠕', 've': '⠾',
    'an': '⠧', 'ang': '⠦', 'en': '⠴', 'eng': '⠼',
    'ian': '⠩', 'iang': '⠭', 'in': '⠣', 'ing': '⠡',
    'uan': '⠻', 'uang': '⠶', 'uen': '⠒', 'ong': '⠲', 'ueng': '⠲',
    'van': '⠯', 'vn': '⠸', 'iong': '⠹',
}
TONES = {1: '⠁', 2: '⠂', 3: '⠄', 4: '⠆', 0: '', 5: ''}
SELF_INITIAL_SYLLABLES = frozenset(('zhi', 'chi', 'shi', 'ri', 'zi', 'ci', 'si'))
_READING_RE = re.compile(r'([a-züv]+)([0-5])\Z')
_Y_FINALS = {
    'yi': 'i', 'ya': 'ia', 'yao': 'iao', 'ye': 'ie', 'you': 'iou',
    'yan': 'ian', 'yang': 'iang', 'yin': 'in', 'ying': 'ing', 'yong': 'iong',
    'yu': 'v', 'yue': 've', 'yuan': 'van', 'yun': 'vn',
}
_W_FINALS = {
    'wu': 'u', 'wa': 'ua', 'wo': 'uo', 'wai': 'uai', 'wei': 'uei',
    'wan': 'uan', 'wang': 'uang', 'wen': 'uen', 'weng': 'ueng',
}

# §8：中文符号不能使用 UEB 英文标点表。
CHINESE_PUNCTUATION = {
    '。': '⠐⠆', '，': '⠐', '、': '⠈', '；': '⠰', '？': '⠐⠄',
    '！': '⠰⠂', '：': '⠤', '“': '⠘', '”': '⠘',
    '‘': '⠘⠘', '’': '⠘⠘', '（': '⠰⠄', '）': '⠠⠆',
    '【': '⠰⠆', '】': '⠰⠆', '［': '⠰⠆', '］': '⠰⠆',
    '——': '⠠⠤', '—': '⠠⠤', '……': '⠐⠐⠐', '…': '⠐⠐⠐',
    '－': '⠤', '《': '⠐⠤', '》': '⠤⠂',
    '〈': '⠐⠄', '〉': '⠠⠂', '·': '⠠⠄',
}


def split_reading(reading: str):
    """拼音正词法缩写展开为规范声韵母；y/w 为隔音字母，不是声母。"""
    match = _READING_RE.fullmatch(reading.lower())
    if not match:
        raise ValueError(f'需要带本调数字的拼音，收到 {reading!r}')
    base = match[1].replace('ü', 'v')
    tone = int(match[2])
    if base in _Y_FINALS:
        return base, '', _Y_FINALS[base], tone
    if base in _W_FINALS:
        return base, '', _W_FINALS[base], tone
    initial = next((i for i in ('zh', 'ch', 'sh', *INITIALS) if base.startswith(i)), '')
    final = base[len(initial):]
    if base in SELF_INITIAL_SYLLABLES:
        final = ''  # §9.2 舌尖韵母省略。
    else:
        if initial in ('j', 'q', 'x') and final.startswith('u'):
            final = 'v' + final[1:]
        final = {'iu': 'iou', 'ui': 'uei', 'un': 'uen', 'ue': 've'}.get(final, final)
        if final and final not in FINALS:
            raise ValueError(f'规范点位表不包含音节 {reading!r} 的韵母 {final!r}')
        if not final:
            raise ValueError(f'音节 {reading!r} 缺少韵母')
    return base, initial, final, tone


def _omit_tone(base: str, initial: str, tone: int) -> bool:
    # §10.2.8：问的声调提供点位参照；再/在的语义区别在字级处理。
    if base == 'wen' and tone == 4:
        return False
    # §10.2.5–6 优先于普通零声母规则。
    if base in ('yi', 'er', 'wo', 'ye', 'you'):
        return tone in {'yi': (1,), 'er': (2,), 'wo': (3,), 'ye': (3,), 'you': (3,)}[base]
    if base == 'o':
        return True
    if base == 'e':
        return False
    if not initial:
        return tone == 4
    if initial == 'f':
        return tone == 1
    if initial in ('p', 'm', 't', 'n', 'h', 'q', 'ch', 'r', 'c'):
        return tone == 2 and base != 'tou'
    return tone == 4 and base not in ('le', 'zi')


def translate_syllable(reading: str,
                       mode: ChineseBrailleMode = ChineseBrailleMode.STANDARD,
                       *, keep_tone: bool = False) -> str:
    """按 §§9–10 转写一个本调音节。轻声不设符号，不做口语变调。"""
    mode = ChineseBrailleMode(mode)
    base, initial, final, tone = split_reading(reading)
    cells = INITIALS.get(initial, '') + FINALS.get(final, '')
    if mode != ChineseBrailleMode.FULL and not keep_tone and _omit_tone(base, initial, tone):
        return cells
    return cells + TONES[tone]


# §11.1。只对列出的读音适用，不能把“目的”的 dì 或“么”的 mó 简写。
SHORTHAND = {
    ('的', 'de5'): '⠙', ('么', 'me5'): '⠍', ('你', 'ni3'): '⠝',
    ('他', 'ta1'): '⠞', ('她', 'ta1'): '⠞⠁', ('它', 'ta1'): '⠈⠞',
}
SPECIAL_SPELLINGS = {('他', 'ta1'): '⠞⠔', ('它', 'ta1'): '⠈⠞⠔'}  # §9.4
