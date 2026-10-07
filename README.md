# CUMCM 数学建模 Skill

**从赛题与附件出发，完成数学推导、模型选择、实际计算与验证，形成可追溯的写作交接大纲。**

面向 Codex 的 CUMCM（全国大学生数学建模竞赛）建模 Skill。以当前题目的数学结构和真实数据为起点，先建立可检验的基线，再根据具体缺口决定是否引入新的模型、表示或求解方法。

仓库提供建模工作流、数学原语、模型专题卡和配套检查工具；具体模型与求解代码围绕当前赛题形成。入口为 [`cumcm-modeling/SKILL.md`](cumcm-modeling/SKILL.md)，调用名称为 `$cumcm-modeling`。

## 核心特点

| 特点 | 在建模中如何发挥作用 |
|---|---|
| 数学结构先行 | 从变量、状态、目标、约束和观测关系进入推导，优先利用守恒、几何、单调性、凸性、尺度与分解结构。 |
| 基线优先，按缺口扩展 | 先建立能回答真实任务的参照，再定位题意、结构、数据或结果缺口；候选开放，复杂度由证据决定。 |
| 优化兼顾表示与求解 | 先检查决策自由度、变量耦合与搜索空间；快速评价用于搜索，正式方案回到原始目标和全部硬约束验证。 |
| 保持真实跨问关系 | 后问继承仍适用的数学对象、核心关系和上游结果，围绕新增信息或约束展开；更换核心模型需要相应依据。 |
| 验证针对主要风险 | 按题目选择回代、边界、守恒、留出/回测、敏感性或数值收敛检查，并关注预测误差对下游决策的影响。 |
| 计算结果可以交接 | 将模型、算法、参数、正式结果、验证及来源整理为 `paper-outline.md`，供后续写作直接查用。 |

局部任务只加载相关资料；完整建模走 G1 → G2 → G3。内置资料按具体问题取用，运行时不依赖相邻论文目录或实体论文库。

## 适合哪些任务

| 任务 | 主要工作 |
|---|---|
| 读题、拆问与数据理解 | 提取研究对象、输出要求、信息边界、约束及跨问接口；检查 CSV/XLSX 字段和表格结构。 |
| 推导、选模与优化 | 建立数学表示与基线，比较候选，处理优化、预测、统计学习、机理仿真或评价决策问题。 |
| 计算、验证与交接 | 执行当前项目代码，分析结果、误差和适用范围，形成正式结果资产及建模交接大纲。 |

## 工作流程与产物

```text
赛题与附件 → 数学对象、数据与假设 → 基线与缺口分析 → 候选模型与验证计划
         → G1：建模方案审查、正式实现
         → G2：实际计算、验证、计算事实审查
         → G3：整理建模交接大纲
```

完整任务在两处进行人工确认：G1-H 审查建模方案，用户可明确跳过；G2-H 审查计算事实，批准后再进入 G3。局部任务按实际范围处理。

| 产物 | 用途 |
|---|---|
| `modeling-brief.md` | 记录题意映射、数学对象、模型路线、验证计划与证据位置。 |
| `preliminary-modeling-report.md` | 在正式主模型计算前说明方案、假设、候选取舍与待确认事项。 |
| 实际代码、结果与 `reproducibility.json` | 保留运行入口、参数、指标和输出路径，支持结果复核。 |
| `G2-H_data_review.md` | 汇总已计算的结果、验证、跨问传递和需要确认的事实。 |
| `paper-outline.md` | 交接逐问推导、模型、算法、答案、验证、跨问关系及结果来源。 |

