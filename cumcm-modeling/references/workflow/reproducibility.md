# CUMCM 可复现计算、工作区与阶段门规范

> **调用时机**：开始实现前读取；计算和验证阶段持续更新。完整整题、正式结果包或详细大纲综合在开始、会话恢复以及 G1/G2/G3 前重新读取持久化项目简报，并只在确认事实变化后更新；单项短任务可省略。项目简报统一使用 Schema 4 任务交付契约。
> **核心原则**：进入 G3 的数字、结构化结果和 figure-ready 数据必须能追溯到实际执行记录；路径、参数、环境与检查结果应由本题事实生成，不从示例照抄。

## 1. 分离 Skill 与赛题工作区

- `SKILL_ROOT`：包含 `SKILL.md` 的目录。相对路径的参考文件、脚本和资产从这里解析；把它视为只读资源库。
- `PROJECT_ROOT`：当前赛题的工作目录。数据派生物、程序、日志、结果资产和大纲只写入这里。
- 用户明确给定的项目结构优先；不要因为使用本 Skill 就强制重命名现有文件夹。
- 原始题目和附件保持不变。清洗、插补、坐标变换等写入派生文件，并记录由哪段程序生成。
- 不假设当前终端目录等于 `SKILL_ROOT` 或 `PROJECT_ROOT`；运行前解析并显示实际路径。

推荐但不强制的最小结构：

```text
PROJECT_ROOT/
├── data/raw/               # 原始附件，只读使用
├── data/processed/         # 程序生成的派生数据
├── src/                    # 求解与验证代码
├── config/                 # 参数与求解器配置
├── results/                # 数值结果、figure-ready 数据、日志、reproducibility.json
└── paper-outline.md        # G3 建模交接大纲
```

## 2. 结构化复现清单

在 `PROJECT_ROOT/results/reproducibility.json` 为每个正式运行维护一个条目。Schema 1.0 继续支持旧式字符串输出；Schema 1.1 使用结构化输出，并把任务到 selected/baseline 实际运行的绑定和结构化结果资产绑定到同一事实源。示例只说明字段，不提供可直接沿用的结果：

```json
{
  "schema_version": "1.1",
  "model_decisions": {
    "Q1": {
      "selected_run": "Q1-main",
      "baseline_run": "Q1-baseline"
    }
  },
  "runs": [
    {
      "id": "Q1-main",
      "question": "Q1",
      "role": "final",
      "purpose": "任务 A 正式计算",
      "working_directory": ".",
      "entry_command": ["python3", "src/q1.py", "--config", "config/q1.json"],
      "runtime_budget": {"timeout_seconds": 120, "max_attempts": 2},
      "inputs": ["data/raw/attachment.xlsx", "config/q1.json"],
      "outputs": [
        {"path": "results/q1_metrics.json", "kind": "metrics"},
        {"path": "results/q1_data.csv", "kind": "figure_data", "purpose": "状态与轨迹的可复用结构化结果"}
      ],
      "environment": {"python": "以实际查询结果填写", "dependency_file": "requirements.txt"},
      "random_seeds": [],
      "checks": [{"name": "约束满足", "criterion": "按本题定义", "value": "由程序写入", "passed": true}],
      "status": "planned"
    }
  ]
}
```

记录要求：

1. `entry_command` 使用参数数组，明确工作目录；不要只写“运行主程序”。
2. 输入、配置和输出使用 `PROJECT_ROOT` 内的相对路径；不写机器专属绝对路径。
3. 环境版本从实际环境查询，依赖文件由正式包管理工具维护；不要手写或计算自定义文件摘要。
4. 随机任务按作用域记录种子、随机数生成器和用途；确定性任务使用空数组。种子值不固定为某个模板数字。
5. `checks` 记录本题真正重要的守恒、边界、约束、误差、样本外或收敛检查及是否通过。
6. 运行时间可作资源说明，但不作为结果正确性的证据。

### 持久化项目简报

完整整题、正式结果包或详细大纲综合必须在项目内维护 `modeling-brief.md`。开始、会话恢复及 G1/G2/G3 前重新读取，核对题面/交付约束、事实证据锚点、确认决策、假设/单位/坐标、选定模型与基线/验证、未决风险、当前门和下一步；确认有变化后再更新。运行输出仍只归本清单，引用仍归 `results/citation-ledger.md`，简报不得复制成第二份结果或引文状态源。项目简报机器契约见 `check_project_brief.py`：

```bash
python3 <SKILL_ROOT>/scripts/check_project_brief.py <PROJECT_ROOT>/modeling-brief.md \
  --require-schema 4 --require-gate G1
```

### 上游变更与依赖重算

