#!/usr/bin/env python3
"""
Braille Conversion — 中文/英文/数学 → 盲文转换与阅读器
"""

import sys
import os
import logging

# 打包兼容路径
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 读取版本号（打包后 VERSION 在 MEIPASS 根目录）
_VERSION_FILE = os.path.join(BASE_DIR, 'VERSION')
try:
    with open(_VERSION_FILE) as f:
        __version__ = f.read().strip()
except Exception:
    __version__ = '1.1.2'

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon
    from src.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("BrailleConverter")
    app.setOrganizationName("BrailleConversion")
    app.setApplicationVersion(__version__)
    app.setStyle('Fusion')

    # 设置图标（打包后 VERSION 和 icon.ico 都在 MEIPASS）
    icon_path = os.path.join(BASE_DIR, 'resources', 'icon.ico')
    if not os.path.isfile(icon_path):
        icon_path = os.path.join(BASE_DIR, 'icon.ico')
    if os.path.isfile(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    window = MainWindow()
    window.setWindowTitle(f"Braille 转换阅读器 v{__version__}")
    if app.windowIcon() and not app.windowIcon().isNull():
        window.setWindowIcon(app.windowIcon())
    window.show()

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.isfile(file_path):
            window._load_file(file_path)

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
