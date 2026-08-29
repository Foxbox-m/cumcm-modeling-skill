# CUMCM 可复现计算、工作区与阶段门规范

> **调用时机**：开始实现前读取；计算、制图和写作阶段持续更新。完整整题、最终论文或完整结果包在开始、会话恢复以及 G1/G2/G3 前重新读取持久化项目简报，并只在确认事实变化后更新；单项短任务可省略。项目简报统一使用 Schema 4 profile 与任务交付契约。
> **核心原则**：进入论文的数字、表格和图件必须能追溯到实际执行记录；路径、参数、环境与检查结果应由本题事实生成，不从示例照抄。

## 1. 分离 Skill 与赛题工作区

- `SKILL_ROOT`：包含 `SKILL.md` 的目录。相对路径的参考文件、脚本和资产从这里解析；把它视为只读资源库。
- `PROJECT_ROOT`：当前赛题的工作目录。数据派生物、程序、日志、结果、图件、论文和清单只写入这里。
- 用户明确给定的项目结构优先；不要因为使用本 Skill 就强制重命名现有文件夹。
- 原始题目和附件保持不变。清洗、插补、坐标变换等写入派生文件，并记录由哪段程序生成。
- 不假设当前终端目录等于 `SKILL_ROOT` 或 `PROJECT_ROOT`；运行前解析并显示实际路径。

推荐但不强制的最小结构：

```text
PROJECT_ROOT/
├── data/raw/               # 原始附件，只读使用
├── data/processed/         # 程序生成的派生数据
├── src/                    # 求解、验证和绘图代码
├── config/                 # 参数与求解器配置
├── results/                # 数值结果、日志、reproducibility.json
├── figures/                # 正文图件
│   └── _qa/                # 灰度等质检预览，不用于提交
└── paper/                  # 论文源文件与最终 PDF
```

## 2. 结构化复现清单

在 `PROJECT_ROOT/results/reproducibility.json` 为每个正式运行维护一个条目。Schema 1.0 继续支持旧式字符串输出；Schema 1.1 使用结构化输出，并把任务到 selected/baseline 实际运行的绑定、图件用途和关键论文数值绑定到同一事实源。示例只说明字段，不提供可直接沿用的结果：

```json
{
  "schema_version": "1.1",
  "paper_source": "paper/main.tex",
  "appendix_sources": ["src/q1.py", "src/q2.py", "src/q3.py"],
  "supporting_archive": "supporting_materials.zip",
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
        {"path": "results/paper_results.tex", "kind": "paper_artifact", "purpose": "供论文输入的正式结果宏"},
        {"path": "figures/q1_result.pdf", "kind": "figure", "purpose": "展示终端状态", "supports_claims": ["C-Q1-01"]},
        {"path": "figures/q1_result.png", "kind": "figure", "purpose": "展示终端状态", "supports_claims": ["C-Q1-01"]}
      ],
      "environment": {"python": "以实际查询结果填写", "dependency_file": "requirements.txt"},
      "random_seeds": [],
      "checks": [{"name": "约束满足", "criterion": "按本题定义", "value": "由程序写入", "passed": true}],
      "status": "planned"
    }
  ],
  "claim_bindings": [
    {"id": "C-TASK-A-01", "paper_location": "摘要/语义任务 A", "source_run": "task-A-main", "output_path": "results/task_a_metrics.json", "output_pointer": "/metrics/burn_time"}
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

完整整题、最终论文或完整结果包可在项目内维护 `modeling-brief.md`。开始、会话恢复及 G1/G2/G3 前重新读取，核对题面/交付约束、事实证据锚点、确认决策、假设/单位/坐标、选定模型与基线/验证、未决风险、当前门和下一步；确认有变化后再更新。运行输出仍只归本清单，引用仍归 `citation-ledger.md`，简报不得复制成第二份结果或引文状态源。项目简报的字段与 Gate 语义见 [`cumcm-paper-playbook.md`](../presentation/cumcm-paper-playbook.md)，机器契约见 `check_project_brief.py`；本文件不重复枚举字段：

```bash
python3 <SKILL_ROOT>/scripts/check_project_brief.py <PROJECT_ROOT>/modeling-brief.md \
  --require-profile-contract --require-schema 4 --require-gate G1
