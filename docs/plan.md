# Braille Converter 实现计划

> 基于设计文档 `docs/superpowers/specs/2026-06-20-braille-converter-design.md`
> 日期：2026-07-27

## 阶段概览

| 阶段 | 内容 | 预估文件数 |
|------|------|-----------|
| **Phase 1** | 项目骨架 + 转换核心 | 8 文件 |
| **Phase 2** | GUI 界面 | 4 文件 |
| **Phase 3** | 测试 + 集成 | 6 文件 |
| **Phase 4** | 入口 + 打包 + 收尾 | 3 文件 |

---

## Phase 1：项目骨架 + 转换核心（不依赖 GUI）

### 任务 1.1：创建项目目录结构和配置文件
- 创建目录：`src/`、`src/gui/`、`src/converter/`、`tests/`、`resources/liblouis_tables/`
- 创建 `src/__init__.py`、`src/gui/__init__.py`、`src/converter/__init__.py`
- 创建 `requirements.txt`（依赖：PySide6、pypinyin>=0.55.0、liblouis、chardet、pytest）
- 创建 `tests/__init__.py`

### 任务 1.2：实现中文 → 盲文（chinese_conv.py）
- 用 pypinyin 将汉字转拼音 + 声调
- 声母/韵母映射到 Braille 点阵（pypinyin 内置 `Style.BRAILLE_MAINLAND` / `Style.BRAILLE_MAINLAND_TONE`）
- 支持无调/带调两种模式
- 函数签名：`chinese_to_braille(text: str, toned: bool = False) -> list[str]`

### 任务 1.3：实现英文 → 盲文 Grade 2（english_conv.py）
- 调用 `louis.translateString()` 使用 `en-ueb-g2.utb` 表
- 处理 liblouis 表缺失的降级（弹窗警告 + 仅基本英文字母映射）
- 函数签名：`english_to_braille(text: str) -> list[str]`

### 任务 1.4：实现数学 LaTeX → Nemeth Code（math_conv.py）
- 自研转换器，基于 Nemeth Code 规则表
- 正则匹配 `$...$`（行内）和 `$$...$$`（独立段落）
- 支持：分式 `\frac{}`、上下标 `^` `_`、求和 `\sum`、积分 `\int`、根号 `\sqrt`、希腊字母
- 未知 LaTeX 命令保留原文作为 fallback
- 函数签名：`latex_to_nemeth(latex_str: str) -> str`

### 任务 1.5：实现总调度器（braille_converter.py）
- 逐行扫描，区分中文区间 / 英文区间 / LaTeX 数学区间
- 数学优先级最高（一旦匹配 `$` 立即转入 MathConv）
- 同一类型连续块合并为一个批次转换
- 结果按原文顺序拼接
- 不支持字符替换为 ⠿ 占位符
- 函数签名：`convert_text(text: str) -> list[str]`

### 任务 1.6：实现分页器（paginator.py）
- 输入：Braille 字符数组、每行字数(列数)、每页行数
- 输出：`list[list[list[str]]]` — 页码 → 行 → Braille 字符
- 自动分行、分页
- 窗口缩放时重新计算列数并重排
- 函数签名：`Paginator(braille_chars: list[str], chars_per_line: int, lines_per_page: int) -> list[list[list[str]]]`

---

## Phase 2：GUI 界面

### 任务 2.1：实现主窗口（main_window.py）
- QMainWindow，布局：顶部工具栏 → 中央 BrailleCanvas → 底部状态栏
- 工具栏：打开文件按钮、页码显示（第 X / Y 页）、重新载入按钮
- 状态栏：当前文件名、总页数、当前页码
- 键盘事件：←/→ 翻页
- 文件拖入支持（drag & drop）
- 空文件提示「文件为空」
- 超大文件 (>10MB) 异步读取 + 进度提示

### 任务 2.2：实现 Braille 点阵画布（braille_canvas.py）
- 继承 QWidget，用 QPainter 渲染盲文点阵
- 每个盲文字符渲染为 2×3 点阵（圆点）
- 自适应窗口宽度 → 计算每行可容纳字符数 → 触发重排
- 上下翻页保持视觉连续性

### 任务 2.3：实现文件对话框（file_dialog.py）
- QFileDialog 打开 UTF-8 .txt 文件
- 窗口拖入文件
- 非 UTF-8 编码自动检测（chardet）+ 用户选择
- 函数签名：`open_file_dialog(parent) -> str | None`

---

## Phase 3：测试

### 任务 3.1：中文转换测试（test_chinese_conv.py）
- 纯中文、中英混合、带声调/无调、空字符串、特殊字符
- 预期输出 Braille 点阵编码

### 任务 3.2：英文转换测试（test_english_conv.py）
- 纯英文句子、缩写、数字、大写开头
- liblouis 表缺失时的降级行为

### 任务 3.3：数学转换测试（test_math_conv.py）
- 行内 `$...$`、独立 `$$...$$`、分式、上下标、求和、积分、根号、希腊字母
- 未知 LaTeX 命令的 fallback

### 任务 3.4：分页器测试（test_paginator.py）
- 正常分页、边界（不足一页、恰好一页）、空输入
- 列数变化重排

### 任务 3.5：总调度器集成测试（test_braille_converter.py）
- 中英混合文本、含数学公式、纯中文、纯英文、空文件
- 混合内容按原文顺序拼接

---

## Phase 4：入口 + 打包 + 收尾

### 任务 4.1：主入口（main.py）
- 创建 QApplication，实例化 MainWindow，启动事件循环
- 打包兼容路径处理（`sys._MEIPASS`）

### 任务 4.2：打包配置（braille-converter.spec）
- PyInstaller `--onefile --windowed` 模式
- 包含 liblouis 表文件作为 data
- 资源路径处理

### 任务 4.3：最终验证
- 运行全部测试
- 验证 `python main.py` 可正常启动
- 打开示例 .txt 文件验证转换

---

## 依赖关系

```
Phase 1 (转换核心)
   ├── 任务 1.1 (骨架)
   ├── 任务 1.2 (中文转换) ──┐
   ├── 任务 1.3 (英文转换) ──┤
   ├── 任务 1.4 (数学转换) ──┤
   │                        ├──→ 任务 1.5 (调度器) → 任务 1.6 (分页器)
   └────────────────────────┘
                                       ↓
Phase 2 (GUI) ──── 任务 2.1-2.3（依赖 Phase 1）
                                       ↓
Phase 3 (测试) ──── 任务 3.1-3.5（依赖 Phase 1 & 2）
                                       ↓
Phase 4 (入口 & 打包) ──── 依赖全部完成
```
