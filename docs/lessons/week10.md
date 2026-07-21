---
week: 10
title: "Walk-Forward 与标签隔离"
phase: "机器学习"
reading_order:
  - "先复习第 9 周 Ridge、折内预处理和时间边界"
  - "再阅读本文的 HistGBDT、统一 walk-forward、逐折重要性与试验纪律"
  - "运行 python scripts/learn.py 10"
  - "按 predictions、comparison、importance、experiment_log、PNG、report 顺序审计"
artifacts:
  predictions.csv:
    summary: "逐日期逐证券保存未来收益标签以及 Ridge 和 HistGBDT 的预测值。"
    columns:
      date: "特征形成和模型预测对应的交易日期。"
      symbol: "证券代码。"
      label: "用于训练或事后评价的固定期限未来收益。"
      ridge: "按统一 walk-forward 边界生成的 Ridge 预测值。"
      hist_gbdt: "按统一 walk-forward 边界生成的 HistGBDT 预测值。"
  model_comparison.csv:
    summary: "汇总 Ridge 与 HistGBDT 在相同评价流程下的 Rank IC 与折数。"
    columns:
      model: "被评价的模型名称。"
      mean_rank_ic: "该模型有效评价日期的平均日 Rank IC。"
      ic_std: "该模型有效日 Rank IC 的样本标准差。"
      valid_dates: "该模型能够计算日 Rank IC 的有效日期数。"
      folds: "该模型在 walk-forward 中完成的重训练折数。"
  fold_importance.csv:
    summary: "逐模型逐折保存特征系数或训练折置换重要性及时间边界。"
    columns:
      fold: "从 0 开始的模型训练折编号。"
      feature: "被解释的输入特征名称。"
      importance: "由 kind 指定口径的特征解释数值。"
      kind: "解释值类型，Ridge 为系数，HistGBDT 为置换重要性。"
      train_end: "该折实际训练窗口的最后一个特征日期。"
      prediction_start: "该折模型开始生成预测的日期。"
      model: "该行解释值所属的模型名称。"
  experiment_log.csv:
    summary: "保存本次两个模型的参数、随机种子、运行模式和评价结果。"
    columns:
      model: "试验使用的模型名称。"
      mean_rank_ic: "该试验有效评价日期的平均日 Rank IC。"
      ic_std: "该试验有效日 Rank IC 的样本标准差。"
      valid_dates: "该试验能够计算日 Rank IC 的有效日期数。"
      folds: "该试验完成的 walk-forward 重训练折数。"
      seed: "生成课程合成数据和模型随机过程所用的固定随机种子。"
      quick: "本次运行是否使用快速模式配置。"
      parameters: "按 JSON 字符串保存的模型名称与超参数。"
  summary.csv:
    summary: "以指标名和 week10 数值列汇总两模型平均 IC 与折数。"
    columns:
      "Unnamed: 0": "CSV 中未显式命名的首列，保存两模型平均 IC 和各自折数等汇总指标名称。"
      week10: "第 10 周各汇总指标对应的数值。"
  model_comparison.png:
    summary: "展示两模型累计 Rank IC 以及按模型汇总的平均逐折解释值。"
  report.md:
    summary: "摘要两模型平均 IC、统一时间边界和特征解释的非因果边界。"
  homework.md:
    summary: "要求比较逐折表现、审计重要性稳定性并记录失败试验。"
  acceptance.json:
    summary: "保存第 10 周机器可读的课程验收标准与完成状态。"
  acceptance_checklist.md:
    summary: "提供第 10 周模型比较实验的人工验收清单。"
  manifest.json:
    summary: "记录第 10 周运行元数据、产物清单及讲义字段释义。"
  run_manifest.json:
    summary: "与 manifest.json 同步保存本次第 10 周运行清单。"
---

# 第 10 周：Walk-Forward 与标签隔离

本周在完全相同的 walk-forward 边界下比较 Ridge 与直方图梯度提升树（HistGBDT）。课程重点不是宣布非线性模型获胜，而是确保两个模型使用相同特征、标签、预测日期和隔离规则，并把参数、seed、逐折解释和无改善试验完整留档。

## 学习目标

1. 区分 Ridge 的线性收缩与 GBDT 的非线性分段拟合。
2. 证明两个模型遵守同一 walk-forward 和标签隔离边界。
3. 正确解释 Ridge 系数与 HistGBDT 置换重要性的不同含义。
4. 评价跨折表现和特征重要性稳定性，而非只看全期均值。
5. 使用试验日志约束事后调参和结果挑选。

## 前置知识