```

`paper_source` 可为 `paper/main.tex` 或 `paper/main.docx`。无论源文件类型，最终检查审计实际渲染的 PDF；若提交 DOCX，原生 DOCX 也须保留并检查。

### Schema 1.1 约束

- `role` 只取 `candidate`（进入短名单的对比运行）、`baseline`（简单或保守基线）和 `final`（正式采用运行）；不使用其他自定义值。
- `status` 只取 `planned`、`running`、`passed`、`failed`、`timed_out`、`interrupted`，只描述生命周期，不代替运行角色。
- `model_decisions` 顶层按 `Q1`、`Q2` 等子问题组织，只把任务绑定到 `selected_run` 与可用的 `baseline_run`；选模理由和未决风险归项目简报，不在运行清单重复维护。
- 1.1 的 `outputs` 结构项至少含 `path` 与 `kind`；`kind: figure` 时还要有非空 `purpose`，`supports_claims` 为可选字符串数组。旧项目的 1.0 输出仍是字符串数组。
- 可选顶层 `paper_visuals` 只登记不由运行生成的正文图：每项必须含非空项目内 `path`、`type`（仅 `paper_native_schematic` 或 `external_cited`）和 `purpose`。前者还要有存在的项目内 `source_path`，后者还要有 `citation_id` 与 `usage_note`；路径重复或越界均阻断。它不承载运行数值结果。
- G3 可选维护 `claim_bindings`。每条绑定含 `source_run`、`output_path` 和标准 JSON Pointer 字段 `output_pointer`（如 `/metrics/burn_time`）；`output_path` 必须是该运行声明的 `kind: metrics` 输出。文件存在时检查器会读取 JSON 并解析 Pointer，未生成的计划输出只提示。
- `claim_bindings.id` 在清单内必须唯一。图件不强制绑定结论；但一旦 `supports_claims` 写入 ID，常规检查会提醒未定义引用，G3 的 `--require-claims` 会阻断悬空引用。
- `--require-claims` 仅在 G3 使用，要求存在非空的 headline 数值主张 `claim_bindings`，并核验实际填写的 `supports_claims` 引用；不要求正文每张图都填写该字段，也不要求逐句维护。
- `claim_bindings` 只绑定摘要、结论、最终方案、基线增益、关键误差阈值等 headline 数值；论文定稿前由 Skill 提出候选，人工确认位置、运行和 Pointer 后写入清单，再由 G3 检查器验证。不要求自动扫描全文、逐句绑定或绑定复杂 JSON 的每个深层字段。
- `runtime_budget.timeout_seconds` 必须为正数，`max_attempts` 必须为正整数；受控运行前必须填写。
- `--require-outputs` 在 G3 对 `baseline` 和 `final` 运行严格阻断：状态必须为 `passed`、检查项必须全部通过且声明输出必须存在。`candidate` 是保留的对比证据，失败、未完成或输出未生成只产生提醒，不因候选本身阻断 G3；其结构字段仍必须合法。
- Schema 1.1 的 `paper_source` 是正式论文源文件字符串（如 `paper/main.tex`）；`appendix_sources` 列出正式附录纳入的完整执行源文件；`supporting_archive` 记录实际提交的支撑材料压缩包（没有时明确为空）。结果宏/表由正式 run 的 `outputs` 生成，再由论文源文件输入；它们不属于 `paper_source` 字段。这些字段必须由本题真实路径填写，不得用占位索引冒充代码。
- `kind: figure` 的事实源是正式运行的脚本、输入和参数；PDF、PNG/TIFF 及灰度 QA 是同次确定性运行的派生物。`paper_visuals` 不保存数值结果；`citation_id` 是否真正回链引用台账及使用依据是否充分，属于 G3 人工核验，不由本检查器新增台账解析。
- `appendix_sources` 必须盘点正式入口实际调用的直接/间接辅助模块、配置生成脚本和绘图/压力测试程序。机器门禁只能核对入口脚本及“已声明清单”的包含关系，不能自动证明不存在未声明依赖；G3 前须人工完成源码依赖清点。

使用结构检查器：

```bash
python3 <SKILL_ROOT>/scripts/check_reproducibility.py \
  <PROJECT_ROOT>/results/reproducibility.json \
  --project-root <PROJECT_ROOT>
```

最终证据门增加 `--require-outputs`；G3 需要 headline 数值追溯时再增加 `--require-claims`。`--require-paper-artifacts` 下，TeX `includegraphics` 可由 role=final 的 `kind: figure` 或 `paper_visuals` 登记；未登记的正文图阻断。脚本只核查清单结构、声明路径和可解析的 metrics Pointer，不执行命令，也默认不扫描未声明文件。

G3 的推荐入口（按实际项目补全路径）为：

```bash
python3 <SKILL_ROOT>/scripts/check_reproducibility.py \
  <PROJECT_ROOT>/results/reproducibility.json \
  --project-root <PROJECT_ROOT> \
  --require-outputs --require-claims \
  --require-paper-artifacts --require-appendix-sources
python3 <SKILL_ROOT>/scripts/check_figures.py \
  <PROJECT_ROOT>/results/reproducibility.json --project-root <PROJECT_ROOT>