若数据清洗、参数、单位/坐标、核心关系或输入接口发生实质变化，沿已有任务依赖定位直接和间接受影响的计算、验证、结果资产及交接内容，按依赖顺序重算或重新核验；不能只更新公式或简报而继续引用旧输出。检查对象包括共享预处理与标定结果，不以题号是否相邻判断影响范围。真正独立的分支保留，不要求整题无差别重跑。

在现有 `modeling-brief.md` 说明变更、受影响任务及下一步，复用现有运行清单记录实际重算。旧运行成功不代表其输出适用于新输入；受影响证据完成更新前，不把旧结果继续作为当前答案或 G3 事实。若有解析不变性或直接核验足以说明某项输出不受影响，可保留并说明依据，不能只因文件存在或数值碰巧相同而跳过。涉及已批准模型或结论的变化仍遵循现有 G1-H/G2-H 回退与审查要求，不新增状态字段、依赖账本或文件摘要。

### Schema 1.1 约束

- `role` 只取 `candidate`（进入短名单的对比运行）、`baseline`（简单或保守基线）和 `final`（正式采用运行）；不使用其他自定义值。
- `status` 只取 `planned`、`running`、`passed`、`failed`、`timed_out`、`interrupted`，只描述生命周期，不代替运行角色。
- `model_decisions` 顶层按 `Q1`、`Q2` 等子问题组织，只把任务绑定到 `selected_run` 与可用的 `baseline_run`；选模理由和未决风险归项目简报，不在运行清单重复维护。
- 1.1 的 `outputs` 结构项至少含 `path` 与 `kind`；`kind: figure_data` 时还要有非空 `purpose`，说明该结构化数据承载的结果关系。旧项目的 1.0 输出仍是字符串数组。
- `kind: figure_data` 表示正式运行产生、且最终标量 metrics 无法完整恢复的可复用定量结果，例如时间序列、轨迹、空间坐标、方案比较矩阵、验证点、残差、已执行的敏感性结果、Pareto 点或可行域采样点。
- `figure_data` 仍属于该 run 的普通 output，不构成第二事实源。
- 不要求为潜在图件提前生成全部数据；只在核心结果包含 metrics 无法恢复的结构信息时保存最小充分数据。推荐结构如 `{"path": "results/q2_trajectory.csv", "kind": "figure_data", "purpose": "正式轨迹及关键状态的可复用结果数据"}`。
- `runtime_budget.timeout_seconds` 必须为正数，`max_attempts` 必须为正整数；受控运行前必须填写。
- `--require-outputs` 在 G3 对 `baseline` 和 `final` 运行严格阻断：状态必须为 `passed`、检查项必须全部通过且声明输出必须存在。`candidate` 是保留的对比证据，失败、未完成或输出未生成只产生提醒，不因候选本身阻断 G3；其结构字段仍必须合法。

使用结构检查器：

```bash
python3 <SKILL_ROOT>/scripts/check_reproducibility.py \
  <PROJECT_ROOT>/results/reproducibility.json \
  --project-root <PROJECT_ROOT> --require-outputs
```

G3 推荐使用一键阶段门禁总控（按实际项目补全路径）：

```bash
python3 <SKILL_ROOT>/scripts/check_stage.py --stage G3 \
  --project-root <PROJECT_ROOT> [--expected-questions Q]
```

### 受控正式运行

复现清单的结构化运行记录可使用标准库脚本执行一项已经批准的运行计划；项目简报的 Schema 4 任务交付契约仍由 `check_project_brief.py` 检查：

```bash
# 默认只做预检和 dry-run，不执行命令，不修改清单
python3 <SKILL_ROOT>/scripts/run_reproducible.py <PROJECT_ROOT>/results/reproducibility.json --project-root <PROJECT_ROOT>

# 显式指定运行条目后才执行
python3 <SKILL_ROOT>/scripts/run_reproducible.py <PROJECT_ROOT>/results/reproducibility.json --project-root <PROJECT_ROOT> --run Q1-main
```

运行器只接受 `entry_command` 参数数组，使用 `shell=False`，并预检解释器、入口脚本、工作目录、输入和输出路径。它只允许工作目录、相对入口脚本及声明路径位于 `PROJECT_ROOT` 内，不自动安装依赖、不静默替换求解器、不扫描未声明文件。每次尝试使用清单中的正数 `timeout_seconds` 和正整数 `max_attempts`；超时终止进程组，KeyboardInterrupt 记为 `interrupted`，非零退出记为 `failed`，成功退出且声明输出均存在才记为 `passed`。

这是一层可追溯执行控制，不是操作系统沙箱：入口程序本身仍可能访问项目外文件或网络。只有团队已经审查并批准的命令才可使用 `--run`；需要真正隔离时，应在受控容器或等价隔离环境中运行。

