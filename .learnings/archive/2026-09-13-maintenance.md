# 经验库维护归档 · 2026-09-13

`maintain-learnings` 维护记录。本次审计（`audit_learnings.py`）中 `880-wrongbook` 为最高频热点（活跃记录 6 条，多数与「Obsidian 公式渲染防线」同族）。

统一动作：把三条防线落到**可执行机制**——事实源 lint、陈旧产物检测、skill 必做校验步骤；机制修好并验证后，归档下列记录，只在 `RULES.md` 保留简短铁律。

## 机制修复（本次新增/收紧）

| 机制 | 位置 | 作用 |
| --- | --- | --- |
| `lint_source(subject)` | `scripts/lint_content.py` | 校验两个事实源索引每道题 `text`/`answer`/`solution`，报 `题号.字段`；先于产物校验 |
| `wrong_book.py --check [--all]` | `scripts/wrong_book.py` | 内存渲染与盘面产物比对（忽略 `updated:`），陈旧则打印 diff 并退出码 1 |
| 「校验（必做）」步骤 4 | `.claude/skills/880-wrongbook/SKILL.md` | 修事实源/生成器后对全部科目重生成 + 两条命令跑绿，禁止只重建被点名的条目 |

---

## 归档记录

### 1. 事实源残留字面 `\n` 与错位 `$$`，已提交的错题本一直是坏的

- **原记录**：`.learnings/ERRORS.md`（2026-09-13）。用户报 `workspace/wrong-book/错题本.md` 渲染坏；HEAD 第 584 行整段解析糊成一行（字面 `\n`，全本 32 处），独立公式块无法成对识别。根因两类：`question-index.json` 20 条字面 `\n`（323 处）+ 11 条 `$$` 截断；`linear-algebra-question-index.json` 7 条题界 `$$` 错位。坏数据在事实源里，而严格校验只在生成时把关，盘面旧文件无人重写。
- **修复路径**（机制）：
  - 事实源方向 → `lint_content.py::lint_source()`：两个索引逐题跑与产物同一个 `lint_math`，坏公式/字面 `\n`/错位 `$$` 在**源头**就被拦住，报 `题号.字段`；
  - 陈旧产物方向 → `wrong_book.py --check --all`：渲染内存副本与盘面比对（忽略 `updated:`），陈旧即 diff + 退出码 1；
  - 流程方向 → `880-wrongbook` skill 步骤 4 固定跑上述两条命令，且要求「对全部科目重生成」。
  - 数据侧另已按只读源修正两索引（本次维护不重复）。
- **验证方式**：`lint_source` 5 例负样本（字面 `\n`、`$` 不成对、行内 `\(...\)`、独立 `\[...\]`、控制字符 `\x0c`）全部捕获并给出 `qid.field`；干净样本无误报；真实运行两索引全绿退出 0。`--check` 双向负样本（盘面多一行 → 7 行 diff；改在错题本内的题的事实源 `solution` → 9 行 diff）均检出，干净态通过，`--list-states` 回归正常。
- **处理结果**：已归档；机制生效。

### 2. 新解析使用旧式公式定界符

- **原记录**：`.learnings/ERRORS.md`（2026-09-12）。新增解析用 `\[...\]`，脚本写入中出现 `\x0c`，错题本渲染异常。根因：生成前没有对索引解析做 Obsidian 定界符与控制字符前置校验。
- **修复路径**：`scripts/wrong_book.py::validate_solution_text` 写入前拒绝控制字符、独立式 `\[...\]`、转义形式，行内 `\(...\)` 由 `lib880.normalize_math_delimiters` 归一为 `$...$`；`880-wrongbook` skill 步骤 4 把「重建后跑 lint」写成固定步骤。
- **验证方式**：`validate_solution_text` 在 `build()` 中对每道题执行；`lint_content.py` 全绿（含事实源）。
- **处理结果**：已归档；机制生效。

### 3. 两道闸门各存一份正则，行内 `\(...\)` 双双漏检

- **原记录**：`.learnings/ERRORS.md`（2026-09-12）。`wrong_book.py` 与 `lint_content.py` 各存一份只查独立式 `\[...\]` 的正则，行内 `\(...\)`（127 处 / 3 道题）同时通过两道闸门，lint 报「全部通过」但渲染仍是裸 `\(x\)`。根因：校验逻辑复制而非共享。
- **修复路径**：判据收敛到 `scripts/lib880.py` 单一出处（`CONTROL_CHAR_RE` / `LEGACY_INLINE_RE` / `LEGACY_DISPLAY_RE`），渲染层与 lint 共用；本轮新增的 `lint_source` 继续复用同一份判据（不再另写正则）。
- **验证方式**：`lint_content.py` 导入 `lib880` 常量、未自带副本；事实源与产物走同一 `lint_math`。
- **处理结果**：已归档；机制生效。

### 4. 严格校验只管新写入，不修盘面上的陈旧产物

- **原记录**：`.learnings/LEARNINGS.md`（2026-09-13，best_practice/high）。生成器写入前校验只拦新写入，已提交产物是更早、更宽松代码路径写出的旧内容；报障时不能因「生成器现在有校验」就假定产物正确。
- **修复路径**：`wrong_book.py --check [--all]` 把「盘面是否已跟上事实源」变成可执行检测（忽略 `updated:`，陈旧退出码 1）；skill 步骤 4 要求「先事实源后产物」两条命令跑绿。
- **验证方式**：干净态通过、双向负样本检出（见记录 1 的验证）。
- **处理结果**：已归档；机制生效。

### 5. 解析写入前的 Obsidian 公式防线

- **原记录**：`.learnings/LEARNINGS.md`（2026-09-12，correction|best_practice）。独立公式统一 `$$...$$`，生成前拒绝 `\[...\]` 与控制字符。
- **修复路径**：由记录 2 的写入前校验承接；本轮补上「事实源也要先绿」——`lint_source` 让坏数据在源头暴露。skill 步骤 4 固化。
- **验证方式**：skill 步骤 4 两条命令可将事实源与产物一起跑绿。
- **处理结果**：已归档；机制生效。

### 6. 坏内容判据要单一出处

- **原记录**：`.learnings/LEARNINGS.md`（2026-09-12，best_practice/high）。同一类判据被渲染层与 lint 各实现一遍时会各自漏掉新形式，应收敛到 `lib880`。
- **修复路径**：判据已集中 `lib880`；本轮 `lint_content.py` 的 `lint_source` 与 `lint_file` 共用同一 `lint_math`，未新增第二处实现。
- **验证方式**：`lint_content.py` 仅 `import lib880` 引用常量，无本地正则副本。
- **处理结果**：已归档；机制生效。

---

## 未归档（继续观察）

- `.learnings/ERRORS.md` 中「880-wrongbook：新解析使用旧式公式定界符 / 两道闸门各存一份正则」两条本次已归档，其余 skill（`880-paper` / `880-analysis` / `obsidian-markdown` 等）的记录未在本轮热点范围内，保留活跃。
