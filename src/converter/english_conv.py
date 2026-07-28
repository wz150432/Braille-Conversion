"""
英文文本 → 盲文 Grade 2 转换模块

基于 liblouis C 库 (ctypes 调用 liblouis.dll)，使用 UEB (Unified English Braille)
en-ueb-g2.ctb 翻译表。

liblouis 输出 ASCII 点字表示，再通过 text_nabcc.dis 映射表转为 Unicode Braille。
"""

import re
import os
import sys
import ctypes
import logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

_TABLE_NAME = 'en-ueb-g2.ctb'

# ── 查找 liblouis DLL 和翻译表 ─────────────────────────────────

def _find_liblouis_dir() -> str:
    """找到 liblouis 数据目录（含 DLL 和 tables/）。"""
    if getattr(sys, 'frozen', False):
        # PyInstaller: --add-data 把文件放在 MEIPASS 下
        # tables/ 在 liblouis_win/share/liblouis/tables/
        # liblouis.dll 在根目录
        return sys._MEIPASS

    candidates = [
        os.path.join(os.path.dirname(__file__), '..', '..', 'liblouis_win'),
        os.path.join(os.path.dirname(__file__), '..', '..', '..', 'liblouis_win'),
    ]
    for d in candidates:
        d = os.path.abspath(d)
        if os.path.isdir(d):
            return d

    env_path = os.environ.get('LIBLOUIS_DIR', '')
    if env_path and os.path.isdir(env_path):
        return env_path
    return ''


_LOUIS_DIR = ''
_LOUIS_DLL: Optional[ctypes.CDLL] = None


def _load_liblouis() -> Optional[ctypes.CDLL]:
    """加载 liblouis DLL 并设置函数签名。"""
    global _LOUIS_DIR, _LOUIS_DLL

    if _LOUIS_DLL is not None:
        return _LOUIS_DLL

    _LOUIS_DIR = _find_liblouis_dir()
    if not _LOUIS_DIR:
        logger.warning("找不到 liblouis 目录")
        return None

    dll_path = os.path.join(_LOUIS_DIR, 'bin', 'liblouis.dll')
    if not os.path.isfile(dll_path):
        dll_path = os.path.join(_LOUIS_DIR, 'liblouis.dll')
    if not os.path.isfile(dll_path):
        logger.warning("找不到 liblouis.dll，已搜索: %s", _LOUIS_DIR)
        return None

    try:
        dll = ctypes.CDLL(dll_path)
    except OSError as e:
        logger.warning("加载 liblouis.dll 失败: %s", e)
        return None

    # Windows 版 liblouis 使用 32-bit widechar (unsigned int)
    dll.lou_translateString.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    dll.lou_translateString.restype = ctypes.c_int

    _LOUIS_DLL = dll
    return dll


# ── ASCII 点字 → Unicode Braille 映射 ──────────────────────────

_DOTS_TO_BRAILLE: Dict[int, int] = {}
_DOTS_MAPPING_LOADED = False


