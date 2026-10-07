# Derivation Patterns：从现实结构到数学表示

本文件提供可选的构造与重表示模式，不是模型白名单或固定流程。先独立识别当前任务的对象、事实和硬约束；若仍有具体的“现实结构 → 数学对象”缺口，再按需读取相关卡片。模式可帮助提出或重表示候选，但不替代当前题目的独立推导。

## 使用契约

- 具体缺口触发按卡片读取；卡片可帮助构造或重新表示候选，也可按题目需要适配、组合或跳过。
- 保留题面/数据来源的事实、硬约束、数据语义和因果顺序；模式不能凭自身惯例覆盖它们。
- 在构造后做一次决定性的兼容性或证伪检查，例如回代约束、检查极限/边界、前向重演或小规模对照；不合适时继续独立推导。
- 不要求 snapshot、schema、artifact、专门术语或持久化审计记录。

## Modeling Core

按需读取本部分。每张卡提供 `Use only if`、`Reject / Abstain if`、`Construct`、`Output`、`Validate` 五个快速入口；先扫查适用与不适用条件，再按当前缺口选择构造和验证内容。

## Pattern 1 — Signed Feasibility Boundary from a Continuous Configuration

### Use only if

答案取决于连续配置空间中的可行/不可行边界，且该边界能由当前题的真实实体、几何或状态量定义。

### Reject / Abstain if

- 题目只有离散分类或计数，没有连续边界。
- 关键对象不能定义连续状态，或状态变化是跳跃的而简单 signed margin 不足。
- margin 的正负没有题意语义，或当前候选已经给出等价且可验证的边界表示。

### Construct

从当前实体与连续配置 `z` 出发，构造 `g(z)>0`、`g(z)=0`、`g(z)<0`，分别对应题目真实的三种状态；不得凭卡片引入新的实体或机制。

### Output

输出 feasibility margin、separation function 或 boundary equation，并标明符号方向和适用域。

### Validate

用解析特例、边界两侧状态、连续域覆盖和对象级复核检查符号、边界位置与题意一致。

> 末尾非激活示例：某些碰撞、遮挡、覆盖或可达域情境可能呈现此结构；词语本身不能激活本卡。

## Pattern 2 — Guarded Event from State Evolution

### Use only if

已有连续或明确离散的状态演化 `x(t)`，且问题关心某状态条件第一次、再次成立的时间、顺序或活动区间。

### Reject / Abstain if

- 没有可信的状态演化，或事件只是人为分组而非状态变化。
- event condition 不能唯一表达题意，或瞬时跳变需要 reset/hybrid 机制而普通根不够。
- 当前候选已定义等价的事件接口，继续套用只会同义改写。

### Construct

定义与题意一致的 guard `g(x(t),t)=0`，先写事件前后语义，再求 event time、顺序或区间；必要时保留离散 reset 和多事件规则。

### Output

输出 event time、order、switching state 或 active interval，以及事件判定所依赖的状态量。

### Validate

做 bracket、双侧状态检查、全时域扫描和多事件顺序复核，确认没有漏掉边界事件或伪根。

> 末尾非激活示例：某些切换、到达或阈值情境可能呈现此结构；题面出现事件词不构成激活条件。

## Pattern 3 — Feasible Coordinates from Coupled Hard Constraints

### Use only if

原始变量并非独立，自由度被耦合硬约束显著压缩，且约束表示本身确实阻碍求解或完整表达。

### Reject / Abstain if

- 原问题已经是简单凸/线性标准形式，约束不是实际瓶颈。
- 参数化可能遗漏重要可行分支，或映射比原问题更病态、不可逆或不可解释。
- 仅因为变量很多就想换坐标，没有结构证据。

### Construct

识别当前题的真实自由变量 `theta`，构造 `x=Psi(theta)` 或有来源的 projection/repair，使候选始终满足硬约束；保留全部必要分支。

### Output

输出真实自由度上的可行表示、映射域和边界分支，而不是一个未经证明的降维近似。

### Validate

全约束回代、可行域覆盖、边界分支和映射奇异性检查必须通过；比较变换前后的目标与可行解。

> 末尾非激活示例：某些配置、资源或网络情境可能具有耦合自由度；“约束”一词不能激活本卡。

