#!/usr/bin/env python3
"""
构建脚本：打包 exe 并放入版本目录。

用法：
    python build.py                   # 按 VERSION 打包
    python build.py --version 1.0.1  # 指定版本
"""

import os
import sys
import shutil
import subprocess
import argparse

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def read_version():
    with open(os.path.join(ROOT_DIR, 'VERSION')) as f:
        return f.read().strip()

def build(version=None):
    if version is None:
        version = read_version()

    print(f'=== Braille Converter v{version} 构建开始 ===')

    # 清理旧构建
    for d in ['build', 'build_temp']:
        path = os.path.join(ROOT_DIR, d)
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)

    # releases/vX.Y.Z/ 作为输出目录
    release_dir = os.path.join(ROOT_DIR, 'releases', f'v{version}')
    os.makedirs(release_dir, exist_ok=True)

    # 运行 PyInstaller（--distpath 直接指向 release 目录）
    exe_name = f'BrailleConverter-v{version}'
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean', '--onefile', '--windowed',
        '--name', exe_name,
        '--distpath', release_dir,
        '--add-data', f'samples/test.txt{os.pathsep}.',
        '--add-data', f'samples/test.md{os.pathsep}.',
        '--hidden-import', 'src.converter.chinese_conv',
        '--hidden-import', 'src.converter.english_conv',
        '--hidden-import', 'src.converter.math_conv',
        '--hidden-import', 'src.converter.braille_converter',
        '--hidden-import', 'src.gui.main_window',
        '--hidden-import', 'src.gui.braille_canvas',
        '--hidden-import', 'src.gui.file_dialog',
        '--hidden-import', 'src.paginator',
        'main.py',
    ]

    print('运行 PyInstaller...')
    result = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print('构建失败！')
        print(result.stderr[-500:])
        sys.exit(1)

    # 验证
    final_exe = os.path.join(release_dir, f'{exe_name}.exe')
    if os.path.exists(final_exe):
        size_mb = os.path.getsize(final_exe) / (1024 * 1024)
        print(f'✅ 构建成功: releases/v{version}/{exe_name}.exe ({size_mb:.1f} MB)')
    else:
        print(f'⚠  exe 未找到: {final_exe}')

    print(f'=== 完成 ===')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='构建 Braille Converter')
    parser.add_argument('--version', '-v', help='指定版本号（默认使用 VERSION 文件）')
    args = parser.parse_args()
    build(args.version)
