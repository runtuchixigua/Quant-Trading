---
week: 21
title: "机器学习稳定性、漂移与解释"
phase: "稳健验证与机器学习"
reading_order:
  - "先审计 walk_forward_folds.csv 的训练与预测边界"
  - "再比较 model_importance.csv 的逐折解释稳定性"
  - "随后核对 drift_degradation_drill.json 与 summary.csv"
  - "最后完成 homework.md 并检查 acceptance.json 和 manifest.json"
artifacts:
  model_importance.csv:
    summary: "逐折逐特征保存模型解释值、解释类型及对应的训练和首次预测边界。"
    columns:
      fold: "与 walk-forward 折表对应、从 0 开始的重训练折编号。"
      feature: "被解释的输入特征名，取值为 value、momentum、quality 或 noise。"
      importance: "该折模型对该特征给出的解释值；Ridge 模型下为标准化后的回归系数。"
      kind: "解释值类型，本周 Ridge 模型为 coefficient，其他模型可为原生或置换重要性。"
      train_end: "产生该解释值的模型所使用的最后一个训练日期。"
      prediction_start: "该折模型首次用于样本外预测的日期。"
  walk_forward_folds.csv:
    summary: "保存每次 walk-forward 重训练的训练区间、计划预测区间、样本量和模型名称。"
    columns:
      fold: "从 0 开始的重训练折编号。"
      train_start: "该折模型训练窗口的首个日期。"
      train_end: "该折模型训练窗口的最后日期，已扣除标签实现期。"
      prediction_start: "该折模型开始生成样本外预测的日期。"
      prediction_end: "该折模型在下一次重训前计划覆盖的最后预测日期。"
      n_train_dates: "该折训练窗口包含的唯一交易日数量。"
      n_train_samples: "该折标签非缺失、实际参与拟合的横截面样本行数。"
      model: "该折使用的模型名称，本周默认为 ridge。"
  drift_degradation_drill.json:
    summary: "保存特征分布漂移故障、PSI、停止判断、降级方案和人工恢复门槛。"
  summary.csv:
    summary: "以指标名和数值的长表汇总 walk-forward 折数、解释行数、PSI 和降级触发状态。"
    columns:
      unnamed_index: "CSV 中未显式命名的索引列，保存本周汇总指标名称。"
      week21: "对应第 21 周汇总指标的值。"
  homework.md:
    summary: "要求量化解释稳定性、研究 PSI 敏感性并补全降级治理责任。"
  acceptance.json:
    summary: "记录第 21 周机器可读的验收状态和验收条件。"
  manifest.json:
    summary: "记录第 21 周运行模式、产物路径、讲义引用和产物字段词典。"
---

# 第 21 周：机器学习稳定性、漂移与解释

## 学习目标（本周目标）

机器学习模型上线后的关键问题不是“特征重要性排第几”，而是训练边界是否无泄漏、解释是否跨折稳定、输入分布是否漂移，以及异常发生时系统如何降级。本周完成后，你应能：

1. 审计 walk-forward 每次训练和预测的时间边界。
2. 区分线性系数、原生重要性和 permutation importance。
3. 计算并解释 PSI，知道它只检测分布变化，不证明模型失效。
4. 把漂移阈值连接到停止、降级、影子运行和人工恢复。
5. 用“跨折符号、排序、尺度”而非单次重要性讲模型稳定性。

## 前置知识

需要理解横截面特征表的 `(date, symbol)` MultiIndex、未来收益标签、训练/预测隔离、Ridge 回归和标准化。还应知道缺失值填充和缩放也属于模型拟合，必须只使用训练折数据。

## 核心理论

本周核心理论把 walk-forward 时间隔离、逐折模型解释、PSI 漂移检测和受控降级串成闭环。任何稳定性结论都以训练边界正确为前提，任何恢复结论都必须有监督指标和人工证据支持。

## 理论一：walk-forward 与标签隔离

对预测日位置 \(i\)，标签期限为 \(H\)，代码令

\[
\text{train\_end}=i-H,
\qquad
\mathcal T_i=\{d_{\max(0,i-H-W)},\ldots,d_{i-H-1}\},
\]

其中 \(W\) 是训练窗口长度。预测从 \(d_i\) 开始，因此训练标签在预测日前已经完整实现。模型每隔 `retrain_every` 个日期重训一次；中间预测沿用最近模型。

快速模式：`min_train_dates=25`、`train_window_dates=40`、`label_horizon_dates=2`、每 10 日重训。完整模式：60、100、2、20。随机种子固定为 202407。数据共有四个特征：`value`、`momentum`、`quality`、`noise`；标签的真实合成关系中前三者系数分别为 0.025、0.015、-0.01，`noise` 没有结构性贡献。