### Search-family parameterization（条件式分支）

#### Use only if

原始优化问题的搜索空间过大或评价昂贵，且存在可解释的结构族、局部扰动或可行修复策略，能够作为一条可验证的搜索路径。

#### Reject / Abstain if

- 没有结构依据说明 `x=Psi(theta)`、扰动、repair 或 swap 为什么覆盖当前风险相关的方案；
- 把搜索参数化误写成与原问题等价的变量变换，或据此声称覆盖全部原始可行域/得到原问题全局最优；
- 原始约束和完整目标无法对每个候选回代检查。

#### Construct

构造 `x=Psi(theta)` 作为搜索策略，而非等价变换；说明结构依据、开放自由度、遗漏边界和适用范围。按风险检查明显不同的结构族，或对原变量实施局部 `perturb/repair/swap`，必要时与代理/低分辨率粗搜配合。

#### Output

输出搜索族、参数域、已覆盖结构、已知表示偏差和未覆盖边界；明确不能据此声称原问题全局最优。

#### Validate

每个正式候选都用原始目标与完整硬约束验收；检查不同结构族、原变量局部动作和边界案例是否产生实质差异，并记录搜索不足与停止依据。

## Pattern 4 — Inverse Formulation from a Generative Observation Map

### Use only if

未知量通过可解释的生成/观测过程产生数据，且题目要求识别隐藏量、参数或其不确定性。

### Reject / Abstain if

- 没有可信 forward relation，或数据只支持相关性预测而非反演。
- 观测无法区分候选参数，或现有候选尚未满足可辨识性要求。
- 目标只是预测，不要求识别隐藏参数；此时反演会制造伪精度。

### Construct

先从当前题写出 `theta` 经过 forward relation 和 observation operator 生成 `y_hat(theta)`，再定义 inverse objective、likelihood 或后验；明确噪声和边界来源。

### Output

输出估计参数、可辨识的参数集合或 posterior，并列出不可辨识方向和不确定性。

### Validate

做 forward replay、identifiability 检查、扰动测试以及不同初值/先验的比较；反演结果必须能回放到观测空间。

> 末尾非激活示例：某些传感、校准或几何观测情境可能呈现此结构；“参数”一词不能激活本卡。

## Pattern 5 — Decision Sensitivity from Upstream Uncertainty

### Use only if

上游不确定量进入最终决策函数、约束或排名，并且其范围可能改变最终动作或方案顺序。

### Reject / Abstain if

- 下游决策对上游误差解析上不敏感，或不确定性远小于决策容差且已有充分证明。
- 问题只要求预测而非决策，或上游模型尚未验证。
- 传播会制造伪精度，当前模型没有定义不确定量及其支持范围。

### Construct

把上游 uncertainty 传播至 `J(x;xi)`、`g(x;xi)`、ranking 或最终 action，区分情景、区间、bootstrap、posterior 和风险度量的来源。

### Output

输出 decision stability、switch region、robust decision 或 risk-aware decision，并说明动作切换的条件。

### Validate

做情景/重采样/后验/区间传播，并直接检查 decision switching、约束违反和结论排序是否稳定。

> 末尾非激活示例：某些风险评估或方案比较情境可能呈现此结构；“预测”一词不能激活本卡。

## Pattern 6 — Reduced Representation from Scale Separation

### Use only if

完整模型已经建立或至少可写，且存在可证明或可测量的尺度差异、无量纲小参数、时间尺度或主导平衡。

### Reject / Abstain if

- 完整机制尚不清楚，或“复杂/计算慢”之外没有尺度依据。
- 被删项可能在边界、长时间或事件附近成为主导。
- reduced model 无法与 reference 输出比较，或简化会改变题面必须保留的结构。

### Construct

由无量纲量、小参数、时间尺度或主导平衡推导 reduced representation；明确删项、适用域、误差量级和恢复完整模型的边界。

### Output

输出低维状态、简化方程或分阶段近似，并附与完整表示的接口。

### Validate

做 full/reference comparison、极限检查和关键输出误差评估，覆盖边界、长时间和事件附近等高风险区域。

> 末尾非激活示例：某些多尺度、慢快变量或近似计算情境可能呈现此结构；“复杂”一词不能激活本卡。

