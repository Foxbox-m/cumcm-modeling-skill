---
name: cumcm-modeling
description: Evidence-driven CUMCM mathematical modeling with open model exploration, baseline-first and gap-driven model selection, reproducible computation, validation, optimization, and structured modeling-handoff synthesis. Use for 高教社杯/全国大学生数学建模竞赛 problem decomposition, data audit, model selection, computation, validation, optimization, or G3 modeling handoff.
---

# CUMCM 数学建模

以证据链为主线：题目要求 → 数据与假设 → 数学表示与候选 → 求解 → 验证 → 边界 → G3 建模交接大纲。按两条路径加载资料：局部/单项任务只读当前需要的参考；完整整题、正式结果包或最终大纲综合走完整 G1→G2→G3。不为形式完整加载无关流程。

## Runtime Context Discipline

- 同一任务不重复读取未变化的参考。
- G3 只读取 `references/workflow/detailed-paper-outline.md`，该文件定义建模交接契约而非论文写作规范。
- 大纲内容所需事实按该文件规定从 modeling-brief、G1-H、G2-H、reproducibility 和正式结果定向读取。
- 不加载论文写作、最终章节结构、语态文风、视觉样式、排版或提交格式规范。
- Method Cards 在结构解析、可检验 baseline 和 Gap Check 之后按缺口形成短名单再深读；候选数量保持开放。
- 推导模式仅在独立建模后有翻译缺口时读取；内置蒸馏规则、数学原语与模型卡按当前缺口加载，不读取或依赖实体历史论文库。

## 基本边界

- 当前题面、用户要求与当届真实规则优先于示例、历史经验和默认建议。
- `SKILL_ROOT` 只读；产物写入任意位置的 `PROJECT_ROOT`；运行时只依赖 Skill 内置规则/模型卡与当前项目文件。
- 不虚构数据、结果、引用、奖级或 AI 使用；正式数字必须来自已执行且可追溯的输出，不能用估计或文本推断冒充运行结果。
- 题目来源（CUMCM/MCM/custom）与当前门禁分开；未明确要求时不把默认模板当官方硬项。

## 数学推理主线

1. 题面翻译为数学对象：实体、状态、变量、决策、时空、目标与输出。
2. 推导机理与数据关系，明确假设、单位、参数、约束与不确定性。
3. 主动利用守恒、几何、单调、凸性、尺度与分解结构，不强行套用。
4. 适用时说明目标约束与参数/状态可辨识性，选择解析、数值或统计路线。
5. **按主导风险选择**反例、极限、对照、回代、敏感性或其他决定性检查挑战结论，明确失败条件与有效域；不为形式完整机械叠加验证。

### 模型经济与开放探索

先闭合可检验 baseline，再用 Gap Check 判断处置。只有缺口能由新增模型、表示或机制在现有证据条件下修复时才扩展候选；数据不足补数据/情景化/收窄主张，验证不足加强验证，求解不足补强求解，不用叠模型绕过。缺口时开放模型卡、库外方法和组合表示，默认单步加机制并最小证伪；无关键缺口转向求解、验证和解释，按 `continue/stop`。

停止模型扩张前，先做结构充分性检查：若已识别的答案敏感结构会改变必需输出、决策、误差或解释，必须已在其真正作用层被处理——进入表示/主模型、误差与不确定性、训练验证切分或决策约束，或已有最小证据说明在本题尺度下可忽略。只有当该结构确实改变核心状态关系或估计机制时，才要求升级 primary model。baseline 能运行或能回答题面，不等于足以成为 selected；若本题没有额外答案敏感结构，允许简单 baseline 直接收敛。

新增复杂度默认遵循 `replace-over-stack`：同一中间目标只保留一个 primary modeling mechanism，其余同功能方法降为 baseline、challenger、diagnostic 或 validation；后续模型若已包含并验证了前一模型的必要能力，应替换其主链位置，而不是并列累积。求解器、诊断统计量和可视化方法不计作新主模型；只有经同口径验证的集成确实优于最佳单模型时，才把 ensemble 本身作为一个 primary mechanism。

### 跨问数学连续性

对存在真实依赖的子问题，连续性优先锁定数学接口而非模型名称。若后问研究同一 `canonical object`，只增加协变量、信息、约束、风险或决策层，则默认继承上游的表示尺度、核心关系和随机/观测语义，只把新增内容作为 `delta`；允许因合法信息口径变化在同结构下重新估计参数，这不视为换核。

若后问改变 response/state representation、核心状态关系、时间/空间基函数、随机结构或观测误差语义，则视为 `core replacement`，而不是普通 `delta`。换核必须由目标对象变化、真实观测机制变化、原核心在下游工作域失效，或同口径最小实验的稳定增益之一支持，并说明原接口为何失效、哪些上游事实继续继承。不得仅因题号变化同时重写多个结构轴。

### 表示与决策充分性

结构充分并不自动意味着当前决策表示充分。若 selected 路线在必需输出层出现持续边界锁定、大面积等价解、增加自由度后仍完全同策略、后续新增信息无法在最终决策上体现，或离散交付与底层连续关系明显不匹配，先判断这种简单/退化结果来自数据本身，还是由 representation、objective、evaluation metric 或 search parameterization 压平了差异。

