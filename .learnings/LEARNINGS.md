# 学习心得

---

_最后更新：2026-09-24_

## 当前可复用学习

### 数列极限中的根式差

**类别**：knowledge_gap
**优先级**：medium
**状态**：pending
**范围**：高数 / 数列极限

**摘要**：把 $(n+1)^{1/n}-n^{1/(n+1)}$ 写成 $e^{A_n}-e^{B_n}$，用指数函数中值定理拆成 $e^{\xi_n}(A_n-B_n)$，再分别求阶。

---

## 2026-09-15

### 二次型正交变换：两次对角化的特征值顺序要对齐，`Q` 不唯一

**类别**：knowledge_gap
**优先级**：medium
**状态**：pending
**范围**：线代 / 二次型（`la-c12-comprehensive-solution-011`）

**摘要**：求使 $Q^{\mathsf T}AQ=B$ 的正交阵 $Q$，做法是分别正交对角化：$Q_1^{\mathsf T}AQ_1=\Lambda_1$、$Q_2^{\mathsf T}BQ_2=\Lambda_2$，**只有 $\Lambda_1=\Lambda_2$（两边的列按特征值一一对齐）**才有 $Q=Q_1Q_2^{\mathsf T}$ 满足 $Q^{\mathsf T}AQ=B$（$Q$ 正交）。同组特征向量可换序换号，所以 $Q$ 不唯一。

**详情**：
- 本题 $A=[[1,0,0],[0,2,1],[0,1,2]]$、$B=[[2,0,-1],[0,1,0],[-1,0,2]]$，特征值都是 $1,1,3$。
- 取 $Q_1$ 的列 = $A$ 的 $\lambda=1$ 特征向量 $(1,0,0),(0,1,-1)$ 与 $\lambda=3$ 的 $(0,1,1)$，$Q_2$ 的列 = $B$ 的 $\lambda=1$ 的 $(0,1,0),(1,0,1)$ 与 $\lambda=3$ 的 $(-1,0,1)$，得 $Q=Q_1Q_2^{\mathsf T}=[[0,1,0],[1,0,0],[0,0,-1]]$——按题中 $f$ 与 $g$ 的系数核验 $Q^{\mathsf T}AQ$ 严格等于 $B$，$Q$ 正交。
- 答案卷给的 $[[0,1,0],[0,0,1],[-1,0,0]]$ 满足同一等式，是同一批列的另一种排列，两者都对：**别把答案卷的列序当唯一标准**。

**下次做法**：自检用 $Q^{\mathsf T}AQ=B$（等价 $AQ=QB$）加 $Q^{\mathsf T}Q=I$，不要与答案卷逐元素比对；写 $Q_1$、$Q_2$ 时每列旁边标清对应的特征值，顺序不一致就算错。

---

## 历史记录
旧记录已归档至 `.learnings/archive/`：`LEARNINGS-2026-08-11-pre-digest.md`、`LEARNINGS-2026-08-12-pre-compress.md`、`LEARNINGS-2026-09-13-pre-compress.md`（2026-09-03 / 09-09 / 09-11 / 09-13）、`LEARNINGS-2026-09-15-pre-compress.md`、`LEARNINGS-2026-09-15-pre-digest.md`（两条 best_practice 内核已进 RULES）；`880-wrongbook` 公式渲染防线 3 条（2026-09-12 / 09-13）见 `.learnings/archive/2026-09-13-maintenance.md`；09-24 归档的两条（用户供稿先验算、公共前缀/后缀定位，内核均已进 RULES）见 `.learnings/archive/2026-09-24-maintenance.md`。
