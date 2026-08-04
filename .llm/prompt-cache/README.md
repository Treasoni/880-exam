# .llm/prompt-cache — LLM usage observability

字段合同与回归样本所在目录（由 `prompt-cache-optimizer` skill 的 bootstrap 安装）。
本目录不是采集器：自动采集由下面的 collector 完成。

## 自动采集管线

```
Claude Code 会话 transcript（~/.claude/projects/-Users-zhqznc-code-880-exam/*.jsonl）
        ↓  python3 .claude/scripts/collect_llm_usage.py
.llm/prompt-cache/usage-events.jsonl   （本地 JSONL，已被 .gitignore 排除）
```

Claude Code 每会话一个 append-only JSONL，assistant 记录带 provider `usage`
（input/output/cache_read/cache_creation tokens）。collector 解析后按
`llm-usage-event.schema.json` 输出事件，增量续写（`collector-state.json` 记录
每文件处理到的字节偏移）。

**自动触发**（`.claude/settings.json`，均为 `--quiet` 静默运行）：
- `Stop` hook：每轮回复结束后自动增量采集，实现实时收集；
- `SessionStart` hook：会话启动时补齐上次会话及漏采数据。

## 字段映射（与 schema 的约定）

| 事件字段 | 来源 |
| --- | --- |
| timestamp / model | transcript 记录字段 |
| input/output_tokens | usage.input_tokens / output_tokens |
| cache_read_tokens | usage.cache_read_input_tokens（提供方未返回时省略，不编造） |
| cache_write_tokens | usage.cache_creation_input_tokens（同上） |
| latency_ms | 本 assistant 记录与其前一条记录的时间差（近似值） |
| request_type / template_id | 按会话首个用户消息关键词分类（见下表） |
| input_reference | `文件名:消息uuid`（安全引用，不含原始输入） |
| status / cost_usd | status 恒 success；cost 由提供方返回时才记录 |

## 请求分类表（collector 与回归样本共用，保持稳定）

| 关键词 | request_type | template_id |
| --- | --- | --- |
| 拼卷/拼张卷/出卷/生成卷子/来张卷 | paper | skill/880-paper |
| 判分/改卷/对答案/判分卡 | grade | skill/880-grade |
| 错题本/看错题/重练/复习错题 | wrongbook | skill/880-wrongbook |
| 进度/预览 | progress | skill/880-progress |
| 入库/重建索引/初始化题库 | build-index | skill/880-build-index |
| 同步技能/注册表 | sync-skill-registry | skill/sync-skill-registry |
| review since | code-review | skill/code-review |
| research/调研/查文档 | research | skill/research |
| 其他 | general-dev | claude-code/session |

## 使用

```bash
# 采集并续写事件
python3 .claude/scripts/collect_llm_usage.py

# 只看本次新增量，不写文件
python3 .claude/scripts/collect_llm_usage.py --dry-run

# 含 subagent/workflow 子目录 transcript
python3 .claude/scripts/collect_llm_usage.py --recursive

# 自定义 transcript 目录（跨平台/换机器时）
python3 .claude/scripts/collect_llm_usage.py --transcript-dir /path/to/projects/<sanitized-root>
```

## 指标口径（同 measurement.md）

- `cache_read_rate = Σcache_read_tokens / Σinput_tokens`，按
  request_type + template_id + template_version + model 分组计算，仅作同项目趋势指标。
- 模型、工具定义或模板版本变化时分组比较，不混入同一基线。
- 无实测数据不下"节省"结论；第一次运行得到的是基线，不是优化收益。

## 回归样本

`regression-cases.json` 含 8 个高频请求（880 拼卷/判分/错题本/进度/入库、
通用开发、code review、research），`fixtures/` 存放脱敏的稳定请求文本；
质量检查项在 `quality_checks`。指标经 collector 自动回填 baseline。

## 最小评审表

| 请求类型 | 模板版本 | 样本数 | 输入 token | 缓存读取 token | 输出 token | 延迟 | 费用 | 质量 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 待首次重放回填 | v1 | 8 | — | — | — | — | N/A | 未评估 |
