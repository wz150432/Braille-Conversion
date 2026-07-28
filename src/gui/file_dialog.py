"""
文件对话框模块：打开文件、拖入文件、编码检测。
"""

import os
import logging
from typing import Optional

from PySide6.QtWidgets import QFileDialog, QWidget, QMessageBox
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)

# 支持的文件格式（第一项为默认，包含所有支持格式）
SUPPORTED_EXTENSIONS = [
    "所有支持的文档 (*.txt *.md *.markdown *.rst)",
    "文本文件 (*.txt)",
    "Markdown (*.md *.markdown)",
    "所有文件 (*.*)",
]
SUPPORTED_EXTENSIONS_FILTER = ";;".join(SUPPORTED_EXTENSIONS)

# 最大文件大小（10MB）
MAX_FILE_SIZE = 10 * 1024 * 1024


def open_file_dialog(parent: Optional[QWidget] = None) -> Optional[str]:
    """打开文件选择对话框，让用户选择一个 .txt 文件。

    Args:
        parent: 父窗口。

    Returns:
        文件路径，如果用户取消则返回 None。
    """
    path, _ = QFileDialog.getOpenFileName(
        parent,
        "打开文本文件",
        "",
        SUPPORTED_EXTENSIONS_FILTER,
    )
    return path if path else None


def read_file_content(file_path: str) -> Optional[str]:
    """读取文件内容，自动检测编码。

    按以下顺序尝试：
      1. UTF-8
      2. chardet 自动检测
      3. 让用户选择（通过 callback）

    Args:
        file_path: 文件路径。

    Returns:
        文件内容字符串，失败返回 None。
    """
    if not os.path.exists(file_path):
        logger.error("文件不存在: %s", file_path)
        return None

    # 检查文件大小
    file_size = os.path.getsize(file_path)
    if file_size > MAX_FILE_SIZE:
        logger.warning("文件过大 (%d MB)，超过限制 (%d MB)",
                       file_size // (1024 * 1024),
                       MAX_FILE_SIZE // (1024 * 1024))
        # 仍然尝试读取，上层可以处理超时

    # 尝试 UTF-8
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        pass
    except Exception as e:
        logger.error("读取文件失败: %s", e)
        return None

    # UTF-8 失败，使用 chardet 检测编码
    try:
        import chardet
        with open(file_path, 'rb') as f:
            raw_data = f.read(min(file_size, 1024 * 1024))  # 最多读 1MB 用于检测
            result = chardet.detect(raw_data)
            encoding = result.get('encoding', 'utf-8')
            if encoding and encoding.lower() == 'ascii':
                encoding = 'utf-8'
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, LookupError) as e2:
                logger.error("自动检测编码 %s 仍失败: %s", encoding, e2)
                return None
    except ImportError:
        logger.warning("chardet 不可用，无法自动检测编码")
        return None
    except Exception as e:
        logger.error("编码检测失败: %s", e)
        return None


class FileDropHandler:
    """文件拖入处理。"""

    @staticmethod
    def is_supported_file(path: str) -> bool:
        """检查是否为支持的文件格式。"""
        ext = os.path.splitext(path)[1].lower()
        return ext in ('.txt', '.md', '.markdown', '.rst')

    @staticmethod
    def get_dropped_file_path(event) -> Optional[str]:
        """从拖入事件中提取文件路径。

        Args:
            event: QDropEvent。

        Returns:
            文件路径，如果不是支持的文件则返回 None。
        """
        from PySide6.QtGui import QDropEvent
        if not isinstance(event, QDropEvent):
            return None

        urls = event.mimeData().urls()
        if not urls:
            return None

        path = urls[0].toLocalFile()
        if FileDropHandler.is_supported_file(path):
            return path
        return None
