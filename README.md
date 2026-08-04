# 880 考研数学习题系统

基于 **李林880 · 数二高数篇**（做题本 + 解析册）的个人做题系统：按真题模式拼卷、手动判分、整理错题本、补弱加权抽题、进度预览。

详细实用文档请看[[docs/使用指南.md]]

## 对话式命令

| 你想做什么 | 直接说 | 实际执行 |
| --- | --- | --- |
| 拼卷 | “拼张卷” | `python3 scripts/make_paper.py` |
| 判分 | “判分卡填好了”（先在判分卡打勾） | `python3 scripts/grade.py --sheet workspace/papers/paper-01/判分卡-01.md` |
| 错题本 | “看错题本” / “重练了第X题会了” | `python3 scripts/wrong_book.py` |
| 预览进度 | “看进度” | `python3 scripts/progress.py` |
| 重建索引 | “入库” | `python3 scripts/prepare_sections.py` + 提取 Workflow + `python3 scripts/merge_extraction.py --journal <jsonl>` |

> Windows 下把 `python3` 换成 `py -3`（如 `py -3 scripts/make_paper.py`），或 `make paper PYTHON='py -3'`。

## 平台兼容（Linux / macOS / Windows）

- **解释器**：命令统一写 `python3`（Linux/macOS）；Windows 用 `py -3` 替代。
- **Makefile**：提供 `make paper` / `make grade` / `make wrongbook` / `make progress` / `make lint` / `make index-check`，解释器可用 `PYTHON ?= python3` 覆盖。
- **输出编码**：脚本统一把 stdout/stderr 重配为 UTF-8，Windows 控制台或非 UTF-8 locale 下打印中文不会报 `UnicodeEncodeError`。
- **判分**：优先 `grade.py --sheet <判分卡>` 读取勾选（paper_id 自动从卡片 frontmatter 获取）；JSON 兜底用 `--grading-file <UTF-8 文件>` 从文件读判分，避免 cmd/PowerShell 引号问题；`--grading` 也容忍外层单/双引号。
- **换行**：`.gitattributes` 强制 `.sh/.py/.md` 等文本文件在仓库与检出时均用 LF，防止 Windows `autocrlf` 把脚本转坏。
- **质量检查**：`make test` 运行不触碰真实学习记录的核心规则与安全生成测试；`make index-check` 严格阻断待复核索引，`make index-check-structure` 只校验索引结构。
- **Shell 工具**（`.claude/scripts/*.sh`、hooks）：仅用于 Claude Code 钩子/插件，需要 bash；Windows 请用 Git Bash 或 WSL 运行。
- **技能软链**：`.claude/skills/*` 下有 41 个软链指向 `.agents/skills/*`（去重设计）。Windows 上克隆后需 `git config core.symlinks true` 并开启系统「开发者模式」才能正确还原；否则这些软链会退化为普通文本文件。

## 卷子规格（真题模式）

- 选择题 10×5 分 + 填空题 6×5 分 + 解答题 6 题 ≈ 150 分 / 180 分钟
- 章节按真题考频配额，难度 基础:综合:拓展 = 4:5:1（拓展可关）
- 允许重复抽题，加权随机：做过降权、错题升权、弱章节升权（补弱）

## 判分五态

`对` / `错` / `不会` / `半会` / `粗心` —— `不会` `半会` 进错题本重点，`错` `粗心` 轻标记；弱点分 = 章节加权错误率（时间衰减）。

## 数据与产物

```
880/                           题库源（做题本 + 解析册，只读）
workspace/
├── schema.yaml                核心配置（配额/权重/判分口径）
├── question-index.json        题目索引（题目↔答案，LLM 按内容对齐提取）
├── papers/paper-XX/卷子-XX.md    卷子 + 答题卡 + 判分表
├── papers/paper-XX/卷子-XX-答案.md  独立答案卷（含解析）
├── papers/paper-XX/判分卡-XX.md  勾选判分卡（判分输入）
├── records/attempts.json      判分记录（补弱/错题/进度的唯一输入）
├── records/papers.json        卷子快照
├── wrong-book/错题本.md        按章节，含复习状态
├── preview/进度总览.md         全局进度与弱点排行
└── workflow-runs/             工作流状态
```

## 说明

- 答案全部来自解析册，**不做 AI 生成**（见 `docs/adr/0001`）；两个源文件有 OCR 标记丢失/合并问题，入库时用 LLM 按内容对齐并逐个校验。
- 当前只含高数；数据模型预留 `科目→章节` 两级，线代题库可随时加入。
- 生成的 Markdown 兼容 Obsidian，可直接用 Obsidian 打开本仓库浏览。
- 指定已存在的卷号会被拒绝，防止覆盖答题卡和学习记录；只有尚未判分的卷子可用 `--replace-ungraded` 显式重生成。
