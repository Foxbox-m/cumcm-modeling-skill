---
name: cumcm-modeling
description: Evidence-driven CUMCM mathematical modeling with open model exploration, assumption checks and, when applicable, parameter-identifiability checks, reproducible computation, citation verification, and award-paper presentation. Use for 高教社杯/全国大学生数学建模竞赛 problem decomposition, data audit, model selection, validation, figures, paper drafting, supporting materials, or submission review.
---

# CUMCM 数学建模

本 Skill 以证据链为主线：题目要求 → 数据与假设 → 数学表示与候选模型 → 求解 → 验证 → 结论边界 → 论文。按任务比例加载资料：快速咨询只读相关步骤；完整建模采用“精简建模简报 + 实际计算 + 与风险匹配的验证”；最终交付再启用复现、提交和视觉检查。不要为了形式完整而加载或执行无关流程。

## 基本边界

- 当前题面、用户要求和当届真实规则优先于示例、历史经验和本 Skill 的默认建议。
- `SKILL_ROOT` 只读；项目、结果、论文和临时产物写入任意位置的 `PROJECT_ROOT`，不得假定旁边存在语料库。
- 不虚构数据、结果、引用、奖级或 AI 使用；正式数字必须来自已执行且可追溯的输出，不能用估计或文本推断冒充运行结果。
- 题目来源（`CUMCM|MCM|custom`）与交付 profile（`CUMCM|MCM_NATIVE|research_report`）分开判断；没有明确要求时，不把默认模板当作官方硬项。

## 数学推理主线

1. 把题面翻译成数学对象：实体、状态、变量、观测、决策、时间、空间、目标与输出。
2. 从题面事实、机理和数据推导关系，明确假设、单位、参数、约束、噪声和信息缺口。
3. 主动利用守恒、几何、单调性、凸性、对称性、尺度、界、可行域和分解等结构，但不为凑方法强行套用。
4. 在适用时说明目标、约束、不确定性与参数/状态可辨识性，选择解析、数值、统计或组合求解路线。
5. 用特殊情形、反例、极限、对照、守恒/约束回代和敏感性挑战结论，并写清有效域、失败条件与可推广范围。

## 按任务路由

| 需要处理 | 首读资源 |
|---|---|
| 题面理解、拆问、任务接口 | `references/workflow/problem-analysis.md` |
| 候选模型、基线、取舍与赛时预算 | `references/workflow/model-selection.md`；再读相关 `references/models/` 模型卡 |
| 数学推导、结构原语与推广边界 | `references/models/mathematical-derivation-primitives.md` |
| 现实结构到数学对象的具体翻译缺口 | `references/models/derivation-patterns.md`（由 `model-selection.md` 按需路由） |
| 假设、辨识、验证、稳健性与敏感性 | `references/workflow/validation-and-sensitivity.md` |
| 实际运行、结果事实源与复现 | `references/workflow/reproducibility.md` |
| 普通论文论证与交付 | `references/presentation/cumcm-paper-playbook.md` |
| 摘要起草与自审 | `references/presentation/abstract-writing.md`；规则要求另读 `references/core/competition-rules.md` |
| 排版、Word/LaTeX、图件与最终页面 | `references/presentation/award-paper-layout.md`、`references/presentation/word-workflow.md`、`references/presentation/award-paper-visualization.md` |
| 文献来源、提交与 AI 合规 | `references/workflow/literature-verification.md`、`references/workflow/submission-and-ai-compliance.md` |

模型名称与求解算法必须分开说明。模型专题卡是开放式候选入口，不是白名单；可使用库外模型、机理—数据融合和组合表示，但须回到当前题目的结构、数据、约束、适用时的可辨识性和验证证据。

## 证据收敛

先从题面和附件独立形成至少一个实质候选，再用简报记录目标、变量/状态、硬约束、数据/机理、子问接口、候选、基线和验证思路。按需读取原语或模型卡；模型已闭合时不因“完整”而增加方法。保留与主要风险匹配的简单基线，启发式或随机求解要说明约束处理、停止条件和重复运行稳定性。完整整题、最终论文、正式 CUMCM 交付或完整结果包，无论交互轮次多少，均按 `reproducibility.md` 与 playbook 完成现有 G1→G2→G3；只有明确局部咨询或单项任务才省略不相关门。

论文正文只写题目事实、数学对象、推导、求解、正式结果、机制、决定性证据和边界；Schema、Gate、运行清单和内部审计属于项目记录。最终交付时，按 playbook 路由复现、提交、规则、匿名、引用、图文和页面检查；机器检查不能代替数学与人工判断。

## 可选外部语料

外部论文库仅在任务确实需要来源追溯、历史方案比较或精确引用/页码核验时使用，或在用户明确要求时使用；它不是正常依赖，也不替代独立建模、实际计算和验证。语料不可用时，删除或收窄无法独立支撑的历史主张。
