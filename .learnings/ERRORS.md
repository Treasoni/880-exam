# 错误日志

---

_最后更新：2026-08-11_

## 2026-08-11

### 一次性脚本：python -c 漏导入 Path 导致 NameError

**错误**：重建 paper-01 答案卷的一次性 `python -c` 片段第 19 行 `NameError: name 'Path' is not defined`，脚本跑挂一次。

**触发场景**：用 `python -c` 内联运行多步脚本时。

**根因**：内联片段顶部忘了 `from pathlib import Path`，直接用了 `Path()`。

**修复**：
- 补上 `from pathlib import Path` 后重跑成功，答案卷按预期重建。

**预防措施**：
- 用 `python -c` 跑一次性脚本前，先把所有 import 在开头写全再执行；步骤较多时写成临时 `.py` 文件再运行，避免内联片段漏导入。

---
