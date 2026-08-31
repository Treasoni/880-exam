# 880 考研数学习题系统 — 跨平台命令入口
#
# 默认用 python3（Linux/macOS）；Windows 覆盖解释器：
#   make paper PYTHON='py -3'
#   或直接 py -3 scripts/make_paper.py
#
# 判分优先读判分卡勾选：
#   make grade SHEET=workspace/papers/paper-01/判分卡-01.md
#   make grade SHEET=workspace/papers/paper-01/判分卡-01.md EXTRA='--redo'
# JSON 兜底（避免 cmd/PowerShell 引号问题）：
#   make grade PAPER=paper-01 EXTRA='--grading-file grade.json'

PYTHON ?= python3

.PHONY: help paper grade wrongbook progress lint index-check index-check-structure linear-index prepare test env-check

help: ## 列出可用命令
	@echo "make paper        — 拼一张卷（线代：make paper SUBJECT=linear-algebra）"
	@echo "make grade        — 判分（make grade SHEET=workspace/papers/paper-01/判分卡-01.md [EXTRA='--redo']）"
	@echo "make wrongbook    — 重新生成错题本"
	@echo "make progress     — 生成进度总览"
	@echo "make lint         — 校验生成产物格式"
	@echo "make index-check  — 题库索引对齐校验（只读）"
	@echo "make linear-index — 构建线代 880 独立题目索引"
	@echo "make test         — 运行核心规则与安全生成测试"
	@echo "make prepare      — 切分做题本/解析册小节"
	@echo "make env-check    — 环境变量模板自检"
	@echo "Windows 覆盖解释器：make <target> PYTHON='py -3'"

paper: ## 拼一张卷；线代：make paper SUBJECT=linear-algebra
	$(PYTHON) scripts/make_paper.py $(if $(SUBJECT),--subject $(SUBJECT))

grade: ## 判分：make grade SHEET=workspace/papers/paper-01/判分卡-01.md [EXTRA='--redo']；JSON 兜底：make grade PAPER=paper-01 EXTRA='--grading-file grade.json'
	$(PYTHON) scripts/grade.py $(if $(SHEET),--sheet $(SHEET),--paper $(PAPER)) $(EXTRA)

wrongbook: ## 重新生成错题本；线代：make wrongbook SUBJECT=linear-algebra
	$(PYTHON) scripts/wrong_book.py $(if $(SUBJECT),--subject $(SUBJECT))

progress: ## 生成进度总览；线代：make progress SUBJECT=linear-algebra
	$(PYTHON) scripts/progress.py $(if $(SUBJECT),--subject $(SUBJECT))

lint: ## 校验生成产物格式
	$(PYTHON) scripts/lint_content.py

index-check: ## 题库索引对齐校验（只读）
	$(PYTHON) scripts/build-question-index.py --check

index-check-structure: ## 只校验索引结构；保留待人工复核提示
	$(PYTHON) scripts/build-question-index.py --check --allow-pending-review

linear-index: ## 从线代做题本与解析册构建独立索引（不影响已判分的高数卷）
	$(PYTHON) scripts/build_linear_algebra_index.py

test: ## 运行自动化测试（不写入真实学习记录）
	$(PYTHON) -m unittest discover -s tests -v

prepare: ## 切分做题本/解析册小节到 workspace/.build
	$(PYTHON) scripts/prepare_sections.py

env-check: ## 环境变量模板自检
	bash .claude/scripts/check-env-template.sh
