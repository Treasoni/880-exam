# 2026-10-11 维护归档

本次维护对象：2026-09-15 / 2026-10-11 的 3 条 ERRORS 族记录 + 2026-10-11 的 3 条 LEARNINGS 记录。
归档前先逐条核对「源头修复是否已落地」，再用代码守卫补上最后一个未落实项。

---

## 1. ERRORS：核验前提未核实族（4 次：查错对象 / 用错工具契约 / 拿转述当事实 / 隔离作用域）

**原记录摘要**：取事实源条目硬编码题号（取回错的题）、探针不符 `lib880.split_answer_sheet` 契约（块不含题干行）、拿上一轮转述当事实（`attempts.json` 实际 0 条）、`patch.multiple` 漏挂 `SOLUTION_OVERRIDES_PATH` 导致测试跑在真实 vault。

**修复路径**：
- 取条目从卷面反查 → `RULES.md`「取事实源条目从卷面反查」。
- 用库函数前读契约 → `RULES.md`「用库函数前先读它的契约」。
- 断言冲突前读对方盘面值 → `RULES.md`「断言冲突前先读对方盘面值」。
- 测试隔离 → `RULES.md`「测试补丁要覆盖全部写盘目标」+ **本次新增代码守卫**：`tests/test_core.py` 的 `setUpModule` / `tearDownModule` 对 `workspace/` 全量指纹，越界写入即报错（此前该条在 ERRORS 里标注「未落实：尚无代码级守卫」）。

**验证方式**：
- 正样本 `python3 -m unittest tests.test_core` → `Ran 32 tests ... OK`（守卫静默）。
- 负样本（临时脚本，守卫指向 `/tmp` 伪 vault，写入第二个文件）→ 守卫抛 `AssertionError` 并点名 `- b.md`。未触碰真实 vault。

**处理结果**：已归档。4 条内核均在 RULES，第 4 条（隔离）由代码守卫兜底。

---

## 2. ERRORS：写盘前提未体检族（3 次：并发会话竞写 / 渲染结论未实测 / lint 判据近似）

**原记录摘要**：压缩重启后不查 `git status`/`ListAgents` 就改同库 peer 已在改的文件；把 `&lt;` 当正解（未在 vault 实测，实测应为 `\<`）；`inline_dollar_lines` 用近似条件把合法整行公式判成错（含用户手写内容）。

**修复路径**：
- 动手前体检 / 硬停信号 → `RULES.md`「动手前先体检」「「file modified on disk」是硬停信号」。
- 渲染结论实测 + oracle 判据 → `RULES.md`「渲染结论先在 vault 实测」「产线判据以渲染层本体为 oracle」「渲染判定用 oracle，不用截图反推」；`lint_content.inline_dollar_lines` / `bare_angle_lines` 均已改为调用 `lib880` 渲染层函数比对（非近似正则）。
- 裸 `<` 方案定案 → `.claude/rules/common/obsidian-content.md` 与 `lib880.escape_bare_angle_brackets` 统一为 `\<`。

**验证方式**：`python3 scripts/lint_content.py` 全绿；`grep` 确认 `lint_content.py` 的两处判据都走 `lib880.normalize_math_delimiters` / `escape_bare_angle_brackets` 本体。

**处理结果**：已归档。**残留**：无机制阻止两会话同时开工（工作流单 `current_phase` 表达不了「谁写哪些文件」），仍靠 `RULES.md`「并发会话按文件切」自觉执行——此项属规则层，不再留在活跃 ERRORS，但每次动手前仍须体检。

---

## 3. ERRORS：工具契约按子命令/API 分叉族（4 次：`screenshot` 的 path / `--all` 作用域 / `getMode` 粒度 / 自动提交中间态）

**原记录摘要**：`dev:screenshot path=` 是输出路径（覆盖了源笔记）、`wrong_book.py --all` 写入模式只刷默认科目（线代陈旧）、`view.getMode()==="source"` 区分不了源码模式与实时预览、自动提交把临时破坏态提交进 HEAD。

