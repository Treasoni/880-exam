# 880 考研数学习题系统 — 跨平台命令入口
#
# 默认用 python3（Linux/macOS）；Windows 覆盖解释器：
#   make paper PYTHON='py -3'
#   或直接 py -3 scripts/make_paper.py
#
# 判分 JSON 建议用 --grading-file 从文件读取，避免 cmd/PowerShell 引号问题：
#   make grade PAPER=paper-01 EXTRA='--grading-file grade.json --redo'

PYTHON ?= python3

.PHONY: help paper grade wrongbook progress lint index-check prepare env-check

help: ## 列出可用命令
	@echo "make paper        — 拼一张卷"
	@echo "make grade        — 判分（make grade PAPER=paper-01 EXTRA='--grading-file grade.json [--redo]'）"
	@echo "make wrongbook    — 重新生成错题本"
	@echo "make progress     — 生成进度总览"
	@echo "make lint         — 校验生成产物格式"
	@echo "make index-check  — 题库索引对齐校验（只读）"
	@echo "make prepare      — 切分做题本/解析册小节"
	@echo "make env-check    — 环境变量模板自检"
	@echo "Windows 覆盖解释器：make <target> PYTHON='py -3'"

paper: ## 拼一张卷
	$(PYTHON) scripts/make_paper.py

grade: ## 判分：make grade PAPER=paper-01 EXTRA='--grading-file grade.json --redo'
	$(PYTHON) scripts/grade.py --paper $(PAPER) $(EXTRA)

wrongbook: ## 重新生成错题本
	$(PYTHON) scripts/wrong_book.py

progress: ## 生成进度总览
	$(PYTHON) scripts/progress.py

lint: ## 校验生成产物格式
	$(PYTHON) scripts/lint_content.py

index-check: ## 题库索引对齐校验（只读）
	$(PYTHON) scripts/build-question-index.py --check

prepare: ## 切分做题本/解析册小节到 workspace/.build
	$(PYTHON) scripts/prepare_sections.py

env-check: ## 环境变量模板自检
	bash .claude/scripts/check-env-template.sh
