# CUMCM 数学建模 Skill

一个面向 Codex 的证据驱动型 CUMCM（全国大学生数学建模竞赛）建模 Skill。它把赛题理解、数据审计、数学表示、候选模型、实际求解、验证与 G3 建模交接大纲串成一条可追溯流程。

## 能做什么

- 从题面和附件提取研究对象、变量、任务、约束、数据与交付要求；
- 先独立推导，再按需使用内置蒸馏规则、数学原语、模型卡和经核验的外部公开来源；
- 审计 CSV/XLSX 数据，识别缺失、重复、异常、单位、时间切分和潜在泄漏；
- 支持优化、预测、统计学习、机理仿真、评价决策等路线，并保留可解释的基线；
- 完整建模在正式实现前生成 `preliminary-modeling-report.md`，经 G1-H 人工 `APPROVED` 或用户明确跳过后再继续；
- 运行可复现清单，检查计算结果、指标输出与 figure-ready 数据资产；
- 完整计算与结果分析在 G2 结束时生成 `G2-H_data_review.md`，经 G2-H 人工 `APPROVED` 并冻结事实后，进入 G3 阶段；
- G3 阶段生成 `PROJECT_ROOT/paper-outline.md` 作为建模交接大纲，覆盖全局问题链、逐问模型/算法/结果/验证、真实跨问关系、证据索引，以及仅在必要时保留的可视化意图；不输出论文语态、章节结构或视觉样式。

Skill 不会凭空生成数据、结果、引用或奖级，也不保证模型正确、论文获奖或符合某一届最新规则。正式数字必须来自当前项目中实际执行且可追溯的输出；规则、题面和用户要求优先于历史经验。

## 工作主线

```text
题面与数据 → 数学对象与假设 → 候选模型与基线 → 模型定式与验证计划
        → preliminary-modeling-report.md → G1-H 人工审查/明确跳过
        → G1 正式实现与运行 → 验证、敏感性与边界 → 结构化结果资产
        → G2-H 数据事实审查（G2-H_data_review.md）→ 人工 APPROVED 与事实冻结
        → G3 建模交接大纲综合（paper-outline.md）
```

默认先完成当前题的独立结构推导，再按具体缺口读取内置参考。只有理论来源、历史失败案例、方案比较或精确出处会改变论证时，才按需检索并核验外部公开来源。

G1-H 是 G1 内的人工子门，G2-H 是 G2 内的人工子门；完整任务在人工报告 `PENDING` 时暂停后续步骤。正式论文写作、视觉设计和提交格式由下游独立 Skill 处理。

## 发布内容

```text
cumcm-modeling-skill/
├── README.md
├── .gitignore
└── cumcm-modeling/
    ├── SKILL.md                 # Skill 入口与任务路由
    ├── agents/openai.yaml       # Codex 显示名和默认提示词
    ├── references/              # 规则、工作流、模型、推导与大纲资料
    ├── assets/                  # 项目简报模板
    └── scripts/                 # 数据审计、复现清单、文献发现与阶段检查工具
```

本仓库只保留可独立运行的 Skill、评测与构建资源；不包含或依赖实体论文库、论文索引或语料维护脚本。项目结果写入独立的 `PROJECT_ROOT`。

## 安装到 Codex

```bash
git clone https://github.com/Foxbox-m/cumcm-modeling-skill.git
mkdir -p .agents/skills
ln -s /path/to/cumcm-modeling-skill/cumcm-modeling \
  .agents/skills/cumcm-modeling
```

在该工作区新建任务后即可调用：

```text
请使用 $cumcm-modeling 分析我提供的 CUMCM 赛题。先做题面和数据审计，再独立推导候选模型，保留基线并用实际运行结果验证；完成计算与事实审查后输出建模交接大纲。
```

也可以直接读取 [`cumcm-modeling/SKILL.md`](cumcm-modeling/SKILL.md)。

## 常用入口

以下命令从 `cumcm-modeling-skill` 根目录执行，项目数据和产物放在独立项目目录：

```bash
# 数据结构与字段审计
python3 cumcm-modeling/scripts/audit_dataset.py PROJECT_ROOT/data/input.xlsx --inspect

# 项目简报规范检查
python3 cumcm-modeling/scripts/check_project_brief.py PROJECT_ROOT/modeling-brief.md \
  --project-root PROJECT_ROOT

# 复现清单终检
python3 cumcm-modeling/scripts/check_reproducibility.py \
  PROJECT_ROOT/results/reproducibility.json --project-root PROJECT_ROOT --require-outputs

# 阶段门禁检查（支持 G1, G2, G3）
python3 cumcm-modeling/scripts/check_stage.py --stage G3 \
  --project-root PROJECT_ROOT --expected-questions N
```

`N` 必须来自题面中明确的题号；没有显式题号时不要臆造。受控复现默认是 dry-run，只有明确指定运行条目才执行。

需要外部理论或算法来源时，可使用公开网络检索，或用内置元数据发现脚本生成待核验候选：

```bash
python3 cumcm-modeling/scripts/search_literature.py "查询词" \
  --provider crossref --timeout-seconds 5 --retries 0 --json
```

外部来源不可用时，核心 Skill 仍可独立完成建模；无法由当前题面、推导、实际运行或已核验来源支撑的外部主张必须删除、标记待核验或收窄。

## 隐私与使用边界

- 本仓库公开发布 Skill、评测与构建资源；赛题附件、个人数据和项目结果应保存在各自的独立项目目录。
- 不要提交 API key、OAuth token、个人数据、私有赛题附件、运行日志或项目结果。
- 本仓库不提供额外开源许可证；在未补充明确许可前，不应将内容视为可自由再分发。
- 仓库不包含论文原件或实体论文语料。使用外部资料时仍需核对来源、版权和当届竞赛规则。

## 入口

- [Skill 入口与任务路由](cumcm-modeling/SKILL.md)
- [建模与模型选择](cumcm-modeling/references/workflow/model-selection.md)
- [G1-H 人工建模审查](cumcm-modeling/references/workflow/human-modeling-review.md)
- [G2-H 数据事实审查](cumcm-modeling/references/workflow/g2-human-review.md)
- [复现与结果事实源](cumcm-modeling/references/workflow/reproducibility.md)
- [G3 建模交接大纲规范](cumcm-modeling/references/workflow/detailed-paper-outline.md)
- [文献引用验证](cumcm-modeling/references/workflow/literature-verification.md)
