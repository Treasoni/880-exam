# 错误日志归档 · 2026-09-15

> 以下两条的机制均已修复并验证（`check-workflow-state.sh` 对负样本报错；round-trip + EOF 断言），可执行规则已提炼进 `.learnings/RULES.md`（「工作流状态机」「改动核验」两节），故从主文件归档。

---

### 880-exam 工作流：状态模板与状态机契约不符（异常表缺失 + token 不在行尾）

**错误**：本轮错题复习收尾时，`todo-state.sh skip` 先以 `todo-state: exception table not found` 直接失败（P0–P2 跳不过去）；补表之后三次 skip 又把 frontmatter 置成 `current_phase: done` / `current_status: complete`，而盘面上 P3 仍是 `{in_progress}`、P4 仍是 `{not_started}`——状态机「跳档」，跳过的阶段说明写不进异常记录表。

**触发场景**：任何用 `.claude/workflows/880-exam/state-template.md` 新建运行文件、并首次调用 `skip`/`block` 或 `complete`/`skip` 需要推进到下一阶段的时候；模板不改，每个新 run 都会复现。

**根因**：两条都是**模板与脚本的契约不一致**，且失败方式不同：
1. 模板 frontmatter 之后只有「当前上下文」，没有 `## 异常记录` 表，而 `ensure_exception_table` 要求表头存在——`skip`/`block` 在写记录前就 exit 1（显式失败）。
2. 模板阶段行写成 `> [P0] ⬜ 未开始 {not_started} — 入库`（token 后带 `— 标签`），而 `phase_has_status` / `previous_open_phase_before` / `next_pending_phase_after` 三条正则全部按 `\{token\}$` 行尾匹配——未改写的阶段行对状态机不可见：前序阶段校验形同虚设（可以 `start P4` 而 P0 未动），`complete`/`skip` 后 `next_pending_phase_after` 恒返回空，于是每次都走 `else` 分支写 `done/complete`（静默跳档）。只有被 `replace_phase_status` 整行重写过的阶段行（标签被抹掉、token 落到行尾）才可见——这正是「前半段正常、后半段跳档」的原因。

**修复**：
- `.claude/workflows/880-exam/state-template.md`：阶段行改为行尾 token（`> [P0] ⬜ 未开始 {not_started}`，阶段含义见 `workflow.md`），补 `> 当前阶段：阶段 0` 行，保留 `## 异常记录` 表。
- 本轮运行文件 `workspace/workflow-runs/错题复习.workflow.md` 同步修正（P4 行去标签），随后 `complete P3` → `start P4` → `complete P4` 全部走脚本，末态 P0–P2 `{skipped}`、P3/P4 `{complete}`、`current_phase: done` 与实际一致——用真实状态机流程端到端验证过。
- 新增 `.claude/scripts/check-workflow-state.sh`（源头+陈旧检测）：校验每个 state-template 与 workflow-run 的阶段行 token 是否在行尾、`## 异常记录` 表是否存在、运行文件 frontmatter 是否含 `current_phase`/`current_status`。用负样本（带 `— 拼卷` 后缀的阶段行）实测能报出精确到行的错误，正样本三个文件全绿。
- 流程步骤：`CLAUDE.md` 的 Workflow Todo State 一节追加「改状态文件/模板后跑 `check-workflow-state.sh`」；`.learnings/RULES.md` 原来那条规则把错样式当范例（`… {not_started} — 入库`），已改写为「token 必须在行尾」，并补异常表规则。

**预防措施**：
- 新建/修改工作流状态模板后，先跑 `.claude/scripts/check-workflow-state.sh`，再拿它新建一个 run 走一遍 `start → complete` 才认模板可用（脚本 py 层面绿≠状态机可驱动）。
- 状态机「静默跳档」的排查顺序：`git show HEAD:<run>` 看盘面 → 对 `todo-state.sh` 的三条正则看行尾 token → 看模板原文（模板才是源头）。

---

### 880 事实源写回：`json.dumps` 不带末尾换行，制造 `No newline at end of file` 假 diff

**错误**：把解析写回 `workspace/question-index.json` 后用 `pathlib.write_text(json.dumps(...))` 落盘，`git diff` 末尾多出一处 `-}` / `+}` 且带 `\ No newline at end of file` 标记。更糟的是，我事先按 `RULES.md` 的 round-trip 判据自检得到「与源一致」，因为那条判据把源文件的情况记反了（写成「含**无**末尾换行」）——自检脚本与写回脚本互相印证同一个错误前提，两边都绿。

**触发场景**：任何写回仓库里人工维护的 JSON 的时候。`json.dumps` 从不输出末尾换行；仓库文件（编辑器与 `.gitattributes` 风格）带末尾换行。EOF 换行差是最容易看漏的一类 diff：`--stat` 只多 1 行，`grep -v` 各种过滤会把它连同文件头一起吞掉。

**根因**：`RULES.md` 的 round-trip 规则把 HEAD 的实际情况记反了。规则本身是「用错误的前提去验收」，所以它只能检验「我的写回和我的误认是否自洽」，检验不出真实格式差异。

**修复**：
- 写回后补 `+ "\n"`，重跑 `git diff`：`No newline at end of file` 计数归 0，`--stat` 从 23/23 收敛到 22/22（22 条改动的 `solution`，缩进 2 的 JSON 里每个 `solution` 各占 1 行，正好对上）。
- 更正 `.learnings/RULES.md` 的 round-trip 判据为「与源**含末尾换行**比对」。

**预防措施**：
- 写回聚合 JSON 固定用 `json.dumps(data, ensure_ascii=False, indent=2) + "\n"`，round-trip 自检用同一表达式。
- 核验时显式断言 `git diff | grep -c "No newline at end of file"` 为 0，不靠 `--stat` 的数字推。

---