该检查不要求产生更复杂或更丰富的结果。只有存在上述可观察触发证据时，默认进行一次最小且结构独立的替代表示探针；若探针仍支持相同结论，就接受简单结果并停止扩张。不得为了避免简单结论而增加模型、强制多个类别、固定更多自由度或反复更换求解器。

当上游统计/预测结果直接进入下游优化、阈值、排序或策略选择时，模型增量是否保留应同时参考任务对齐的决策证据；平均 RMSE、MAE、AUC 或拟合优度只能作为证据之一。决策证据必须来自题面、预先识别的主导风险或 G1 中事先声明的评价口径，不得在看到结果后挑选最有利的子群或指标。

### 优化型任务额外原则

对显式优化任务，区分 design representation `R(theta)`、用于快速排序的 fast/search evaluation 与用于正式结论的 full/formal validation。先审关键决策自由度与搜索空间，再选择求解算法；高保真评价可用代理或松弛粗搜，但正式候选必须由原始目标与全部硬约束统一验收。表示偏差与数值误差通过结构检查和对照控制，不把中间模型便利当正式依据。**搜索阶段的评价器以决策分辨率（能稳定区分候选排序、约束边界和方案切换）为充分标准，不以物理细节最完整为目标；当评价误差已小于当前决策差距且不改变可行性判断时，新增预算优先用于释放关键自由度、扩大结构搜索或局部改进，而不是继续提高评价保真度。只有评价误差可能改变排名、约束通过/失败或最终方案时，才继续加精。**

## 按任务路由

| 任务 | 首读资源 |
|---|---|
| 题面/拆问/接口 | `references/workflow/problem-analysis.md` |
| 表格/时序数据审计 | `references/workflow/problem-analysis.md`（按需触发 `scripts/audit_dataset.py`） |
| 候选/基线/取舍/预算 | `references/workflow/model-selection.md`，再读短名单 Method Cards |
| 优化变量与搜索 | `references/models/optimization-models.md` |
| G1-H 建模审查 | `references/workflow/human-modeling-review.md`，生成 `PROJECT_ROOT/preliminary-modeling-report.md` |
| G2-H 数据事实审查 | `references/workflow/g2-human-review.md`，生成 `PROJECT_ROOT/G2-H_data_review.md` |
| 推导/验证/复现 | `references/models/mathematical-derivation-primitives.md`、`references/workflow/validation-and-sensitivity.md`、`references/workflow/reproducibility.md` |
| G3 建模交接大纲 | `references/workflow/detailed-paper-outline.md`；只在 G2-H APPROVED 与 fact freeze 后进入 |
| 外部证据核验 | `references/workflow/literature-verification.md` |

模型名称与求解算法分开说明。模型专题卡是开放入口非白名单；现实结构翻译缺口按 `model-selection.md` 路由 `references/models/derivation-patterns.md`；数学原语为 `mathematical-derivation-primitives.md`。

## 证据收敛

按需读取原语/模型卡；完整任务按 `reproducibility.md` 走 G1→G2→G3，主模型前生成 `PROJECT_ROOT/preliminary-modeling-report.md`，等待批准或显式跳过。

G1-H 是 G1 内的人工子门，不新增 G4、不改变 Schema 4 或 `reproducibility.json`。报告为 `PENDING` 时不得开始正式主模型求解、完整训练、大规模优化/仿真或生成正式大纲结论；`REVISE` 时按意见回退并重生成报告。允许在 G1-H 前进行数据审计和与选模有关的轻量诊断，但不包装为正式答案。

G2-H 是 G2 内的人工子门。计算、验证与 G2-A 机器检查后，完整任务必须生成 `PROJECT_ROOT/G2-H_data_review.md` 并等待明确 `APPROVED`；未批准前不得冻结事实或开始 G3 大纲综合。局部任务可带范围记录省略（非批准）。`REVISE`/`ROLLBACK` 回到计算或选模；保持 `PENDING`，批准后冻结事实并进入 G3。

Handoff Synthesis Boundary：G3 只消费 G2-H 已确认并冻结的模型、算法、结果和验证事实，输出 `PROJECT_ROOT/paper-outline.md` 作为下游兼容的建模交接大纲。G3 不撰写论文、不决定最终论文结构/语态/图型/视觉样式、不产生新的正式结果，也不修改模型。发现结果冲突、解释缺口或更优 challenger 时返回 G2。交接大纲允许保留理解模型形成所需的失败候选、实际问题与修正过程，但必须区分正式事实与交接注记。

G3 完成后只检查交接大纲是否覆盖题面任务、模型推导、求解/优化、正式结果、验证、跨问关系和事实来源；可视化意图仅在实际需要时保留。G3 不检查最终章节、语态文风、图型、视觉样式、页数、字体、版式或提交文件。终检推荐运行 `scripts/check_stage.py --stage G3`。

## 外部来源边界

需要理论、事实、标准、算法来源或历史方案比较时，按 `references/workflow/literature-verification.md` 检索并逐条核验公开来源。外部资料只作证据扩展，不替代独立建模、当前数据与实际计算。
