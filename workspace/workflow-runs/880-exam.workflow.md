---
workflow_id: 880-exam
task: 880 习题系统做题流程
created: 2026-08-11
updated: 2026-10-20
last_updated: "2026-10-20"
current_phase: done
current_status: complete
blocked_reason: ""
---

# 880-exam 状态

> [P0] ✅ 已完成 {complete}
> [P1] ✅ 已完成 {complete}
> [P2] ✅ 已完成 {complete}
> [P3] ✅ 已完成 {complete}
> [P4] ✅ 已完成 {complete}

## 当前上下文

- 最近卷子：[[workspace/papers/paper-06/卷子-06.md|paper-06]]（2026-10-20 判完 22/22 → 54.5/150 · 36.3%，选32.5/50 · 填10/30 · 解12/70）；本卷最弱：第一章 函数、极限、连续（失分22/27）、第五章 二重积分（20/25）、第三章 一元函数积分学（19.5/32）
- 最近线代卷：[[workspace/papers/la-paper-05/线代卷子-05.md|la-paper-05]]（2026-10-11 拼好，待做；选10 · 填6 · 解6）
- 上一张已判高数卷：[[workspace/papers/paper-05/卷子-05.md|paper-05]]（2026-10-10 判完 22/22 → 85/150 · 56.7%，选37.5/50 · 填17.5/30 · 解30/70）；本卷最弱：第五章 二重积分（失分29/44）、第三章 一元函数积分学（20/30）、第一章（17/27）
- 上一张已判线代卷：[[workspace/papers/la-paper-04/线代卷子-04.md|la-paper-04]]（2026-10-11 判完 22/22 → 56.5/150 · 37.7%，选15/50 · 填17.5/30 · 解24/70）；本卷最弱：第十二章 二次型（失分37/47）、第十章 线性方程组（27/27）、第十一章 相似矩阵（19.5/44）
- 更早一张已判高数卷：[[workspace/papers/paper-04/卷子-04.md|paper-04]]（49.5/150 · 33.0%；选10/50 · 填12.5/30 · 解22/70）
- 已判完的线代卷：[[workspace/papers/la-paper-02/线代卷子-02.md|la-paper-02]]（132/150 · 88.0%，2026-09-28 补判解答题第 2 题）
- 欠账（抽到过未判）：高数 0 题 · 线代 0 题
- 累计：高数 已判 106 · 未做 512；线代 已判 82 · 未做 229
- 错题本待复习：高数 15 道（重点 9 · 轻标记 6；已掌握 55）· 线代 22 道（重点 12 · 轻标记 10；已掌握 31）
- 最近一轮复习见 [[错题复习-06.workflow.md]]（2026-10-01 提前结束：实练 4/7 题全对，转已掌握 4 题）；上一轮见 [[错题复习-05.workflow.md]]（6 题 对 2 · 半会 2 · 不会 1 · 粗心 1）
- 待办方向：la-paper-05 已拼好待做；做完后勾判分卡判分。下一轮复习重点题——高数 `gs-c05-comprehensive-fill-002`，线代 `la-c11-comprehensive-solution-014`、`la-c12-comprehensive-solution-014`
- 备注：得分与弱点分析、错因分析（对话式归因→analysis.json→错题本渲染）已落地；外部错题关联 46 条（一对多）。

## 异常记录

| 时间 | 阶段 | 问题描述 | 处理方式 |
|------|------|---------|---------|
| 2026-10-01 | 判分核对 | 高数错题本待复习 13→18 只 +5（新增非对 6 题），`gs-c01-basic-choice-013` 从清单消失（状态仍为未复习） | 核为**设计行为**而非缺陷：`build_wrong_lists` 仅收录「最近判分非『对』」的题（`tests/test_core.py::test_mastered_redo_is_preserved_in_archive` 覆盖），故待复习集合 ≡ 进度总览「非『对』」计数（高数 18、线代 9 两处一致）；该题判分记录仍在 `attempts.json`，再次判错会自动回到清单。已掌握归档是该过滤的唯一例外 |
| 2026-10-11 | 拼卷产物 | 卷子-06 第 6 题（`gs-c02-comprehensive-choice-024`）题干末句「…满足 $S_2>S_1>S_3$，则下列选项正确的是（）.」在卷子上打印两遍 | 三层定位：**非生成器缺陷**——原文源 `880/【A4紧凑版】…/block_list.json` 第 27 页 idx 3/4 各含一次该句（OCR 重复），一路流经 content_list → full.md → 索引 → 卷子/答案卷。全库 618 题仅此一例。按既有「覆盖层」模式新增 `workspace/records/text-overrides.json`（题干覆盖，渲染时替换、重建索引不丢），已 `--rebuild paper-06` 重刷卷子与答案卷；`lint_content.py` 增 `lint_text_overrides`（公式判据 + qid 必须命中题库，防题号写错静默空转）；`tests/test_core.py` 增 3 例回归 |
| 2026-10-11 | 拼卷产物 | 用户报「渲染失败了」（[[workspace/papers/paper-06/卷子-06.md|卷子-06]]）。三类**行内格式**缺陷叠加：① 选择题4 选项行 `A. M<N<P B. N<M<P …` 的裸 `<`（同行无 `>`）使 Live Preview 从该行起到文末整段退化为原始 Markdown；② 解答题4 题干「设 $$…$$，求 $$…$$」的**行内** `$$` 渲成 display:block 数学块、把段落撑破；③ 选择题6 示意图用相对路径 `images/<hash>.jpg`，产物目录解析不到（裂图）。全库波及 paper-01/03/04/05 卷子与答案卷、两本错题本（81 处行内 `$$`，多处裸 `<`） | 三层定位（盘面 `git show HEAD:<产物>` → 事实源 → 生成器）后定为**渲染层归一**修复，事实源只读原貌保留：`lib880.normalize_math_delimiters` 增行内 `$$…$$`→`$…$`（`INLINE_DOLLAR_PAIR_RE`，只作用于非独立行）；新增 `lib880.escape_bare_angle_brackets`，把公式区外（行内 `$…$`、独立 `$$` 块、行内代码之外）的这类 `<` 转义为 `\<`——**不可用 HTML 实体 `&lt;`**，实测实时预览不解码实体、两边显示不一致；新增 `lib880.RELATIVE_IMAGE_RE`，`images/<hash>.jpg` → `![[<hash>.jpg]]`（哈希名全库唯一，源图目录在 vault 内可跨目录解析）。三者合并进同一净化链，新增 `prepare_stem_text`，`prepare_solution_text` / `markdown_math_answer` 一同并入，`make_paper.py`（卷子+答案卷题干）与 `wrong_book.py` 题干改走它。`lint_content.py` 增三个**产物侧**判据（行内 `$$`、未转义 `<`、相对图片路径），判据取自 lib880 同一函数/正则、不另存副本；解析根补收 `880/**` 源图片，避免正确的 `![[<hash>.jpg]]` 被误判死链（源头侧不判：只读原文按设计保留原貌，否则 lint 永远红）。`tests/test_core.py` 增 6 例回归（31 例全绿），规则文档 `obsidian-content.md` 同步三类写法。**重刷范围**：`--rebuild-answers all` 只动答案卷，卷子必须逐卷 `--rebuild <paper_id>`（两个科目都要），再 `wrong_book.py --all`；全部重刷后 `lint_content.py` 归零，并用阅读视图/实时预览截图复核 paper-06 |

