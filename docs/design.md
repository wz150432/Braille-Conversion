# Braille Converter 设计文档

> 中文文本 + 英文文本 → 盲文（Braille）转换与阅读器
> 配套硬件盲文点显器的桌面软件（视觉展示部分）

## 一、概述

将 .txt 文件中的中英文混合文本转换为盲文点阵，在屏幕上分页展示。软件部分先行实现，硬件驱动接口预留。

### 核心技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | PySide6 (Qt for Python) |
| 中文→盲文 | pypinyin 本调读音 + jieba 候选词界 + 项目内 GF 0019—2018 规则层 |
| 英文 Grade 2 → 盲文 | liblouis C 库（ctypes 按平台加载动态库） |
| LaTeX 数学→Nemeth Code | 自研模块（基于 Nemeth Code 规则表） |
| 打包分发 | PyInstaller（--onefile --windowed） |
| 测试 | pytest |

### 标准依据

- 中文盲文：GF 0019-2018《国家通用盲文方案》（2018-07-01 施行）
- 英文盲文：UEB（Unified English Braille），通过 liblouis 实现
- 数学盲文：现有 **Nemeth Code** 模块；不能将其当作中国盲文数学规范的实现

中文规则、支持范围和人工校订接口以 [中文转写说明](chinese-braille.md) 为准。自动候选分词和读音不能保证专业翻印质量。

## 二、整体架构

```
main.py  (入口：启动 QApplication)
   │
   ├── src/gui/                (桌面界面层)
   │   ├── main_window.py      — 主窗口、工具栏、底部导航
   │   ├── braille_canvas.py   — Braille 点阵渲染 (QPainter)
   │   └── file_dialog.py      — 文件打开 / 拖入
   │
   ├── src/converter/          (盲文转换核心，不依赖 GUI)
   │   ├── braille_converter.py — 中/英/数学分流调度器
   │   ├── chinese_conv.py     — 本调读音与连写单位转写，人工校订接口
   │   ├── chinese_rules.py    — 点位、标调、省写、简写、中文标点
   │   ├── chinese_segmentation.py — 候选分词与规范原例校订
   │   ├── english_conv.py     — liblouis → 盲文 (Grade 2)
   │   └── math_conv.py        — LaTeX 数学 → Nemeth Code
   │
   └── src/paginator.py        — 按画布容量自动分页
```

