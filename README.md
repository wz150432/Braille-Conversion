# Braille Conversion

桌面盲文阅读器，支持中文正文、英文和 LaTeX 公式。

中文以教育部、国家语委、中国残联发布的 GF 0019—2018《国家通用盲文方案》为规则依据。pypinyin 提供读音，项目单独处理点位、标调、省写、简写和分词连写。

## 使用

```bash
python -m pip install -r requirements.txt
python main.py
```

在 **视图 → 中文盲文** 中选择：

- **省写与简写（默认）**：按规则省写声调，使用“的、么、你、他、她、它”的规定简写。
- **省写，不简写**：保留完整字形，按规则省写声调。
- **字字标调**：保留本调，便于学习和校对；轻声不加调号，“他、它”仍用规范特殊拼写。

自动分词和多音字判读需要人工校订，程序输出不能直接当作专业盲文出版终稿。规则来源、人工校订接口和支持范围见 [中文转写说明](docs/chinese-braille.md)。

中文、英文和数学的实测结果见 [验证报告](docs/conversion-verification.md)。数学模块已按 BANA Nemeth 2022 修正基础点位和结构规则，支持范围及人工复核限制见 [数学转写说明](docs/math-braille.md)。英文 Grade 2 需要实际启用 liblouis。