python3 <SKILL_ROOT>/scripts/check_paper.py \
  <PROJECT_ROOT>/paper/final.pdf --profile cumcm --award-style-audit
```

推荐使用 `--award-style-audit` 做功能覆盖、表现和官方硬项审计；只有用户、题面或模板明确要求精确七章时才使用 `--strict-structure` 内部模板门，二者不是别名。

只有题面显式编号时，才在命令中追加 `--expected-questions <Q>`；无显式编号则省略。CUMCM 正文页数按 playbook 的 26–29 推荐、30 警告、24–25 警告、低于 24 强提醒、超过 30 失败处理；默认不向 `check_paper.py` 传入正文最小页数参数。只有已在 G3 简报记录证据缺口审计与真实原因，且用户/题面明确需要时，才显式使用兼容的最小页数参数。`check_figures.py` 通过后仍需人工审查最终插入宽度；必要时才使用 `--allow-missing-dpi`。矢量容器可含栅格热图，不能因此宣称“纯矢量”。

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
- 进入论文的关键量、稳定性指标和最优性证据应写入正式机器可读结果文件及 `checks`；日志应能把论文表格或图件追溯到具体运行条目。

## 4. 图件的实际视觉终检

图件生成后，在论文采用的最终尺寸下打开导出的 PNG/PDF，而不是只检查绘图代码。逐项确认：

1. 图要证明的结论清楚，图型与证据类型相符；
2. 标题、坐标、量名、单位、图例、刻度、显著数字完整且未裁切；
3. 多曲线除颜色外还用线型、标记或直接标注区分；
4. 图例、注释和置信带不遮挡关键区域；字号在论文实际版面可读；
5. 数值、单位和正文引用与程序输出一致；
6. 生成灰度预览并实际查看，确认不同类别、线条与区域仍可区分。

可对最终 PNG 调用 `save_grayscale_preview()`，把预览写入 `figures/_qa/`。预览只用于质检，不能替代彩色原图，也不能代替人工查看。发现裁切、遮挡、错单位或难以区分时，应修改绘图代码并重新导出。

## 4.1 单一事实源与附录代码

- 正式一次运行应同时生成 JSON/CSV、图件和供论文导入的结果宏/表格；摘要、正文、图题中的数字和结果快照从同一机器可读结果源更新，禁止分别手改。
- 鲁棒性情景函数、阈值和全范围结果由同一程序生成；论文只引用其导出结果。路径存在性、freshness（新鲜度）和版本记录检查不能替代数学正确性，也不能证明防篡改。
- 附录源码必须直接纳入正式执行源文件（LaTeX 用 `\\lstinputlisting` 或 `\\inputminted`），不得手抄、简化、改名、删行或只提交文件索引；索引只能作为导航，不能替代全部代码。

附录的逐问题块先给出本问特异核心函数/签名和主求解逻辑，再在共享区完整引入公共代码一次；PDF 中只看到文件映射时，`check_paper.py` 仅给出 `QUALITY_WARN`，题号到入口映射本身仍是硬契约。`paper_visuals` 中 `paper_native_schematic.path` 必须与论文 TeX 实际消费的 includegraphics 产物路径一致；`source_path` 可以是 SVG 等源文件。该反向消费约束只在 `--require-paper-artifacts` 下阻断，普通复现检查不增加硬门。

## 5. 三道阶段门

为避免与语料标签 `M1` 混淆，阶段门统一命名为 G1/G2/G3：

| 门 | 完整工作流的触发点 | 最低放行证据 |
|---|---|---|
| **G1 建模门** | 主模型正式实现前 | 题目结构与子问依赖明确；候选、基线和选择理由齐全；关键假设与验证计划已定义，参数/状态可辨识性仅在适用任务中定义 |
| **G2 计算证据门** | 用结果写正文前 | 正式命令实际运行；复现清单更新；关键输出与检查通过；图件完成最终尺寸和灰度视觉终检；引用来源已逐条核验 |
| **G3 提交门** | 声称“可以提交”前 | 题目—代码—结果—图表—正文一致；支撑材料可复现；再加载当届规则完成格式、匿名、引用和真实 AI 使用记录审计 |

门禁不限制独立咨询任务：如果用户只要求模型候选、单张图或局部审稿，只执行与该交付物有关的最低检查，并明确哪些完整流程证据尚未建立。任何未通过项应回到对应阶段修复，不能靠文字润色掩盖。

## 6. 放行边界

只有在当前机器或明确记录的等价环境中实际执行了正式命令、核对了输出和检查结果，才能声称“已复现”。清单格式通过、文件存在、程序退出码为零或图像已生成，均不能单独证明数学模型、数据处理或论文结论正确。