职责边界：
- **converter/** 下的模块不依赖 GUI，可独立测试，后续也能用于 CLI 版本
- **gui/** 只负责呈现和交互，不包含转换逻辑
- **paginator** 接收 Braille 字符串数组和每页容量，返回二维分页数组

## 三、转换管道

```mermaid
flowchart LR
    A[.txt 文件] --> B[全文读取]
    B --> C{识别内容类型}
    C -->|中文| D[ChineseConv]
    C -->|英文| E[EnglishConv]
    C -->|$LaTeX$ 数学| F[MathConv]
    D --> G[BrailleDot 编码]
    E --> G
    F --> G
    G --> H[Paginator 分页]
    H --> I[Canvas 渲染]
```

### 3.1 中文盲文转换（ChineseConv）

1. 形成候选连写单位；可通过 `ChineseWord` 指定人工校订的词界
2. 使用 pypinyin 获取逐字本调；允许人工指定多音字读音
3. 按 GF 0019—2018 第 5–9 条处理点位和拼写
4. 按第 10–11 条处理省写、保调、定字简写及词内例外
5. 支持 `standard`、`tone_reduced`、`full` 三种模式，默认按规则省写与简写
6. 使用中文标点表，词间空一方；语境和出版版式仍需专业编校

### 3.2 英文 Grade 2 转换（EnglishConv）

1. 调用 `louis.translateString()` 使用 `en-ueb-g2.utb` 表
2. liblouis 自动处理大小写、数字标志符、缩写规则
3. 输出 Unicode Braille 字符

### 3.3 LaTeX 数学 → Nemeth Code（MathConv）

数学片段支持 `$...$`、`$$...$$`、`\(...\)`、`\[...\]` 及已有公式环境识别。实现采用“分词 → 结构树 → Nemeth 状态转写”的流程，依据 BANA Nemeth 2022 的明确支持范围。

- 数字使用下位点，按上下文决定数字指示符；比较符两侧留空。
- 上标为 ⠘（dots 45），下标为 ⠰（dots 56）；处理数字下标省写、同时上下标顺序、嵌套层级和基线恢复。
- 分数为 ⠹ / ⠌ / ⠼，根式为 ⠜ / ⠻；嵌套结构标明阶数。
- 保留希腊字母和明确字体类别，处理函数名、撇号与括号列表。
- 依据行内/独立公式及 `\limits` / `\nolimits` 选择上下限位置；总转换入口加数学切换符。
- 未支持或格式错误的完整公式返回 ⠿ 并记录原因。

支持范围、条款及局限见 [数学转写说明](math-braille.md)。矩阵、多行对齐、连分数空间排版及专业公式断行尚未实现。

### 3.4 内容类型识别

- 逐行扫描，区分三个通道：**中文区间**、**英文区间**、**$LaTeX$ 数学区间**
- 数学区间的优先级最高（一旦匹配 `$` 分隔符，立即转入 MathConv）
- 同一类型连续块合并为一个批次转换，结果按原文顺序拼接

## 四、UI 布局

```
┌──────────────────────────────────────────────────┐
│  📂 打开文件        第 3 / 42 页    ⟲ 重新载入    │
├──────────────────────────────────────────────────┤
│                                                  │
│  ⠓⠑⠇⠇⠕   ⠰⠉⠐⠁  ⠛⠕  ⠎⠚⠊⠑      │
│  ⠠⠉⠕⠝⠞⠑⠝⠞  ⠞⠑⠇⠇⠑⠗       │
│  ⠠⠝⠑⠭⠞  ⠏⠁⠛⠑       │
│                                                  │
│  ← 上一页                    下一页 →            │
├──────────────────────────────────────────────────┤
│  example.txt  |  共 42 页  |  当前: 第 3 页      │
└──────────────────────────────────────────────────┘
```

**交互：**
- 打开文件：QFileDialog 或窗口拖入
- 翻页：按键 ←/→，或底部按钮
- 窗口缩放 → 画布列数变化 → 自动重排分页
- 每行 Braille 字符数：根据窗口宽度自适应（默认 ~40 字）

**文件格式支持：**
- 当前支持：UTF-8 `.txt`、`.md`、`.markdown`、`.rst`
- LaTeX 源文件：`.tex`、`.ltx`（按文本读取，数学片段进入 Nemeth 转换）
- 未来可扩展：`.docx`、`.epub`、`.srt` 等

## 五、分页机制

```
Paginator(braille_chars: list[str], chars_per_line: int, lines_per_page: int)
  → list[list[list[str]]]  # 页码 → 行 → Braille 字符
```

- Braille 字符序列按行容量切分行，再按页容量切分页
- 窗口尺寸变化时重新计算 `chars_per_line` 并重排
- 翻页保持当前段落的视觉连续性

## 六、边界情况处理

| 场景 | 处理方式 |
|------|----------|
| 空文件 | 提示「文件为空」，显示空白画布 |
| 非 UTF-8 | chardet 自动检测编码；失败则让用户选择 |
| 超大文件 (>10MB) | 异步读取 + 进度提示，不阻塞 UI |
| 不支持字符 | 替换为 ⠿（占位符），状态栏提示 |
| 纯英文文件 | 自动识别，全程走 EnglishConv，结果正确 |
| 窗口缩放 | 画布重排 + 重新分页，保持当前阅读位置 |
| liblouis 表缺失 | 降级仅用英文规则，记录日志警告 |
| 打包后资源路径 | 通过 sys._MEIPASS 处理路径兼容 |
| 数学表达式内的中英文 | 公式内文本命令尚不支持，返回复核标记并记录原因 |
| 非标准/自定义 LaTeX 宏 | 降级为 ⠿ 盲文占位符，避免输出非盲文字符 |

## 七、项目文件结构

```
Braille Conversion/
├── main.py                    # 入口
├── requirements.txt           # 依赖
├── src/
│   ├── __init__.py
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py
│   │   ├── braille_canvas.py
│   │   └── file_dialog.py
│   ├── converter/
│   │   ├── __init__.py
│   │   ├── braille_converter.py
│   │   ├── chinese_conv.py
│   │   ├── english_conv.py
│   │   └── math_conv.py          # LaTeX → Nemeth Code
│   └── paginator.py
├── resources/
│   └── liblouis_tables/
│       ├── en-ueb-g2.utb
│       └── nemeth.utb            # Nemeth Code 对照表
├── tests/
│   ├── test_chinese_conv.py
│   ├── test_english_conv.py
│   ├── test_math_conv.py
│   ├── test_paginator.py
│   └── test_braille_converter.py
├── docs/superpowers/specs/
│   └── 2026-06-20-braille-converter-design.md
└── braille-converter.spec     # PyInstaller spec 文件
```

## 八、未来扩展预留

- **硬件驱动层**：预留 `src/driver/` 目录，后续通过 pyserial/pyusb 与盲文点显器通信。Converter 模块的输出可以直接喂给硬件驱动。
- **更多文件格式**：通过注册文件解析器模式扩展 .docx/.epub 等
- **命令行模式**：`braille-converter --input file.txt --output braille.txt`（converter 模块已不依赖 GUI）
- **Emoji / 代码**：后续可以映射为 Braille 专用符号

---

> 设计版本：v1.0
> 日期：2026-06-20
