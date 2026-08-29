# CUMCM 数学建模 Skill

一个面向 Codex 的证据驱动型 CUMCM（全国大学生数学建模竞赛）建模 Skill。它把赛题理解、数据审计、数学表示、候选模型、实际求解、验证、图表和论文交付串成一条可追溯流程。

## 能做什么

- 从题面和附件提取研究对象、变量、任务、约束、数据与交付要求；
- 先独立推导，再按需使用数学原语、模型卡和可选的外部历史资料；
- 审计 CSV/XLSX 数据，识别缺失、重复、异常、单位、时间切分和潜在泄漏；
- 支持优化、预测、统计学习、机理仿真、评价决策等路线，并保留可解释的基线；
- 运行可复现清单，检查结果、图件、论文结构、引用、附录和提交边界；
- 按当前题目证据组织摘要、正文、图表、LaTeX/Word 骨架和 AI 使用声明。

Skill 不会凭空生成数据、结果、引用或奖级，也不保证模型正确、论文获奖或符合某一届最新规则。正式数字必须来自当前项目中实际执行且可追溯的输出；规则、题面和用户要求优先于历史经验。

## 工作主线

```text
题面与数据 → 数学对象与假设 → 候选模型与基线 → 求解与实际运行
        → 验证、敏感性与边界 → 结果与图表 → 论文与提交审计
```

默认先完成当前题的独立结构推导，再按具体缺口读取参考资料。外部论文库不是运行前置条件；只有明确需要来源追溯、历史失败案例、方案比较或精确页码时，才显式提供外部 `CORPUS_ROOT`。

## 发布内容

```text
cumcm-modeling-skill/
├── README.md
├── .gitignore
└── cumcm-modeling/
    ├── SKILL.md                 # Skill 入口与任务路由
    ├── agents/openai.yaml       # Codex 显示名和默认提示词
    ├── references/              # 规则、工作流、模型、验证、写作与排版资料
    ├── assets/                  # LaTeX 模板、样式、声明和提交清单
    └── scripts/                 # 数据、复现、图件、论文和可选语料检索工具
```

本次发布只保留可独立运行的 Skill 运行时。顶层 `论文/` 语料、评测与 fixture、研究/维护文档和脚本、生成的二进制 Word 文件、语料索引均不随远程 `main` 上传；它们仍保留在本地源工作区，便于后续维护。运行时不假定 Skill 旁边存在论文目录，项目结果应写入独立的 `PROJECT_ROOT`。

## 安装到 Codex

```bash
git clone https://github.com/Foxbox-m/cumcm-modeling-skill.git
mkdir -p .agents/skills
ln -s /path/to/cumcm-modeling-skill/cumcm-modeling \
  .agents/skills/cumcm-modeling
```

在该工作区新建任务后即可调用：

```text
请使用 $cumcm-modeling 分析我提供的 CUMCM 赛题。先做题面和数据审计，再独立推导候选模型，保留基线并用实际运行结果验证；暂时不要写论文。
```

也可以直接读取 [`cumcm-modeling/SKILL.md`](cumcm-modeling/SKILL.md)。

## 常用入口

以下命令从 `cumcm-modeling-skill` 根目录执行，项目数据和产物放在独立项目目录：

```bash
# 数据结构与字段审计
python3 cumcm-modeling/scripts/audit_dataset.py PROJECT_ROOT/data/input.xlsx --inspect

# 按显式题号生成 LaTeX 或 Word 可见骨架
python3 cumcm-modeling/scripts/build/generate_paper_scaffold.py \
  --profile cumcm --questions N --format tex \
  --output PROJECT_ROOT/paper/main.tex

# 复现清单与图件终检
python3 cumcm-modeling/scripts/check_reproducibility.py \
  PROJECT_ROOT/results/reproducibility.json --project-root PROJECT_ROOT
python3 cumcm-modeling/scripts/check_figures.py \
  PROJECT_ROOT/results/reproducibility.json --project-root PROJECT_ROOT

# 普通 CUMCM 论文功能覆盖审计
python3 cumcm-modeling/scripts/check_paper.py PROJECT_ROOT/paper/final.pdf \
  --profile cumcm --award-style-audit
```

`N` 必须来自题面中明确的题号；没有显式题号时不要臆造。受控复现默认是 dry-run，只有明确指定运行条目才执行。论文审计是风险提示，不能替代数学、数据、视觉和当届规则的人工复核。

需要历史来源时，显式指定外部语料根目录，例如：

```bash
python3 cumcm-modeling/scripts/search_corpus.py 调度 \
  --corpus-root /path/to/CORPUS_ROOT --tag A1R,A1,A1Q,M1,M3 --limit 5
```

语料不可用时，核心 Skill 仍可独立完成；无法由当前题面、推导或实际运行支撑的历史主张必须删除、标记待核验或收窄。

## 隐私与使用边界

- 本仓库应保持 GitHub **Private**，只授予必要协作者访问权限；README 不能替代仓库可见性设置。
- 不要提交 API key、OAuth token、个人数据、私有赛题附件、运行日志或项目结果。
- 本仓库不提供额外开源许可证；在未补充明确许可前，不应将内容视为可自由再分发。
- 本次远程发布不包含论文原件或论文语料。使用外部资料时仍需自行核对来源、版权和当届竞赛规则。

## 入口

- [Skill 入口与任务路由](cumcm-modeling/SKILL.md)
- [来源治理](cumcm-modeling/references/core/source-governance.md)
- [建模与模型选择](cumcm-modeling/references/workflow/model-selection.md)
- [复现与结果事实源](cumcm-modeling/references/workflow/reproducibility.md)
- [论文写作与交付](cumcm-modeling/references/presentation/cumcm-paper-playbook.md)
