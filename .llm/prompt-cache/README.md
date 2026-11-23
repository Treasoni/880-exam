---
type: 文档
updated: 2026-11-23
tags: [880, LLM, 提示缓存]
---

# LLM 用量与提示缓存

## 启动上下文

Claude Code `SessionStart` 默认只输出固定的经验索引。做相关任务之前，按索引定位 [[.learnings/RULES.md|铁律]] 的对应章节；仅在需要时读 [[.learnings/ERRORS.md|错误日志]] 和 [[.learnings/LEARNINGS.md|学习心得]]。启动时不再随经验库滚动注入最近条目。需要查看旧式摘录时，可手动运行 `python3 .claude/hooks/read_learnings.py --tail-lines 50`。

## 自动采集

`SessionStart` 与 `Stop` 静默执行 `.claude/scripts/collect_llm_usage.py --quiet`，读取当前项目的 Claude Code JSONL transcript，增量写入 `usage-events.jsonl`。`collector-state.json` 保存读取偏移和去重所需状态。两者均不入库。采集器只记录用量及分类，不保存用户输入或模型正文，也不更新回归基线。

| 事件字段 | 口径 |
| --- | --- |
| `input_tokens` / `output_tokens` | 原样记录非负整数；`input_tokens` 不一定是总输入，取决于来源 |
| `cache_read_tokens` / `cache_write_tokens` | 原样记录提供方返回的非负整数；缺失或非法时省略，不补零 |
| `latency_ms` | 相邻 transcript 记录的时间差，非 API 延迟或整轮任务耗时；无法计算时为 0 |
| `request_type` / `template_id` | 从每个会话首条非元数据用户文本推断；不是实际技能调用记录。已有会话的标签继续沿用 |
| `template_version` | 分类标签保持 `"1"`，不表示实际模板内容版本 |
| `metadata.collector_version` | `2` 为新口径；字段缺省为历史口径，不与新记录混算 |
| `metadata.cache_semantics` | 默认 `unknown`。经验证的原生 Anthropic 来源可用 `--cache-semantics anthropic`，且仅在三种输入字段齐全时标记为 `anthropic` |
| `input_reference` | `文件名:消息uuid`，不含原始输入 |
| `cost_usd` | 当前 transcript 未提供可靠实际费用，不记录、不估算 |

同一 transcript 的连续 `message.id` 快照只记录一次（包括跨采集批次）；无消息 ID 时不能可靠去重。`<synthetic>` 响应不计入新样本。旧数据不重写，跨旧版和新版采集边界的重复仍可能存在。

```bash
# 检查增量而不写盘
python3 .claude/scripts/collect_llm_usage.py --dry-run

# 仅当确认该目录全部采用 Anthropic 原生口径时，写到独立的本地分析输出。
# 两个输出路径必须与自动采集隔离，避免历史重复写入主日志。
python3 .claude/scripts/collect_llm_usage.py --transcript-dir /path/to/verified-transcripts \
  --cache-semantics anthropic --output /path/to/local-analysis/events.jsonl \
  --state-file /path/to/local-analysis/state.json
```

## 如何解释缓存数据

> [!warning] 不能从代理模型名、字段名或计数大小推断缓存口径
> Anthropic 原生 `input_tokens` 只是未缓存部分，因此 `cache_read_tokens > input_tokens` 并不异常。旧采集器据此丢弃了不少缓存读取字段，历史记录不能当作可靠的缓存比例基线。

- 仅对已确认 Anthropic 口径且三个字段齐全的样本计算：总输入 = 未缓存输入 + 缓存写入 + 缓存读取；缓存读取占比 = 总缓存读取量 ÷ 总输入量（总输入量非零）。占比不等于命中请求比例，也不等于费用节省。
- 按请求类型、模板 ID、模板版本、模型、采集版本和来源口径分组。未知口径仅看原始字段，不汇总为命中率。

## 回归验证

`regression-cases.json` 与 `fixtures/` 保存脱敏任务和质量检查项。现有 collector **不会自动重放或回填基线**。固定请求如果会拼卷、判分或重建索引，须在隔离的副本中重放，不要直接运行在当前 Vault 上。对比前固定模型、工具、初始状态和缓存冷热条件，并验证两边的产出质量。没有可比重放数据时，只报告可验证的本地变化（例如 hook 输出字节数），不报告缓存、延迟或费用收益。
