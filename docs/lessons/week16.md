---
week: 16
title: "多因子诊断与冗余控制"
phase: "因子、风险与优化"
reading_order:
  - "先读 factor_sample.csv：明确因子、目标与顺序切分"
  - "再读 factor_correlations.csv：定位高相关因子对"
  - "最后读 factor_diagnostics.csv：联合判断 VIF、FDR 与样本外边际贡献"
artifacts:
  factor_sample.csv:
    summary: "保存五个合成因子与前瞻收益目标的顺序样本。"
    columns:
      value: "具有真实预测系数的价值因子。"
      quality: "具有真实预测系数的质量因子。"
      momentum: "具有真实预测系数的动量因子。"
      value_clone: "与 value 高度相关的复制因子。"
      noise: "没有真实预测系数的噪声因子。"
      forward_return: "由有效因子线性组合与噪声生成的前瞻收益目标。"
  factor_correlations.csv:
    summary: "五个特征的 Pearson 相关矩阵。"
    columns:
      unnamed_index: "CSV 未命名索引列，保存相关矩阵的行因子名。"
      value: "各行因子与 value 的 Pearson 相关系数。"
      quality: "各行因子与 quality 的 Pearson 相关系数。"
      momentum: "各行因子与 momentum 的 Pearson 相关系数。"
      value_clone: "各行因子与 value_clone 的 Pearson 相关系数。"
      noise: "各行因子与 noise 的 Pearson 相关系数。"
  factor_diagnostics.csv:
    summary: "按因子保存完整 OLS、VIF、BH-FDR 与样本外边际 MSE 诊断。"
    columns:
      unnamed_index: "CSV 未命名索引列，保存因子名称。"
      coefficient: "训练集完整 OLS 的因子系数。"
      standard_error: "训练集完整 OLS 的系数标准误。"
      t_value: "系数除以标准误得到的 t 值。"
      p_value: "根据 t 值正态近似得到的双侧原始 p 值。"
      vif: "该因子被其余因子联合解释程度对应的方差膨胀因子。"
      adjusted_p_value: "Benjamini-Hochberg 方法校正后的 p 值。"
      reject: "校正 p 值是否不大于 0.05。"
      marginal_oos_mse_reduction: "删除该因子后的测试 MSE 减去完整模型测试 MSE。"
  homework.md:
    summary: "本周因子冗余、多重检验与边际贡献作业。"
  acceptance.json:
    summary: "本周程序化验收条件。"
  manifest.json:
    summary: "本周运行模式与产物清单。"
---

# 第 16 周：多因子诊断与冗余控制

## 学习目标

本周不再问“单个因子是否显著”，而是问它在其他因子存在时是否仍有独立信息。你将联合使用相关矩阵、VIF、OLS、Benjamini–Hochberg FDR 和样本外边际 MSE，识别共线、伪发现和没有增量预测价值的因子。

完成后，你应能解释：低 p 值不等于可交易价值；高相关不等于完全冗余；VIF 衡量的是一个因子被所有其他因子解释的程度；最终保留决策应结合样本外增量、稳定性、经济逻辑和成本。

## 前置知识

- 掌握相关系数、线性回归、标准误、t 值和 p 值。
- 理解训练集与测试集必须隔离。
- 了解多重假设检验会提高至少一次假阳性的概率。
- 会解释均方误差 MSE，且知道 MSE 越小越好。

## 核心理论

对因子 \(x_j\)，用其余因子回归得到 \(R_j^2\)，方差膨胀因子为

\[
VIF_j=\frac{1}{1-R_j^2}.
\]

\(VIF\) 越高，系数方差被共线性放大得越严重。完全共线或常量列在工具实现中返回无穷大。经验阈值 5 或 10 只能用于提示，不能机械删除。

多因子 OLS 为

\[
y=\beta_0+X\beta+\varepsilon.
\]

本实验用正态近似从 \(|t|\) 计算双侧 p 值。对 \(m\) 个 p 值排序为 \(p_{(1)}\le\cdots\le p_{(m)}\)，BH 方法控制假发现率，并生成单调校正后的

\[
\tilde p_{(i)}
=\min_{k\ge i}\left(\frac{m}{k}p_{(k)}\right)\wedge 1.
\]

样本外边际贡献通过“删除一个因子后测试 MSE 增加多少”定义：

\[
\Delta_j=MSE_{\text{reduced}(-j)}-MSE_{\text{full}}.
\]

\(\Delta_j>0\) 表示删除该因子使误差变大，即该因子在这次切分中有正的边际贡献；\(\Delta_j<0\) 表示删除后反而更好。

## 实验步骤：相关、VIF、FDR 与边际贡献

完整模式使用 700 个顺序观测，`quick` 模式为 180 个；随机种子固定为 16。

1. 构造 `value`、`quality`、`momentum` 三个独立基础因子。
2. 构造 `value_clone = 0.92 * value + noise`，制造高相关与高 VIF。
3. 加入纯噪声因子 `noise`。
4. 目标 `forward_return` 由 value、quality、momentum 的线性组合加噪声生成；`value_clone` 和 `noise` 没有独立的真实系数。
5. 前 70% 为训练集，后 30% 为测试集，不随机打乱。
6. 在训练集拟合含截距的完整 OLS，计算系数、标准误、t 值和 p 值。
7. 计算训练特征 VIF，并对全部因子 p 值执行默认 \(\alpha=0.05\) 的 BH-FDR。
8. 在测试集计算完整模型 MSE；逐个删除因子、重新训练，记录 reduced MSE 与 full MSE 之差。