Ridge 流水线依次进行训练折中位数填充、标准化和回归：

\[
\widehat\beta=\arg\min_\beta
\|y-X\beta\|_2^2+\alpha\|\beta\|_2^2.
\]

标准化后系数可用于同一折内的方向和相对强度比较，但跨折仍会受样本分布和正则化影响。

## 理论二：逐折解释与稳定性

实现按以下优先级生成解释：

1. 最终估计器有 `coef_`：记录 `coefficient`。
2. 有 `feature_importances_`：记录 `native_importance`。
3. 否则用训练折上的 permutation importance，评分为负均方误差。

解释值的含义依 `kind` 而异，不能把不同类型混在同一尺度比较。稳定性至少包括：

- 方向稳定：有符号解释在各折是否反复翻转。
- 排名稳定：绝对重要性排序是否大幅变化。
- 幅度稳定：是否由少数折异常放大。
- 经济稳定：方向是否符合预先提出的机制，而非事后故事。

“重要”不等于“因果”；高度相关特征可互相替代，使单个重要性下降。

## 理论三：PSI

PSI 使用基准样本分位点构造分箱。设第 \(j\) 箱基准占比为 \(p_j\)，当前占比为 \(q_j\)，则

\[
PSI=\sum_j(q_j-p_j)\ln\frac{q_j}{p_j}.
\]

实现将比例下限截为 \(10^{-6}\)，避免零频导致对数无定义；首尾边界扩为 \(-\infty,+\infty\)。若基准为常量，当前仍相同则 PSI=0，否则为无穷大。

本实验把 `value` 特征前后两段分开，并给当前段整体加 2.0，故制造显著漂移。停止阈值为 0.10，比 `MonitorConfig` 默认 0.25 更严格。PSI 是无监督输入漂移指标：它不知道标签、预测误差或策略 PnL，所以：

- PSI 高：输入发生变化，需要调查，不等同模型已失效。
- PSI 低：分箱边际分布稳定，不保证特征关系或联合分布稳定。
- PSI 受分箱、样本量和基准窗口影响，阈值必须经历史校准。

## 理论四：自动停止与受控恢复

`evaluate_stop_rules` 将 PSI 与阈值比较；达到或超过阈值时原因包含 `PSI_DRIFT`，`should_stop=true`。本周演练的降级方案是“停用 ML 打分，降级到冻结的等权规则组合”。这要求备用组合在故障前已经批准、版本冻结并持续验证，不能在事故中临时发明。

恢复门槛为：数据修复、PSI 低于阈值、影子运行通过，最后人工恢复。自动停止偏向安全；自动恢复容易在间歇故障中反复启停，因此必须有人复核根因和证据。

## 阅读顺序

先证明每折没有时间泄漏，再比较解释稳定性，随后阅读漂移与降级演练，最后用摘要做一致性复核。不能先根据 PSI 或重要性决定模型好坏，再回头检查边界。

## 实验步骤

1. 先读 `walk_forward_folds.csv`，确认每折 `train_end < prediction_start`，并理解两日期间至少留出标签实现期。
2. 读 `model_importance.csv`，按 `fold` 和 `kind` 分组，比较四个特征的符号、绝对值排名。
3. 读 `drift_degradation_drill.json`，核对 PSI、阈值、停止原因、降级和恢复门槛。
4. 读 `summary.csv`，复核折数、重要性行数、PSI 与是否触发降级。
5. 最后检查作业、验收与 manifest。

## 逐文件与字段解释（逐产物与字段字典）

### `walk_forward_folds.csv`

- `fold`：从 0 开始的重训练折编号。
- `train_start`、`train_end`：该次拟合使用的训练日期边界。
- `prediction_start`、`prediction_end`：该模型计划覆盖的预测日期边界。
- `n_train_dates`：训练日期数。
- `n_train_samples`：训练折中标签非缺失的横截面样本数。
- `model`：配置中的模型名，本周默认 `ridge`。

注意 `prediction_end` 是该次重训计划覆盖边界；末折可能短于 `retrain_every`。审计重点是训练截止日，而不是只数折数。

### `model_importance.csv`

- `fold`：与折表对应。
- `feature`：`value`、`momentum`、`quality` 或 `noise`。
- `importance`：解释值；Ridge 下为标准化流水线最终估计器系数。
- `kind`：本周应为 `coefficient`，其他模型可能为原生或置换重要性。
- `train_end`：解释对应模型的训练截止日期。
- `prediction_start`：该模型首次预测日期。