数据仍是 `(date, symbol)` 面板，特征为按日标准化的 `momentum`、`low_volatility`、`small_size`，标签是未来 3 日或 5 日收益。第 9 周已说明：特征日不等于标签实现日，训练集必须排除预测日前仍未实现的标签；缺失值处理和缩放不能使用未来数据。

本周两个模型都调用同一个 `walk_forward_evaluate` 和同一组配置边界，因此模型差异不应与拆分差异混在一起。

## 核心理论：Ridge 与 HistGBDT

Ridge 假设条件均值近似线性：

\[
\hat y=\beta_0+\sum_j\beta_jx_j,
\qquad
\min_\beta\sum_i(y_i-\hat y_i)^2+\alpha\|\beta\|_2^2.
\]

HistGBDT 逐轮加入浅树，对残差方向进行梯度提升，可表达阈值、交互和非线性。教学配置为：

- quick：`max_iter=35`；
- 完整：`max_iter=80`；
- 两者 `max_leaf_nodes=15`、`learning_rate=0.08`、固定 `random_state`。

树模型不使用 `StandardScaler`，但使用训练折中位数填充。更强表达能力同时增加过拟合和状态不稳定风险。若真实关系近似线性或样本较少，Ridge 完全可能更稳。

## Walk-forward 与标签隔离

quick 模式使用至少 18 个训练日期、最长 35 日滚动窗、3 日标签期限、每 8 日重训；完整模式对应 60、100、5、20。对预测日期 \(T\)，只有在 \(T\) 前已经完整实现的标签进入训练。

应区分三种泄漏：

1. **标签泄漏**：使用尚未实现的未来收益。
2. **变换泄漏**：用全期数据拟合填充、标准化或特征筛选。
3. **选择泄漏**：反复观察最终区间后调整模型和参数。

前两种由代码结构控制，第三种必须靠 `experiment_log.csv` 和研究纪律控制。固定 seed 只保证可复现，不能消除选择偏差。

本周 runner 没有单独保存两个模型的 folds 文件；折数进入 comparison 和 summary，详细边界由共享 walk-forward 实现保证。审计时应结合第 9 周 folds 结构和源码配置，不要声称本周 CSV 中存在并未输出的训练日期列。

## 特征重要性

Ridge 最终估计器有 `coef_`，因此其 `kind` 为 `coefficient`，数值带符号。因输入已标准化，系数相对可比，但相关特征会分摊权重，仍非因果效应。

sklearn 的 HistGradientBoostingRegressor 没有本流程直接采用的原生 `feature_importances_`，因此代码在每个训练折上计算 permutation importance：

\[
I_j=\operatorname{MSE}(y,\hat f(X_{\pi(j)}))-
\operatorname{MSE}(y,\hat f(X)),
\]

实现使用 `neg_mean_squared_error` 评分，输出扰动后性能损失方向的平均重要性。quick 重复 1 次，完整重复 2 次。它是在训练折上计算，不是样本外重要性；相关特征会互相替代，重要性低不等于无经济信息，负值也可能来自噪声或有限重复。

不同 `kind` 的绝对数值不能直接横向比较。应在同一模型内看特征排序、符号（仅系数适用）和跨折稳定性。

## 阅读顺序

先以第 9 周的 walk-forward 边界作为共同基准，再比较线性与非线性模型；运行后依次读 predictions、comparison、逐折 importance、experiment log、summary、PNG 和 report。先核对样本与参数一致，再讨论胜负；最后补记失败试验并验收。

## 实验步骤

1. 运行 `python scripts/learn.py 10`。
2. 核对 manifest 的周次、标题、phase、runner、quick 与产物。
3. 在 `predictions.csv` 中确认两个模型对同一 `(date, symbol)` 给出预测，尾部标签空值符合期限。
4. 分日期计算两个模型的 Rank IC、均值、标准差和正值比例。
5. 用 `model_comparison.csv` 核对均值、标准差、有效日期与折数。
6. 按 `model, fold` 检查 `fold_importance.csv`；分别解释 coefficient 和 permutation importance。
7. 检查 `experiment_log.csv` 中 seed、quick 和 JSON 参数，确认结果行与 comparison 一致。
8. 阅读 PNG 左右图，回到逐折数据确认视觉结论。
9. 新增试验时另存记录；保持拆分、seed 和评价口径，至少记录一次失败或无改善结果。

## 逐文件与字段解释（产物与字段字典）

### `predictions.csv`

- `date`：预测特征日期。
- `symbol`：证券代码。
- `label`：未来固定期限收益。
- `ridge`：Ridge 预测。
- `hist_gbdt`：HistGBDT 预测。

早期预测为空是等待训练历史和隔离期的结果。不要用填零方式计算 IC。

### `model_comparison.csv`