由于 `value` 与 `value_clone` 高度相关，二者会竞争同一信号，系数和显著性可能不稳定。边际贡献也是“在其他因子已存在时”的条件贡献，不等于单因子预测能力。

## 逐文件与字段解释

### `factor_sample.csv`

- `value`：真实有效基础因子。
- `quality`：真实有效基础因子。
- `momentum`：真实有效基础因子。
- `value_clone`：value 的高相关复制因子。
- `noise`：无真实预测系数的噪声因子。
- `forward_return`：目标前瞻收益。

文件按生成顺序排列；前 70%/后 30% 对应实验训练/测试切分。

### `factor_correlations.csv`

五个特征的 Pearson 相关矩阵。行列名称相同，对角线为 1，矩阵对称。重点观察 `value` 与 `value_clone`。

### `factor_diagnostics.csv`

行索引为因子名，字段为：

- `coefficient`：训练集完整 OLS 系数，不含截距行。
- `standard_error`：系数标准误。
- `t_value`：系数除以标准误。
- `p_value`：正态近似双侧 p 值。
- `vif`：该因子对其余因子回归得到的 VIF。
- `adjusted_p_value`：BH 单调校正 p 值。
- `reject`：校正 p 值是否不大于 0.05。
- `marginal_oos_mse_reduction`：删除该因子后的测试 MSE减去完整模型测试 MSE；名字中的 “reduction” 表示完整模型相对删除模型减少的误差。

### 框架产物

- `homework.md`：冗余处理、FDR 对照、边际贡献判断。
- `acceptance.json`：相关与 VIF、BH-FDR、样本外边际贡献三项验收。
- `manifest.json`：运行模式与完整产物。

## 阅读顺序

1. 从 `factor_sample.csv` 明确数据生成结构和顺序切分。
2. 读 `factor_correlations.csv`，找到高相关因子对。
3. 在 `factor_diagnostics.csv` 先看 `vif`，再比较原始与校正 p 值。
4. 最后看 `marginal_oos_mse_reduction`，判断显著性是否转化为测试集增量。
5. 将三类证据放在一起，而不是按单一阈值自动删因子。

## 图表解读

本周 runner 不生成图表，因为诊断结论需要把相关、VIF、FDR 和样本外贡献逐因子对齐。建议将 `factor_correlations.csv` 画成带数值标注的热力图，重点查看 `value` 与 `value_clone` 的高相关块；再将 `factor_diagnostics.csv` 的 `vif` 与 `marginal_oos_mse_reduction` 画成并列条形图，并用颜色表示 `reject`。高 VIF 且边际贡献接近 0 的因子是冗余候选，但若不同时间切分中符号变化，图上的单次排序不能作为永久删除依据。

## 动态指标判断

- `value` 与 `value_clone` 的绝对相关应明显最高，两者 VIF 通常也最高。
- `adjusted_p_value` 不应小于对应 BH 排序逻辑允许的值，`reject` 应与 `<=0.05` 一致。
- `quality`、`momentum` 和 value 信号整体上应更可能有正边际贡献，但有限样本可能波动。
- `noise` 没有真实信号，不应因一次低 p 值就被保留。
- 正边际贡献仅表示当前一次时间切分中删除它会恶化 MSE；需要滚动切分验证稳定性。
- 高 VIF 影响系数可解释性和稳定性，但并不必然恶化整体预测。

## 常见误区

- 只看两两相关，忽略一个因子可被多个因子联合解释。
- 把 VIF 当成预测能力指标；它诊断共线性，不衡量收益。
- 同时检验很多因子却按每个原始 p 值 0.05 判定。
- 在全样本计算预处理、筛选或 VIF 后再切测试集，造成信息泄露。
- 将 `marginal_oos_mse_reduction` 误读为 reduced 模型优于 full 模型；正值恰好表示 full 更好。
- 因为复制因子不显著就断言 value 信号无效，忽略共线导致的系数竞争。
- 用一次切分做永久因子治理。

## 思考题

1. value 与 value_clone 同时存在时，为什么单个系数可能不显著但联合预测仍有效？
2. BH 控制 FDR 与 Bonferroni 控制家族错误率有什么不同？
3. 删除高 VIF 因子、正交化、岭回归和合成因子各有什么代价？
4. 若测试期发生因子漂移，边际贡献会如何改变？
5. 多个行业内分别筛因子时，检验“家族”应如何定义？

## 作业提示

- 找高冗余因子时同时报告相关系数、VIF、系数符号和边际贡献。
- 比较原始 p 值与 FDR 后结论，列出结论发生变化的因子。
- 删除或正交化方案必须只在训练样本拟合，再原样应用到测试样本。
- 可使用多个顺序切分重复计算 \(\Delta_j\)，报告均值、符号一致率和最差期。

## 验收标准

- [ ] 同时报告并正确解释相关矩阵与 VIF。
- [ ] 能手算 VIF 公式并说明完全共线时为何为无穷大。
- [ ] 完成 BH-FDR，并区分原始 p 值、校正 p 值与拒绝标记。
- [ ] 正确解释样本外边际 MSE 的符号。
- [ ] 能逐字段说明三个核心产物和三个框架产物。
- [ ] 因子保留结论同时考虑冗余、统计可信度、样本外增量和稳定性。
