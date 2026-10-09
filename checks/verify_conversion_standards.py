"""独立的规范点位审计：失败返回 1，不修改转换器或系统依赖。

中文 GF 0019—2018；英文 ICEB UEB 2024；数学 BANA Nemeth 2022。
数学期望值表示 Nemeth 数学区内的内容，不含外层 UEB/Nemeth 切换符。
审计包含故意启用的英文降级路径，用于揭示它与完整 UEB 的差异。
此文件不参与普通 pytest 收集；已知规范差异也必须如实返回失败。
"""

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.converter import english_conv as en
from src.converter.braille_converter import convert_text
from src.converter.math_conv import latex_to_nemeth


CHINESE_CASES = [
    ('你的', 'standard', '⠝⠙', '11.1'),
    ('他用', 'standard', '⠞⠔⠹', '11.2'),
    ('怎么样', 'standard', '⠵⠴⠄⠍⠢⠭', '11.2'),
    ('慈爱', 'standard', '⠉⠂⠪', '10.2.7'),
    ('事业', 'standard', '⠱⠆⠑⠆', '10.2.7'),
    ('问', 'standard', '⠒⠆', '10.2.8'),
    ('再', 'standard', '⠵⠪⠆', '10.2.8'),
    ('在', 'standard', '⠵⠪', '10.2.3'),
    ('地道', 'standard', '⠙⠊⠆⠙⠖⠆', '10.2.8'),
    ('你的', 'tone_reduced', '⠝⠊⠄⠙⠢', '10.1, 10.2'),
    ('他 她 它', 'full', '⠞⠔ ⠞⠔⠁ ⠈⠞⠔', '9.4, 10.1'),
]
ENGLISH_CASES = [
    ('hello', '⠓⠑⠇⠇⠕', '4'),
    ('the', '⠮', '10.2'), ('and', '⠯', '10.2'), ('with', '⠾', '10.2'),
    ('123', '⠼⠁⠃⠉', '6'),
    ('"hello"', '⠦⠓⠑⠇⠇⠕⠴', '7.6'),
    ("can't", '⠉⠄⠞', '10.1.2'),
    ('HELLO', '⠠⠠⠓⠑⠇⠇⠕', '8'),
]
MATH_CASES = [
    ('x', '⠰⠭', '6.3.1; complete isolated mathematical expression'),
    ('1+2', '⠼⠂⠬⠆', '3.1.2, 3.3.1, 3.4, 20'),
    ('3.14', '⠼⠒⠨⠂⠲', '3.2.3, example 3-6'),
    ('a+b', '⠁⠬⠃', '20'),
    ('a-b', '⠁⠤⠃', '20'),
    ('x^2', '⠭⠘⠆', '14.4.1, example 14-3'),
    ('x_a', '⠭⠰⠁', '14.4.1, example 14-7'),
    (r'\frac{1}{3}', '⠹⠂⠌⠒⠼', '13.2.1, example 13-1'),
    (r'\sqrt{x}', '⠜⠭⠻', '16.1.1'),
    (r'\alpha', '⠨⠁', '2, 6.1.4'),
    ('-1', '⠤⠼⠂', '3-11'),
    ('x_1', '⠭⠂', '14-36'),
    ('x^2+1', '⠭⠘⠆⠐⠬⠂', '14-64'),
    ('x^2=y^2', '⠭⠘⠆ ⠨⠅ ⠽⠘⠆', '14-91'),
    ('x_a^n', '⠭⠰⠁⠘⠝', '14-121'),
    ('{x_1}^2', '⠭⠂⠐⠘⠆', '14-128'),
    ('1+x+y=0', '⠼⠂⠬⠭⠬⠽ ⠨⠅ ⠼⠴', '3-14'),
    ('3*4', '⠼⠒⠈⠼⠼⠲', '3-36'),
    ('3+-4', '⠼⠒⠬⠐⠤⠲', '24-9'),
    ('(a,b,c)', '⠷⠁⠠ ⠃⠠ ⠉⠾', '6.4.5'),
    ('(1,2)', '⠷⠂⠠ ⠆⠾', '3.5.2'),
    (r'\frac{1}{x^2}', '⠹⠂⠌⠭⠘⠆⠐⠼', '14-97'),
    (r'\frac{\frac{1}{2}}{3}', '⠠⠹⠹⠂⠌⠆⠼⠠⠌⠒⠠⠼', '13.6'),
    (r'\sqrt[3]{2}', '⠣⠒⠜⠆⠻', '16-10'),
    (r'\sqrt{x^2+y^2}', '⠜⠭⠘⠆⠐⠬⠽⠘⠆⠐⠻', '16-4'),
    (r'\Sigma', '⠨⠠⠎', '6-1'),
    (r'\mathbb{R}', '⠠⠸⠰⠠⠗', '7-2'),
    (r'\cos^2 x', '⠉⠕⠎⠘⠆ ⠭', '18-8'),
    (r'\int_a^b f(x)dx', '⠮⠰⠁⠘⠃⠐⠋⠷⠭⠾⠙⠭', '23-16'),
    (r'x^{\prime\prime}_1', '⠭⠄⠄⠂', '14.12, 14.6'),
]
MATH_DISPLAY_CASES = [
    (r'\sum_{n=1}^\infty\frac{1}{2^n}',
     '⠐⠨⠠⠎⠩⠝ ⠨⠅ ⠼⠂⠣⠠⠿⠻⠹⠂⠌⠆⠘⠝⠐⠼', '15-37'),
    (r'\sqrt[\sum_{i=1}^n]{x}',
     '⠣⠨⠠⠎⠰⠊ ⠰⠨⠅ ⠼⠂⠘⠝⠐⠜⠭⠻', '16.2; TeX root-index style'),
]