**修复路径**：
- CLI 输入/输出契约 → `RULES.md`「CLI 子命令各自是独立契约」（明写 `open path=` 输入 / `dev:screenshot path=` 输出）。
- 作用域开关 → `RULES.md`「CLI 子命令各自是独立契约」末句（`--all`/`--subject`/`--days` 要 grep 全部分支）+ **源码修复**：`wrong_book.py` 写入路径改为 `targets = 两科 if args.all else [subject]`，回归测试 `test_all_regenerates_both_subjects_but_subject_stays_scoped` 锁死（已喂负样本）。
- 字段粒度 → `RULES.md`「细粒度问题用细粒度字段」。
- 自动提交仓库 → `RULES.md`「自动提交的仓库别留破坏态」。

**验证方式**：`grep -n "targets\|args.all" scripts/wrong_book.py` 确认写入与 `--check`/`--due` 三条分支共用同一 `targets`；回归测试在 32 项中通过。

**处理结果**：已归档。源码 `--all` 与渲染层同族输出点两处均已修。

---

## 4. LEARNINGS：Obsidian 渲染层事实（行内 `$$` 降级边界 / 裸 `<` 转义形式）

**原记录摘要**：行内 `$$…$$` 只在「同行另有正文」时撑破段落；整行 `$$x=1$$` 与引用块 `> $$…$$` 是合法独立块；裸 `<` 转义用 `\<`，不能用 `&lt;`（实时预览不解码实体）。

**修复路径**：`.claude/rules/common/obsidian-content.md`（定界符章节 + 裸 `<` 章节，均写明判据与反例）；实现落在 `lib880.normalize_math_delimiters` / `escape_bare_angle_brackets`；`lint_content.py` 以渲染层为 oracle。

**验证方式**：`lint_content.py` 全绿；`workspace/papers/paper-06/卷子-06.md` 第 4 题选项实测输出 `A. M\<N\<P`（触发本次缺陷的卷子已修复）。

**处理结果**：已归档，内核在 `RULES.md`「公式定界符只认 Obsidian 原生两种」「callout 内的独立公式也算独立块」「产线判据以渲染层本体为 oracle」。

---

## 5. LEARNINGS：验证「Obsidian 会怎么渲染」的三件套

**原记录摘要**：`MarkdownRenderer.render(app, md, el, "", null)` 读 `innerHTML` 精确断言渲染（`mjx-container[display=true]` = 独立公式块）；要验实时预览须显式 `setState({mode:"source", source:false})`；`return` 必须包在 IIFE 内。

**修复路径**：`RULES.md`「渲染判定用 oracle，不用截图反推」「细粒度问题用细粒度字段」。

**验证方式**：本轮无新增，内核已成文；反向依赖见归档 2（`getMode` 陷阱）。

**处理结果**：已归档。

---

## 6. LEARNINGS：渲染层归一化要覆盖同族全部输出点

**原记录摘要**：`wrong_book.py` 待复习条目题干仍拼 `{q['text']}` 原文，而已掌握归档走 `prepare_stem_text(effective_text(...))`——同问两路径口径不一、且待复习条目静默忽略 `text-overrides`。

**修复路径**：源码修复——`scripts/wrong_book.py` 两条路径统一为 `lib880.prepare_stem_text(lib880.effective_text(q, text_overrides))`（现 178 / 244 两行同构）；`RULES.md`「归一化要覆盖同族全部输出点」。

**验证方式**：`grep -n "题干：\|prepare_stem_text" scripts/wrong_book.py` 确认两处同一调用；`python3 scripts/wrong_book.py --check --all` 与事实源一致。

**处理结果**：已归档。当时为**潜在**缺陷（15 条待复习里无题干会被归一改动的题），无产物变更。