状态更新只原子替换同一个 `reproducibility.json`，不建立额外账本、备份或哈希。若清单 JSON 损坏，运行器拒绝覆盖并提示使用 Git 或手工恢复。若条目已经是 `running`，必须显式加 `--recover-running`；恢复时先标为 `interrupted`，再开始新的批准尝试。

第一阶段不实现操作系统级资源配额或自动情境化降级。只有在实际赛时发现预检与超时不足，或发布盲测证明缺少资源限制造成问题时，才启动第二阶段增强。

## 3. 随机性、依赖与运行证据

- 显式创建并传递随机数生成器，避免多个库各自使用未记录的隐式全局状态。
- 对随机优化、Bootstrap、蒙特卡洛或随机初始化，重复次数和种子数量由稳定性、估计精度与失败风险决定，不设统一次数；须同时记录相应的时间/迭代预算。
- 若不同合理种子可能改变可行性、目标值、排序或结论方向，不得只报告单次运行的最好值；应在可行预算内进行独立重复，报告分布并把方案不稳定性纳入结论边界。
- 记录算法终止条件、容差、初值和求解器状态；若声称“最优”，须由实际求解状态、界/间隙、容差或终止原因等证据支持，不绑定特定求解器字段；“退出码为 0”只证明程序正常结束，不证明模型正确。
- 进入大纲的关键量、稳定性指标和最优性证据应写入正式机器可读结果文件及 `checks`；日志应能把大纲结论或可视化意图追溯到具体运行条目。

## 4. 结构化结果与可视化数据交接

Modeling Skill 负责保存足以复现结论和供下游绘图使用的**数据资产**，不负责正式论文图的视觉设计、导出格式或版式 QA。

- headline 标量写入 metrics/JSON 等机器可读结果；时间序列、轨迹、空间坐标、前沿点、残差、验证点等结构信息按需保存为 `figure_data`。
- `figure_data` 必须保留单位、索引/坐标语义、方案身份和必要元数据，使下游无需重跑主模型即可重建所需关系。
- 只有标量结果无法恢复关键结构时才保存额外数据，不为潜在图件预生成大量冗余资产。
- Modeling Skill 可为调试或结果核验临时生成 diagnostic plot，但它不是 G2/G3 放行所需的正式论文图，也不携带配色、字体、图例、DPI、矢量格式或多面板等交付约束。
- G3 的可视化意图只能引用已存在的数据资产和证据关系；最终图型、视觉编码、注释、图例、布局和导出由下游 Figure/Writing Skill 决定。

## 5. 三道阶段门

阶段门统一命名为 G1/G2/G3：

| 门 | 完整工作流的触发点 | 最低放行证据 |
|---|---|---|
| **G1 建模门** | 主模型正式实现前 | 题目结构与子问依赖明确；候选、基线和选择理由齐全；关键假设、数学定式和验证计划已定义；`preliminary-modeling-report.md` 已完成人工审查且 G1-H 获得明确批准（或记录用户显式跳过），参数/状态可辨识性仅在适用任务中定义 |
| **G2-A 机器计算证据子门** | 综合结果前 | 正式命令、相关验证和机器检查实际运行；复现清单更新；关键输出与检查通过；正式运行保存结论所需的结构化结果，且在标量不足以恢复关键关系时保存最小充分的 `figure_data` |
| **G2-H 数据与结果人工子门** | G2-A 之后、冻结事实与大纲综合前 | `PROJECT_ROOT/G2-H_data_review.md` 明确记录 `gate: G2-H`、`decision: APPROVED`；人工核对数据/预处理、最终模型/算法、核心结果、验证和 G1→G2 偏差。G2 只有 G2-A 与 G2-H 均完成才放行 |
| **G3 详细论文大纲综合门** | 产出 `paper-outline.md` 后 | 题目—代码—结果—大纲一致；计算结果齐全可复现；`PROJECT_ROOT/paper-outline.md` 结构完整并覆盖子问；保留本次实际运行的 `check_stage.py --stage G3` 放行记录 |

门禁不限制独立咨询任务：如果用户只要求模型候选、局部诊断或局部建模讨论，只执行与该交付物有关的最低检查，并明确哪些完整流程证据尚未建立。任何未通过项应回到对应阶段修复，不能靠文字润色掩盖。

G1-H 只是 G1 的人工子门，不写入 Schema 4 的任务字段，不修改 `reproducibility.json`，也不新增 G4。未明确批准时，报告状态保持 `PENDING`，不得开始正式主模型求解；人工 `REVISE` 时按意见回退并重新生成报告。

## 6. 放行边界

只有在当前机器或明确记录的等价环境中实际执行了正式命令、核对了输出和检查结果，才能声称“已复现”。清单格式通过、文件存在、程序退出码为零或图像已生成，均不能单独证明数学模型、数据处理或大纲结论正确。
