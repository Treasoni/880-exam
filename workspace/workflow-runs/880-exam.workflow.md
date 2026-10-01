---
workflow_id: 880-exam
task: 880 习题系统做题流程
created: 2026-08-11
updated: 2026-10-01
last_updated: "2026-10-01"
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

- 最近卷子：[[workspace/papers/paper-05/卷子-05.md|paper-05]]（2026-09-28 拼好；2026-10-01 **部分判分** 16/22 题 → 55/150 · 36.7%，选37.5/50 · 填17.5/30 · 解答题 6 题未做未判）
- 最近线代卷：[[workspace/papers/la-paper-04/线代卷子-04.md|la-paper-04]]（2026-09-28 拼好，未判分）
- 上一张已判高数卷：[[workspace/papers/paper-04/卷子-04.md|paper-04]]（49.5/150 · 33.0%；选10/50 · 填12.5/30 · 解22/70）；paper-05 本卷最弱：第五章 二重积分（失分29/44）、第三章 一元函数积分学（20/30）、第一章（17/27）
- 已判完的线代卷：[[workspace/papers/la-paper-02/线代卷子-02.md|la-paper-02]]（132/150 · 88.0%，2026-09-28 补判解答题第 2 题）
- 欠账（抽到过未判）：高数 6 题（paper-05 解答题未判）· 线代 19 题（la-paper-04 未判）
- 累计：高数 已判 100 · 未做 512；线代 已判 63 · 未做 229
- 错题本待复习：高数 14 道（重点 1 · 轻标记 13；已掌握 52）· 线代 9 道（重点 2 · 轻标记 7；已掌握 30）
- 最近一轮复习见 [[错题复习-06.workflow.md]]（2026-10-01 提前结束：实练 4/7 题全对，转已掌握 4 题）；上一轮见 [[错题复习-05.workflow.md]]（6 题 对 2 · 半会 2 · 不会 1 · 粗心 1）
- 待办方向：paper-05 解答题 6 题、la-paper-04 整卷判分；下一轮复习重点题——高数 `gs-c05-comprehensive-fill-002`，线代 `la-c11-comprehensive-solution-014`、`la-c12-comprehensive-solution-014`
- 备注：得分与弱点分析、错因分析（对话式归因→analysis.json→错题本渲染）已落地；外部错题关联 46 条（一对多）。

## 异常记录

| 时间 | 阶段 | 问题描述 | 处理方式 |
|------|------|---------|---------|
| 2026-10-01 | 判分核对 | 高数错题本待复习 13→18 只 +5（新增非对 6 题），`gs-c01-basic-choice-013` 从清单消失（状态仍为未复习） | 核为**设计行为**而非缺陷：`build_wrong_lists` 仅收录「最近判分非『对』」的题（`tests/test_core.py::test_mastered_redo_is_preserved_in_archive` 覆盖），故待复习集合 ≡ 进度总览「非『对』」计数（高数 18、线代 9 两处一致）；该题判分记录仍在 `attempts.json`，再次判错会自动回到清单。已掌握归档是该过滤的唯一例外 |