每折通常有四行，因此 `importance_rows` 应等于折数乘特征数。`quality` 的预设关系为负；`noise` 理论上接近零，但有限样本下不必恰为零。

### `drift_degradation_drill.json`

- `fault`：固定为 `FEATURE_DISTRIBUTION_SHIFT`。
- `psi`：基准与平移后当前样本的 PSI。
- `threshold`：0.10。
- `should_stop`：监控是否要求停止。
- `reasons`：停止原因数组，应包含 `PSI_DRIFT`。
- `degradation`：停用 ML、切换冻结规则组合的方案。
- `recovery_gate`：修复、PSI、影子运行和人工批准条件。

### `summary.csv`

- `folds`：walk-forward 折数。
- `importance_rows`：逐折逐特征解释行数。
- `psi`：本次漂移值。
- `degradation_triggered`：停止规则是否触发。

### `homework.md`、`acceptance.json`、`manifest.json`

作业文件要求比较解释稳定性并补齐治理责任；验收文件关注逐折留档和降级恢复门槛；manifest 用于核对本次运行模式及文件完整性。

## 图表解读（无预生成图时的建议）

本周默认没有图片产物。建议将 `walk_forward_folds.csv` 画成逐折训练与预测区间时间轴；将 `model_importance.csv` 画成“折×特征”热力图，系数类使用以零为中心的发散色标，并按 `kind` 分面；另画每个特征重要性随折变化的折线，突出符号翻转。PSI 可画参考/当前分箱占比并列柱图，而不是只显示一个总值；总 PSI 超阈值时还要指出贡献最大的箱。

## 动态指标判断

- 每次重训检查 `train_end < prediction_start`、训练样本数和预测覆盖长度；边界失败时直接停止评价后续性能。
- 滚动计算特征符号一致率、绝对重要性排名和四分位距。核心特征连续翻转或 `noise` 长期进入前列，应降级稳定性评级。
- PSI 按固定基准窗口、分箱和阈值监控，同时等待标签成熟后联合查看 Rank IC、误差与 PnL；PSI 单独只能触发调查或预设降级，不能证明概念漂移。
- 恢复需连续窗口低于阈值、监督指标通过、影子运行通过并人工批准，避免指标在阈值附近抖动导致频繁启停。

## 判断框架

先判断“模型是否可审计”，再判断“模型是否稳定”，最后决定“是否可运行”：

1. 若训练边界泄漏，所有性能和解释作废。
2. 边界正确后，检查重要性方向与排名是否跨折稳定。
3. 再检查 PSI 是否超过经校准阈值。
4. PSI 超限时执行预先批准的降级；同时用标签延迟后的 IC、误差和 PnL 判断模型是否真的失效。
5. 只有根因关闭、影子运行通过且人工批准后恢复。

## 常见误区

1. 在全样本先填充和标准化，再做 walk-forward。
2. 忽略标签期限，只要求训练日早于预测日一天。
3. 把 Ridge 系数绝对值直接与树模型原生重要性比较。
4. 把 PSI 高解释为预测准确率下降的证明。
5. 把 PSI 低解释为模型安全。
6. 漂移发生后才临时设计备用策略。
7. 告警消失就自动恢复，没有影子运行和人工批准。
8. 只展示平均重要性，隐藏折间符号翻转。

## 思考题

1. 为什么标签期限为 2 时，训练截止位置使用 `i-2` 且切片不含该端点？
2. 输入边际 PSI 都很低时，联合分布仍可能怎样漂移？
3. 相关特征会怎样影响系数和 permutation importance 的稳定性？
4. 若 PSI 超限但实时 IC 未下降，应立即停机、降级还是继续？还需要哪些证据？

## 作业提示（作业）

1. 按折计算每个特征的重要性符号一致率、排名中位数和四分位距，解释 `noise` 是否被错误依赖。
2. 用不同基准窗口和 `bins` 重算 PSI，说明阈值敏感性。
3. 为降级流程补齐负责人、通知对象、最大响应时间、影子运行长度和恢复签字人。
4. 设计一个 PSI 检测不到、但会导致模型失效的概念漂移案例，并给出监督指标。

## 验收标准

- 所有折均满足训练截止早于预测开始，并能解释标签实现隔离。
- 每折每特征都有解释记录，且结论区分 `kind`。
- 能明确陈述“PSI 检测分布变化，不证明模型失效”。
- 漂移超阈值时有明确停止原因、冻结备用方案和人工恢复门槛。
- summary 与三个核心产物一致，manifest 所列路径均存在。
