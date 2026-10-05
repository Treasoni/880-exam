---
name: 880-retest
description: 回炉（间隔复习）——定期从已掌握归档抽查题目，做错退回待复习。触发词：回炉、间隔复习、抽查、复习已掌握、已掌握重审、回炉复习。
---

# 回炉（间隔复习）

已掌握题不会自动复现：错题本只在**待复习**集合里抽题，归档意味着"毕业"。但"毕业"是一次性判定，之后无人复核——本技能按间隔把已掌握题拉回来抽查，**做错即退回待复习**，做对则刷新时间、重新归档。

判定与落库都由 `scripts/wrong_book.py` 提供（`--due` / `--retest` / `--record`），本技能负责挑题、呈现、记录与校验。

> [!warning] 只管 880
> 本技能覆盖 880 两科（`--subject high-math` 高数 / `--subject linear-algebra` 线代）。**真题**（数一/数二/数三）是独立体系，其已掌握题的回炉走 `zhenti-wrong`（`zhenti_wrong_book.py --due/--redo/--record`），不要混入 880（见 `docs/adr/0006-zhenti-system-independent-of-880.md`）。

## 什么时候回炉

- 用户说"回炉""间隔复习""抽查一下已掌握的题""复习已掌握"。
- 距上次掌握已有段时间（默认门槛 **30 天**，可用 `--days N` 调整；`--days 0` = 全部已掌握）。
- 一轮错题复习（`错题复习-XX`）收尾后，顺手抽几道归档题复查。

## 步骤

1. **列出到期题**：
   ```
   python3 scripts/wrong_book.py --due                 # 高数，≥30 天
   python3 scripts/wrong_book.py --due --all           # 高数 + 线代
   python3 scripts/wrong_book.py --due --days 0        # 全部已掌握
   ```
   输出按"逾期天数降序"排（越久越优先），每行给 qid/章节题型题号/难度/已掌握日期/天数。

2. **挑题并给题干**（隐去答案与解析）：
   ```
   python3 scripts/wrong_book.py --retest <qid> [<qid> ...]
   ```
   把题干读给用户，让用户**独立重做**（这一步的关键是"没有答案在眼前"）。一轮建议 3–6 题。

3. **记录结果**（用户报完判分态后）：
   ```
   python3 scripts/wrong_book.py --record <qid>=<对|错|不会|半会|粗心> [<qid>=... ...]
   ```
   - 落库一笔 `note="回炉"` 的判分记录，并联动复习状态：**对 → 已掌握（刷新时间，重新归档）；非对 → 已掌握退回未复习**；
   - 自动重生成错题本，并同步刷新进度总览（回炉会改变"非对"计数）。
   - 幂等：同日同题同态重复记录不会叠加。

4. **校验（必做，两步都要绿）**：
   ```
   python3 scripts/lint_content.py                  # 先事实源、后产物
   python3 scripts/wrong_book.py --check --all      # 盘面产物是否跟上事实源
   ```
   Windows 把 `python3` 换成 `py -3`（或 `make retest PYTHON='py -3'`）。

## 语义与边界

- **退回的是"已掌握"，不是删除**：非对只把状态退回 `未复习`，题重新进入待复习清单，错因与解析全部保留。
- **做对不降级**：做对只是刷新 `updated`，题留在归档；下次到期才再抽到。
- **不自动判定**：判分态由用户报告，`--record` 只落库，不替用户猜对错。
- **一轮别贪多**：归档题多（高数数十道），按逾期天数优先，一次 3–6 题，覆盖最久未复习的。
- 若某题其实不在归档（仍是待复习）：用 `880-wrongbook` 的 `--mark`/重练流程处理，不要用 `--record` 硬塞。

## 内容规范

- `--due` / `--retest` / `--record` 的输出是给对话用的，不是 vault 产物；**不要**把它们写成新笔记。
- 回炉产生的判分记录落在 `workspace/records/attempts.json`（`paper_id` 为空、`note="回炉"`），错题本与进度总览由脚本重建，**不要手工编辑**这两份产物。
- 复习状态口径与 `grade.py --redo` 共用单一出处 `lib880.redo_state`；改语义先改 `scripts/lib880.py`，再同步 `scripts/wrong_book.py` 与 `scripts/grade.py`。

## 关联

- 生成/状态维护：`880-wrongbook`（`scripts/wrong_book.py --list-states / --mark`）
- 卷内重练判分：`880-grade`（`--redo`）
- 真题回炉：`zhenti-wrong`
