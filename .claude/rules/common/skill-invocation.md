# Skill Invocation

## 技能列表
<!-- skill-registry:managed ["880-analysis","880-build-index","880-grade","880-paper","880-progress","880-wrongbook","ask-matt","batch-grill-me","claude-handoff","code-review","codebase-design","defuddle","design-an-interface","diagnosing-bugs","digest","domain-modeling","edit-article","git-guardrails-claude-code","grill-me","grill-with-docs","grilling","handoff","implement","improve-codebase-architecture","json-canvas","loop-me","maintain-learnings","manifest-platform","migrate-to-shoehorn","obsidian-bases","obsidian-cli","obsidian-markdown","obsidian-vault","prompt-cache-optimizer","prototype","qa","request-refactor-plan","research","resolving-merge-conflicts","scaffold-exercises","setup-matt-pocock-skills","setup-pre-commit","setup-ts-deep-modules","sync-skill-registry","tdd","teach","to-questionnaire","to-spec","to-tickets","triage","ubiquitous-language","wayfinder","wizard","workflow-todo-state","writing-beats","writing-fragments","writing-great-skills","writing-shape"] -->

#### 未分类

| 技能 | 触发场景 | 关键触发词 |
|------|----------|-----------|
| `880-analysis` | 对话式过程归因——用户贴做题过程，定位出错环节并给出建议，写入 analysis.json 并由错题本渲染。 | 分析、错因、归因、这题我哪里错了、看我做题过程、我这样做的 |
| `880-build-index` | 从做题本+解析册重建题目索引（首次入库或源文件更新后用）。 | 入库、重建索引、初始化题库 |
| `880-grade` | 判分记录（五态：对/错/不会/半会/粗心），更新判分记录、错题本与进度总览。 | 判分、改卷、对答案、交判分 |
| `880-paper` | 拼一张 880 高数模拟卷（真题模式：选10×5分+填6×5分+解6题=150分/180分钟），生成卷子、答案卷与判分卡。 | 拼卷、拼张卷、出卷、生成卷子、来张卷 |
| `880-progress` | 生成或查看进度总览——哪些题已完成/未完成/做错，章节完成率与弱点排行。 | 预览、进度、看进度、进度总览 |
| `880-wrongbook` | 查看/重生成错题本，更新复习状态（未复习/已重做/已掌握）。 | 错题本、看错题、重练、复习错题 |
| `ask-matt` | Ask which skill or flow fits your situation. A router over the skills in this… | Ask which skill or flow fits your situat… |
| `batch-grill-me` | A relentless interview that asks every frontier question at once | A relentless interview that asks every f… |
| `claude-handoff` | Hand the current conversation off to a fresh background agent that picks up t… | Hand the current conversation off to a f… |
| `code-review` | Review the changes since a fixed point (commit, branch, tag | review since X |
| `codebase-design` | Shared vocabulary for designing deep modules. Use when the user wants to desi… | Shared vocabulary for designing deep mod… |
| `defuddle` | Extract clean markdown content from web pages using Defuddle CLI | Extract clean markdown content from web … |
| `design-an-interface` | Generate multiple radically different interface designs for a module using pa… | design it twice |
| `diagnosing-bugs` | Diagnosis loop for hard bugs and performance regressions. Use when the user s… | diagnose、debug this |
| `digest` | 自我学习阶段。回顾本次会话，记录真实发生的学习点和错误到 .learnings/； | 自我学习阶段 |
| `domain-modeling` | Build and sharpen a project's domain model. Use when the user wants to pin do… | Build and sharpen a project's domain mod… |
| `edit-article` | Edit and improve articles by restructuring sections, improving clarity | Edit and improve articles by restructuri… |
| `git-guardrails-claude-code` | Set up Claude Code hooks to block dangerous git commands (push, reset --hard | Set up Claude Code hooks to block danger… |
| `grill-me` | A relentless interview to sharpen a plan or design. | A relentless interview to sharpen a plan… |
| `grill-with-docs` | A relentless interview to sharpen a plan or design | A relentless interview to sharpen a plan… |
| `grilling` | Grill the user relentlessly about a plan, decision | Grill the user relentlessly about a plan… |
| `handoff` | Compact the current conversation into a handoff document for another agent to… | Compact the current conversation into a … |
| `implement` | "Implement a piece of work based on a spec or set of tickets." | Implement a piece of work based on a spec or set of tickets. |
| `improve-codebase-architecture` | Scan a codebase for deepening opportunities | Scan a codebase for deepening opportunit… |
| `json-canvas` | Create and edit JSON Canvas files (.canvas) with nodes, edges, groups | Create and edit JSON Canvas files (.canv… |
| `loop-me` | Grill me about specs for the workflows I want to build, within this workspace. | Grill me about specs for the workflows I… |
| `maintain-learnings` | 维护 .learnings/ 经验库，把过多或反复出现的学习记录、错误日志、规则失效问题聚类诊断，追溯并修改对应 skill、模板、hook、校验脚本或项目规则； | 维护 .learnings/ 经验库，把过多或反复出现的学习记录、错误日志、规则… |
| `manifest-platform` | Install, configure, migrate, and validate a portable manifest registry for ag… | Install, configure, migrate, and validat… |
| `migrate-to-shoehorn` | Migrate test files from `as` type assertions to @total-typescript/shoehorn. U… | Migrate test files from `as` type assert… |
| `obsidian-bases` | Create and edit Obsidian Bases (.base files) with views, filters, formulas | Create and edit Obsidian Bases (.base fi… |
| `obsidian-cli` | Interact with Obsidian vaults using the Obsidian CLI to read, create, search | Interact with Obsidian vaults using the … |
| `obsidian-markdown` | Create and edit Obsidian Flavored Markdown with wikilinks, embeds, callouts | Create and edit Obsidian Flavored Markdo… |
| `obsidian-vault` | Search, create, and manage notes in the Obsidian vault with wikilinks and ind… | Search, create, and manage notes in the … |
| `prompt-cache-optimizer` | 审计并优化 LLM 提示缓存命中率、输入 token、延迟与调用成本。 | 优化缓存命中、降低 token 成本、审计 LLM 调用、提示词缓存优化、优化 AI 调用费用 |
| `prototype` | Build a throwaway prototype to answer a design question. Use when the user wa… | Build a throwaway prototype to answer a … |
| `qa` | Interactive QA session where user reports bugs or issues conversationally | QA session |
| `request-refactor-plan` | Create a detailed refactor plan with tiny commits via user interview | Create a detailed refactor plan with tin… |
| `research` | Investigate a question against high-trust primary sources and capture the fin… | Investigate a question against high-trus… |
| `resolving-merge-conflicts` | "Use when you need to resolve an in-progress git merge/rebase conflict." | Use when you need to resolve an in-progress git merge/rebase conflict. |
| `scaffold-exercises` | Create exercise directory structures with sections, problems, solutions | Create exercise directory structures wit… |
| `setup-matt-pocock-skills` | Configure this repo for the engineering skills — set up its issue tracker | Configure this repo for the engineering … |
| `setup-pre-commit` | Set up Husky pre-commit hooks with lint-staged (Prettier), type checking | Set up Husky pre-commit hooks with lint-… |
| `setup-ts-deep-modules` | Wire dependency-cruiser into a TypeScript repo so each package is a deep modu… | Wire dependency-cruiser into a TypeScrip… |
| `tdd` | Test-driven development. Use when the user wants to build features or fix bug… | red-green-refactor |
| `teach` | Teach the user a new skill or concept, within this workspace. | Teach the user a new skill or concept, w… |
| `to-questionnaire` | Turn a decision you can't fully answer into a questionnaire for someone else … | Turn a decision you can't fully answer i… |
| `to-spec` | Turn the current conversation into a spec and publish it to the project issue… | Turn the current conversation into a spe… |
| `to-tickets` | Break a plan, spec, or the current conversation into a set of tracer-bullet t… | Break a plan, spec, or the current conve… |
| `triage` | Move issues and external PRs through a state machine of triage roles — catego… | Move issues and external PRs through a s… |
| `ubiquitous-language` | Extract a DDD-style ubiquitous language glossary from the current conversation | domain model、DDD |
| `wayfinder` | Plan a huge chunk of work — more than one agent session can hold — as a share… | Plan a huge chunk of work — more than on… |
| `wizard` | Generate an interactive bash wizard that walks a human through a manual proce… | Generate an interactive bash wizard that… |
| `workflow-todo-state` | Create or retrofit reusable named workflow state machines for multi-step agen… | Create or retrofit reusable named workfl… |
| `writing-beats` | Writing, exploit — assemble raw material into a journey of beats | Writing, exploit — assemble raw material… |
| `writing-fragments` | Writing, explore — mine raw fragments, no structure yet. | Writing, explore — mine raw fragments, n… |
| `writing-great-skills` | Reference for writing and editing skills well — the vocabulary and principles… | Reference for writing and editing skills… |
| `writing-shape` | Writing, exploit — shape raw material into an article, paragraph by paragraph. | Writing, exploit — shape raw material in… |

#### 工具发现

| 技能 | 触发场景 | 关键触发词 |
|------|----------|-----------|
| `sync-skill-registry` | 技能注册表同步工具。扫描任意 agent skill 目录中的 */SKILL.md 并自动更新对应 skill-invocation.md 中的技能列表… | 同步注册表、更新技能列表、sync skill registry、update skill registration、刷新技能列表、同步技能表格 |

### 1. 分析意图

根据用户请求选择最合适的可复用 skill 或模板。