这些文件写入独立的 `PROJECT_ROOT`。正式论文写作可接续使用 [CUMCM 写作 Skill](https://github.com/Foxbox-m/cumcm-writing-skill)。

## 快速开始

在目标工作区执行：

```bash
git clone https://github.com/Foxbox-m/cumcm-modeling-skill.git
mkdir -p .agents/skills
ln -s "$PWD/cumcm-modeling-skill/cumcm-modeling" \
  .agents/skills/cumcm-modeling
```

完整建模示例：

```text
请使用 $cumcm-modeling，根据我提供的题面和附件完成建模。
先拆解各问并审计数据，再独立推导数学结构，建立可检验基线，按具体缺口比较候选。
实际运行代码，验证主要结果，保留真实跨问关系，并在事实确认后输出建模交接大纲。
```

局部任务也可直接调用：

```text
请使用 $cumcm-modeling，只分析问题二的决策变量、目标与约束，
给出一个可检验基线和最需要验证的假设，暂不开展完整计算。
```

## 配套工具

| 工具 | 功能 |
|---|---|
| [`audit_dataset.py`](cumcm-modeling/scripts/audit_dataset.py) | CSV/XLSX 数据检查，以及 XLSX 工作表、合并/隐藏结构、公式和批注侦察。 |
| [`check_project_brief.py`](cumcm-modeling/scripts/check_project_brief.py) | 检查项目简报的结构、任务说明与证据路径。 |
| [`check_reproducibility.py`](cumcm-modeling/scripts/check_reproducibility.py) | 检查复现清单中的运行、指标和输出记录。 |
| [`run_reproducible.py`](cumcm-modeling/scripts/run_reproducible.py) | 默认只读预览；显式选择运行条目后，按记录的命令与预算执行。 |
| [`check_stage.py`](cumcm-modeling/scripts/check_stage.py) | 检查 G1/G2/G3 阶段材料，包含交接大纲的逐问信息覆盖。 |
| [`search_literature.py`](cumcm-modeling/scripts/search_literature.py) | 从 Crossref、Semantic Scholar 发现文献元数据候选，采用前另行核验来源。 |

在仓库根目录执行，例如：

```bash
# 侦察 XLSX 结构
python3 cumcm-modeling/scripts/audit_dataset.py PROJECT_ROOT/data/input.xlsx --inspect

# 检查复现清单及输出文件
python3 cumcm-modeling/scripts/check_reproducibility.py \
  PROJECT_ROOT/results/reproducibility.json --project-root PROJECT_ROOT --require-outputs

# 检查建模交接大纲
python3 cumcm-modeling/scripts/check_stage.py --stage G3 --project-root PROJECT_ROOT

# 发现待核验文献；请求超时 5 秒，不额外重试
python3 cumcm-modeling/scripts/search_literature.py "查询词" \
  --provider crossref --timeout-seconds 5 --retries 0 --json
```

时间列、预测截止点等信息需要按真实数据显式提供；数据检查工具不会自动判定全部泄漏风险。阶段检查验证材料契约，数学正确性仍需依靠当前问题的推导与实际验证。

## 仓库结构与维护

```text
cumcm-modeling-skill/
├── cumcm-modeling/
│   ├── SKILL.md             # 入口、任务路由与建模原则
│   ├── agents/              # Codex 显示信息
│   ├── references/          # 工作流、数学原语与模型专题卡
│   ├── assets/              # 项目简报模板
│   └── scripts/             # 数据、复现、阶段与文献工具
├── evaluation/              # 回归测试与建模决策评测材料
└── scripts/build_skill.py   # 维护检查入口
```

配套工具使用 Python 3；读取 XLSX 需要 `openpyxl`，构建检查需要 `pytest` 与 `openpyxl`。具体求解依赖由赛题决定。在仓库根目录运行：

```bash
python3 scripts/build_skill.py
```

该入口检查资源完整性、运行脚本语法与现有回归测试，并保留当前维护的运行时文件。

## 使用说明

当前题面、用户要求与经核实的当届规则优先。正式数值来自实际执行且可追溯的输出；模型正确性和比赛表现取决于具体问题、数据与验证。公开仓库仅包含 Skill、评测与构建资源，项目数据、凭据和计算产物保存在各自项目中。本仓库未附加开源许可证，公开访问不构成额外的再分发授权。
