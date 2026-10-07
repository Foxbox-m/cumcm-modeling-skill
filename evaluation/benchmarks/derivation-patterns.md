# Derivation Pattern Layer benchmark fixtures

这些是发布前的结构探针，不是运行时 schema、artifact 或自动路由表。执行者只接收 blind input、independent candidate 与当前 Skill；current gap、expected mode、must preserve 和 validation 留给评审者，不提前透露。以下抽象 fixture 检查构造卡适配；含原始数据、可核算答案及执行边界的局部任务见 [modeling-decisions.md](modeling-decisions.md)。

## B1 — 简单闭合的连续边界

- **blind input**：一个已给出连续位置、明确距离函数和可行阈值的几何判定。
- **independent candidate**：直接用题面距离与阈值定义符号判定，并已覆盖边界两侧。
- **current gap**：无；候选已闭合。
- **expected mode**：no-pattern。
- **must preserve**：实体、距离语义、正负号约定和题面阈值。
- **validation**：解析边界、两侧样例和对象级复核。

## B2 — 几何边界尚未可计算

- **blind input**：连续配置改变实体间的可行/不可行状态，但题面没有可计算的分隔函数。
- **independent candidate**：列出实体和配置变量，暂以状态枚举描述。
- **current gap**：缺少连续边界的数学对象。
- **expected mode**：确认具体缺口后按需构造或重表示；允许局部使用 Pattern 1。
- **must preserve**：实体几何、可行方向、配置域和题面状态定义。
- **validation**：符号边界、两侧状态、域覆盖和对象级复核。

## B3 — 状态演化中的首次事件

- **blind input**：状态随时间演化，题目要求第一次达到状态条件的时刻。
- **independent candidate**：写出状态递推/微分关系，但没有事件接口。
- **current gap**：事件条件与时间定位尚未闭合。
- **expected mode**：针对已确认的具体缺口按需构造或重表示；允许局部使用 Pattern 2。
- **must preserve**：时间方向、初值、事件前后语义和可能的 reset。
- **validation**：bracket、双侧状态、全时域扫描和多事件顺序。

## B4 — 耦合硬约束的自由坐标

- **blind input**：多个变量受等式与不等式硬约束耦合，原始求解反复产生不可行点。
- **independent candidate**：原变量优化并记录约束违反。
- **current gap**：缺少保持可行性的低维表示，且瓶颈已有证据。
- **expected mode**：针对已确认的具体缺口按需构造或重表示；允许局部使用 Pattern 3。
- **must preserve**：全部硬约束、可行分支、目标和边界解。
- **validation**：全约束回代、分支覆盖、奇异性与变换前后目标比较。

## B5 — 生成观测的反演

- **blind input**：未知量通过已知机制生成观测，题目要求估计隐藏量而非单纯预测。
- **independent candidate**：已有 forward relation，但没有把观测误差接入识别目标。
- **current gap**：反演目标、可辨识性和回放接口缺失。
- **expected mode**：针对已确认的具体缺口按需构造或重表示；允许局部使用 Pattern 4。
- **must preserve**：观测语义、forward 方向、噪声假设和不可辨识方向。
- **validation**：forward replay、identifiability、扰动和不同初值/先验。

## B6 — 上游不确定性改变决策

- **blind input**：预测区间进入方案目标或约束，可能改变动作或排序。
- **independent candidate**：用上游点估计做一次确定性决策。
- **current gap**：没有检查不确定性传播及动作切换。
- **expected mode**：针对已确认的具体缺口按需构造或重表示；允许局部使用 Pattern 5。
- **must preserve**：决策目标、约束、动作集合和不确定性的来源范围。
- **validation**：情景/重采样传播、decision switching、约束违反和排序稳定性。

## B7 — 有依据的尺度约化

- **blind input**：完整机制可写，存在无量纲小参数和可分离的快慢尺度。
- **independent candidate**：完整模型已经运行，但在高分辨率下成本过高。
- **current gap**：需要在明确适用域内约化并保留关键输出。
- **expected mode**：针对已确认的具体缺口按需构造或重表示；允许局部使用 Pattern 6。
- **must preserve**：主导机制、边界/事件附近行为、关键输出和完整模型接口。
- **validation**：full/reference 对照、极限检查、边界与长时间误差。

## B8 — 两个彼此独立的缺口

- **blind input**：同一题同时有状态事件接口缺口和独立硬约束参数化缺口。
- **independent candidate**：分别识别了状态演化与耦合约束，但两处均尚未闭合。
- **current gap**：两个可定位、互不替代的结构缺口。
- **expected mode**：辨明两处缺口后，只有两卡各自解决一个 gap 时才组合 Pattern 2 与 Pattern 3。
- **must preserve**：题面任务顺序、事件语义、硬约束和两个接口的独立性。
- **validation**：分别验证事件定位与全约束可行性，再做接口一致性检查。

## B9 — None-of-the-above 复合机制

- **blind input**：带反馈、离散资源和人为规则的复合机制，其关键关系不自然属于六张卡。
- **independent candidate**：保留自定义状态、规则和组合目标的独立模型。
- **current gap**：没有需要 Layer B 修复的结构断链。
- **expected mode**：no-pattern；Layer B abstain。
- **must preserve**：自定义机制、规则顺序、实体关系和组合目标。
- **validation**：规则回放、边界场景、独立基线和端到端输出检查。

## B10 — Lexical bait

- **blind input**：题面包含“碰撞”“约束”“预测”“参数”等词，但数学上是离散计数与规则分类。
- **independent candidate**：按离散状态和题面规则直接计数/分类，已闭合。
- **current gap**：无；诱导词不对应任何 Pattern 前提。
- **expected mode**：no-pattern；false activation 必须为 0。
- **must preserve**：离散性、计数口径、规则优先级和题面分类定义。
- **validation**：穷举小规模状态、规则一致性和反例检查。

## B11 — Ambiguous structure

- **blind input**：连续状态的阈值事件同时出现在一个带边界的决策问题中。
- **independent candidate**：分别列出状态事件与决策边界，但尚不确定是否共用同一数学对象。
- **current gap**：可能是一个接口缺口，也可能是两个真实独立缺口。
- **expected mode**：先辨明共享对象和具体缺口；只使用必要 Pattern，不因相似表面叠加卡片。
- **must preserve**：事件时间、决策目标、边界定义、因果方向和题目特异接口。
- **validation**：仅对真实竞争的表示比较闭合度、反例、接口一致性和复杂度，不强制凑齐单卡、双卡与 no-pattern。

## Release-only shadow A/B

该 A/B 按维护需要用于发布前影子评估，不进入正常竞赛运行，也不创建用户模型 schema 或运行时 artifact。两组使用相同原始输入与任务预算，独立执行，不共享答案、评审判据或另一组输出；记录实际输出与失败，未运行不记为通过。

- **A：Layer B disabled**：只用独立结构推导、候选和验证。
- **B：Layer B enabled**：遵循当前 runtime：独立识别结构与具体缺口，按需读取构造卡，保留题面事实和硬约束，完成决定性验证；不强制使用卡片或额外持久化记录。
- **覆盖**：至少一个简单 fixture、一个复杂标准结构 fixture、一个语料外复合 fixture。
- **指标**：`false activation 0`、`unsupported structural change 0`、`problem-specific preservation` 全保留、`pattern leakage 0`、`unsupported formal claim 0`。