def comparison(group, source, actual, expected, rule):
    # U+2800 和普通空格均表示空方；不归一化任何有点的盲符。
    actual = actual.replace('\u2800', ' ')
    return dict(group=group, source=source, actual=actual, expected=expected,
                rule=rule, passed=actual == expected)


def audit():
    native_available = en._check_louis()
    rows = [comparison('chinese', source, ''.join(convert_text(source, mode=mode)),
                       expected, rule)
            for source, mode, expected, rule in CHINESE_CASES]
    if native_available:
        rows.extend(comparison('english_native', source, ''.join(en.english_to_braille(source)),
                               expected, rule)
                    for source, expected, rule in ENGLISH_CASES)
    with patch.object(en, '_LOUIS_AVAILABLE', False):
        rows.extend(comparison('english_fallback', source, ''.join(en.english_to_braille(source)),
                               expected, rule)
                    for source, expected, rule in ENGLISH_CASES)
    rows.extend(comparison('math_nemeth', source, latex_to_nemeth(source), expected, rule)
                for source, expected, rule in MATH_CASES)
    rows.extend(comparison('math_nemeth', source, latex_to_nemeth(source, display=True),
                           expected, rule) | {'display': True}
                for source, expected, rule in MATH_DISPLAY_CASES)
    summary = {}
    for row in rows:
        counts = summary.setdefault(row['group'], {'passed': 0, 'failed': 0})
        counts['passed' if row['passed'] else 'failed'] += 1
    return {'native_available': native_available, 'summary': summary, 'cases': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='保存完整 JSON 审计记录')
    args = parser.parse_args()
    report = audit()
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n',
                               encoding='utf-8')
    print(json.dumps(report['summary'], ensure_ascii=False, indent=2))
    for row in report['cases']:
        if not row['passed']:
            print(f"FAIL {row['group']} {row['source']!r}: "
                  f"actual={row['actual']} expected={row['expected']} rule={row['rule']}")
    if not report['native_available']:
        print('SKIP english_native: 未启用 liblouis，未验证 Grade 2')
    return 1 if any(not row['passed'] for row in report['cases']) else (
        0 if report['native_available'] else 2)


if __name__ == '__main__':
    sys.exit(main())