- `model`：`ridge` 或 `hist_gbdt`。
- `mean_rank_ic`：每日 Rank IC 的有效日均值。
- `ic_std`：每日 Rank IC 的样本标准差。
- `valid_dates`：有效 IC 日期数。
- `folds`：该模型重训折数。

该表没有正值比例、统计显著性或成本后收益。

### `fold_importance.csv`

- `fold`：从 0 开始的模型折编号。
- `feature`：特征名。
- `importance`：解释值；含义由 `kind` 决定。
- `kind`：Ridge 为 `coefficient`，HistGBDT 通常为 `permutation_importance`。
- `train_end`：该折训练数据最后日期。
- `prediction_start`：该折第一次预测日期。
- `model`：runner 追加的 `ridge` 或 `hist_gbdt`。

可用 `train_end < prediction_start` 做基本检查，但完整标签隔离仍需结合 horizon。

### `experiment_log.csv`

它复制 comparison 的 `model`、`mean_rank_ic`、`ic_std`、`valid_dates`、`folds`，并新增：

- `seed`：固定为课程常量 `20260720`。
- `quick`：是否快速模式。
- `parameters`：JSON 字符串。Ridge 记录模型名与 `ridge_alpha`；HistGBDT 记录模型名、`max_iter`、`max_leaf_nodes`、`learning_rate`。

日志只有本次两个配置，不代表已自动记录你之后的试验；新增试验应保留旧行并补充唯一试验标识和时间。

### `summary.csv`

指标索引配 `week10` 值列：

- `ridge_mean_rank_ic`；
- `hist_gbdt_mean_rank_ic`；
- `ridge_folds`；
- `hist_gbdt_folds`。

### 图表解读：`model_comparison.png`

左图是两个模型每日 Rank IC 的累计和，不是净值。右图按模型展示各特征跨折 `importance` 均值；由于两模型的 `kind` 不同，柱高不能直接说成“某模型更依赖该特征”。均值还会掩盖折间正负抵消。

### `report.md` 与控制文件

报告仅汇报平均 IC，并强调同边界比较和非因果解释。作业、acceptance、checklist、manifest 的用途与前周一致；重跑不会覆盖已有 `homework.md`。

## 动态指标判断与结果边界

本周可以比较在固定合成数据和统一边界下两个模型的排序表现，并诊断解释值是否跨折稳定。不能证明非线性关系真实存在、重要特征具有因果作用、最佳模型未来占优，或任一模型可形成成本后策略。

选择模型不应只按最高平均 IC。至少同时考虑：

- 相对 Ridge 的增量是否持续而非集中于少数日期；
- `ic_std`、正值比例和阶段路径；
- 逐折重要性是否剧烈变化；
- 参数数量、训练稳定性和复现成本；
- 转成持仓后的换手与交易成本。

若 HistGBDT 均值略高但不稳定，应保留 Ridge 作为基线或生产降级方案，而不是自动升级复杂模型。

## 常见误区（常见误读）

1. 认为树模型不需标准化就可以在全样本预处理；填缺失仍须折内拟合。
2. 把 HistGBDT 训练折置换重要性说成样本外因果贡献。
3. 直接比较 Ridge 系数与置换重要性的绝对大小。
4. 只比较全期均值，不看逐日和逐折稳定性。
5. 多次调参后只保留最优试验。
6. 认为固定 seed 等于没有过拟合。
7. 把累计 IC 当收益曲线。
8. 声称本周输出了完整 folds 边界表；实际只有 importance 中的部分边界和折数。

## 思考题

1. 哪类真实关系会让 HistGBDT 相对 Ridge 有明确优势？
2. 为什么在训练折上计算的重要性可能过于乐观？
3. 两个高度相关特征中一个被置换时，另一个为何会掩盖其重要性？
4. 如何设计嵌套 walk-forward，使调参与最终评价区间分离？
5. 当复杂模型略优但重要性漂移明显时，模型治理应如何决策？

## 作业提示

逐折分析不要只对 importance 求均值；至少报告范围、符号变化（Ridge）或排序变化（GBDT）。新增失败试验时保存模型、参数、seed、quick、边界和所有指标。若改动模型参数，也要在相同预测日期重算两个模型，避免样本变化制造虚假增量。

## 验收标准

- [ ] Ridge 与 HistGBDT 使用相同特征、标签期限和 walk-forward 配置。
- [ ] 能解释标签、变换和选择三类泄漏。
- [ ] 正确区分 coefficient 与训练折 permutation importance。
- [ ] 按日期复算两个模型的 Rank IC，并检查有效日期一致。
- [ ] 保留参数、seed、quick、结果以及至少一次无改善试验。
- [ ] 未将重要性解释为因果，未将累计 IC 解释为组合净值。
