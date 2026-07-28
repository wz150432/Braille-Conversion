"""
中文文本 → 盲文（Braille）转换模块

基于 pypinyin 的 Style.BRAILLE_MAINLAND / BRAILLE_MAINLAND_TONE，
遵循 GF 0019-2018《国家通用盲文方案》。
"""

from pypinyin import pinyin, Style
from typing import List


def chinese_to_braille(text: str, toned: bool = False) -> List[str]:
    """将中文文本转换为盲文字符列表 (Unicode Braille)。

    Args:
        text: 中文文本（可含标点、空格、非汉字字符）。
        toned: True 输出带声调盲文 (BRAILLE_MAINLAND_TONE)，
               False 输出无调盲文 (BRAILLE_MAINLAND)。

    Returns:
        盲文字符列表，每个元素是一个 Unicode 盲文字符 (U+2800..U+28FF)。

    注意:
        - 非汉字字符（英文字母、数字、标点）保持原样返回。
        - 声调模式(BRAILLE_MAINLAND_TONE) 在无调盲文基础上附加声调点。
    """
    if not text:
        return []

    style = Style.BRAILLE_MAINLAND_TONE if toned else Style.BRAILLE_MAINLAND
    # pinyin() 返回 List[List[str]]，每个汉字对应一个多音字列表
    # 取第一个读音（最常见读音）
    result: List[str] = []

    try:
        raw = pinyin(text, style=style, errors='default')
        for item in raw:
            if item:
                syllable = item[0]
                # pypinyin 对非汉字返回原字符，对汉字返回 Braille 字符串（如 "你"→"⠝⠊"）
                # 展开为单个 Braille 字符列表
                for ch in syllable:
                    result.append(ch)
            else:
                # 空条目安全处理
                result.append(' ')
    except Exception:
        # 任何异常降级：返回占位符
        result.append('⠿')  # ⠿ 占位符

    return result


def is_chinese_char(ch: str) -> bool:
    """判断单个字符是否为 CJK 统一表意文字。"""
    if len(ch) != 1:
        return False
    cp = ord(ch)
    return (
        (0x4E00 <= cp <= 0x9FFF) or
        (0x3400 <= cp <= 0x4DBF) or
        (0x20000 <= cp <= 0x2A6DF) or
        (0x2A700 <= cp <= 0x2B73F) or
        (0x2B740 <= cp <= 0x2B81F) or
        (0x2B820 <= cp <= 0x2CEAF) or
        (0xF900 <= cp <= 0xFAFF) or
        (0x2F800 <= cp <= 0x2FA1F)
    )