def _load_dots_mapping() -> None:
    """解析 liblouis display 表，建立 ASCII→Unicode Braille 映射。"""
    global _DOTS_TO_BRAILLE, _DOTS_MAPPING_LOADED
    if _DOTS_MAPPING_LOADED:
        return

    if getattr(sys, 'frozen', False):
        tables_dir = os.path.join(_LOUIS_DIR, 'liblouis_win', 'share', 'liblouis', 'tables')
    else:
        tables_dir = os.path.join(_LOUIS_DIR, 'share', 'liblouis', 'tables')
        if not os.path.isdir(tables_dir):
            tables_dir = os.path.join(_LOUIS_DIR, 'tables')

    for fname in ['text_nabcc.dis', 'spaces.uti']:
        fpath = os.path.join(tables_dir, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                for line in f:
                    m = re.match(r'display\s+\\x([0-9A-Fa-f]{4})\s+([0-9]+)', line)
                    if m:
                        ascii_val = int(m.group(1), 16)
                        dot_str = m.group(2)
                        bits = 0
                        for d in dot_str:
                            if '1' <= d <= '8':
                                bits |= 1 << (int(d) - 1)
                        _DOTS_TO_BRAILLE[ascii_val] = 0x2800 | bits
        except OSError:
            pass

    _DOTS_MAPPING_LOADED = True
    logger.info("liblouis: 已加载 %d 个点字→Unicode 映射", len(_DOTS_TO_BRAILLE))


def _dots_to_unicode(chars: str) -> str:
    """将 liblouis ASCII 点字输出转为 Unicode Braille。"""
    result = []
    for ch in chars:
        braille = _DOTS_TO_BRAILLE.get(ord(ch))
        if braille is not None:
            result.append(chr(braille))
        else:
            result.append(ch)
    return ''.join(result)


# ── 降级用基本 Braille 字母映射 ───────────────────────────────

_FALLBACK_MAP = {
    'a': '⠁', 'b': '⠃', 'c': '⠉', 'd': '⠙', 'e': '⠑',
    'f': '⠋', 'g': '⠛', 'h': '⠓', 'i': '⠊', 'j': '⠚',
    'k': '⠅', 'l': '⠇', 'm': '⠍', 'n': '⠝', 'o': '⠕',
    'p': '⠏', 'q': '⠟', 'r': '⠗', 's': '⠎', 't': '⠞',
    'u': '⠥', 'v': '⠧', 'w': '⠺', 'x': '⠭', 'y': '⠽', 'z': '⠵',
    'A': '⠠⠁', 'B': '⠠⠃', 'C': '⠠⠉', 'D': '⠠⠙', 'E': '⠠⠑',
    'F': '⠠⠋', 'G': '⠠⠛', 'H': '⠠⠓', 'I': '⠠⠊', 'J': '⠠⠚',
    'K': '⠠⠅', 'L': '⠠⠇', 'M': '⠠⠍', 'N': '⠠⠝', 'O': '⠠⠕',
    'P': '⠠⠏', 'Q': '⠠⠟', 'R': '⠠⠗', 'S': '⠠⠎', 'T': '⠠⠞',
    'U': '⠠⠥', 'V': '⠠⠧', 'W': '⠠⠺', 'X': '⠠⠭', 'Y': '⠠⠽', 'Z': '⠠⠵',
    '0': '⠼⠚', '1': '⠼⠁', '2': '⠼⠃', '3': '⠼⠉', '4': '⠼⠙',
    '5': '⠼⠑', '6': '⠼⠋', '7': '⠼⠛', '8': '⠼⠓', '9': '⠼⠊',
    '.': '⠲', ',': '⠂', '?': '⠦', '!': '⠖', ':': '⠒',
    ';': '⠆', '-': '⠤', '/': '⠌', '(': '⠶', ')': '⠶',
    '"': '⠦', "'": '⠄', ' ': ' ',
}

_LOUIS_AVAILABLE: Optional[bool] = None


def _get_table_path() -> str:
    """返回 en-ueb-g2.ctb 的绝对路径。"""
    if getattr(sys, 'frozen', False):
        # PyInstaller: tables at liblouis_win/share/liblouis/tables/
        tables_dir = os.path.join(_LOUIS_DIR, 'liblouis_win', 'share', 'liblouis', 'tables')
    else:
        tables_dir = os.path.join(_LOUIS_DIR, 'share', 'liblouis', 'tables')
        if not os.path.isdir(tables_dir):
            tables_dir = os.path.join(_LOUIS_DIR, 'tables')
    return os.path.join(tables_dir, _TABLE_NAME)


def _check_louis() -> bool:
    """检查 liblouis 是否可用，结果缓存。"""
    global _LOUIS_AVAILABLE
    if _LOUIS_AVAILABLE is not None:
        return _LOUIS_AVAILABLE

    dll = _load_liblouis()
    if dll is None:
        _LOUIS_AVAILABLE = False
        return False

    table_path = _get_table_path()
    if not os.path.isfile(table_path):
        logger.warning("找不到翻译表: %s", table_path)
        _LOUIS_AVAILABLE = False
        return False

    # 加载点字映射
    _load_dots_mapping()
    if not _DOTS_TO_BRAILLE:
        logger.warning("点字映射表为空")
        _LOUIS_AVAILABLE = False
        return False

    # 验证翻译可用
    try:
        result = _louis_translate_native("test")
        if result is not None:
            _LOUIS_AVAILABLE = True
            return True
    except Exception as e:
        logger.warning("liblouis 翻译验证失败: %s", e)

    _LOUIS_AVAILABLE = False
    return False


def english_to_braille(text: str) -> List[str]:
    """将英文文本转换为 Grade 2 盲文字符列表。

    Args:
        text: 英文文本（可含标点、数字、空格）。

    Returns:
        盲文字符列表。
    """
    if not text:
        return []

    if _check_louis():
        return _louis_translate(text)
    else:
        return _fallback_translate(text)


def _louis_translate(text: str) -> List[str]:
    """使用 liblouis (ctypes) 进行 Grade 2 翻译。"""
    try:
        result = _louis_translate_native(text)
        if result is None:
            raise RuntimeError("翻译返回 None")
        return list(result)
    except Exception as e:
        logger.error("liblouis 翻译失败: %s，降级为基本映射", e)
        return _fallback_translate(text)


def _louis_translate_native(text: str) -> Optional[str]:
    """ctypes 调用 lou_translateString，输出转为 Unicode Braille。"""
    dll = _LOUIS_DLL
    if dll is None:
        return None

    # 输入缓冲 (widechar = uint32)
    inbuf = (ctypes.c_uint32 * (len(text) + 1))()
    for i, ch in enumerate(text):
        inbuf[i] = ord(ch)
    inbuf[len(text)] = 0
    inlen = ctypes.c_int(len(text))

    # 输出缓冲
    out_size = len(text) * 8 + 32
    outbuf = (ctypes.c_uint32 * out_size)()
    outlen = ctypes.c_int(out_size)

    # 翻译
    table_path = _get_table_path().encode('utf-8')
    ret = dll.lou_translateString(
        table_path,
        inbuf, ctypes.byref(inlen),
        outbuf, ctypes.byref(outlen),
        ctypes.c_char_p(0),
        ctypes.c_char_p(0),
        ctypes.c_int(0),
    )

    if ret == 0:
        return None

    # liblouis 输出 ASCII 点字表示 → 转为 Unicode Braille
    ascii_output = ''.join(chr(outbuf[i]) for i in range(outlen.value))
    return _dots_to_unicode(ascii_output)


def _fallback_translate(text: str) -> List[str]:
    """降级：基本字符到 Braille 的一一映射（非 Grade 2）。"""
    result: List[str] = []
    for ch in text:
        braille = _FALLBACK_MAP.get(ch)
        if braille is not None:
            for c in braille:
                result.append(c)
        else:
            result.append('⠿')
    return result
