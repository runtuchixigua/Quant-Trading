---
week: 9
title: "横截面机器学习"
phase: "机器学习"
reading_order:
  - "先复习第 7–8 周横截面因子、Rank IC 与简单等权基线"
  - "再阅读本文的 Ridge、walk-forward 与训练折内预处理"
  - "运行 python scripts/learn.py 9"
  - "先审计 folds，再看 predictions、comparison、PNG、report 与验收"
artifacts:
  predictions.csv:
    summary: "逐日期逐证券保存未来收益标签、Ridge 预测和等权因子基线预测。"
    columns:
      date: "特征形成和模型预测对应的交易日期。"
      symbol: "证券代码。"
      label: "用于训练或事后评价的固定期限未来收益。"
      ridge_prediction: "按 walk-forward 流程生成的 Ridge 模型预测值。"
      baseline_prediction: "三个标准化特征逐行等权平均得到的基线预测值。"
  folds.csv:
    summary: "逐折记录 Ridge walk-forward 的训练窗口、预测区间与样本规模。"
    columns:
      fold: "从 0 开始的 walk-forward 训练折编号。"
      train_start: "该折实际训练窗口的首个特征日期。"
      train_end: "该折实际训练窗口的最后一个特征日期。"
      prediction_start: "该折模型开始生成预测的日期。"
      prediction_end: "该折模型计划覆盖的最后预测日期。"
      n_train_dates: "该折训练窗口包含的不同交易日期数。"
      n_train_samples: "该折标签有效且实际用于拟合的日期证券样本数。"
      model: "该折使用的模型配置名称，本周为 ridge。"
  model_comparison.csv:
    summary: "在相同有效日期上比较 Ridge 与等权因子基线的 Rank IC 表现。"
    columns:
      model: "被评价的模型或基线名称。"
      mean_rank_ic: "该模型有效评价日期的平均日 Rank IC。"
      ic_positive_rate: "该模型有效日 Rank IC 大于零的比例。"
      valid_dates: "该模型能够计算日 Rank IC 的有效日期数。"
  summary.csv:
    summary: "以指标名和 week09 数值列汇总两种预测的平均 IC 与折数。"
    columns:
      "Unnamed: 0": "CSV 中未显式命名的首列，保存两模型平均 IC、折数和预测日期数等汇总指标名称。"
      week09: "第 9 周各汇总指标对应的数值。"
  ridge_walk_forward.png:
    summary: "展示 Ridge 与等权因子基线日 Rank IC 的累计和路径。"
  report.md:
    summary: "摘要 walk-forward 折数、两种模型平均 IC 及折内预处理约束。"
  homework.md:
    summary: "要求审计时间边界、比较基线并记录 Ridge 参数试验。"
  acceptance.json:
    summary: "保存第 9 周机器可读的课程验收标准与完成状态。"
  acceptance_checklist.md:
    summary: "提供第 9 周横截面机器学习实验的人工验收清单。"
  manifest.json:
    summary: "记录第 9 周运行元数据、产物清单及讲义字段释义。"
  run_manifest.json:
    summary: "与 manifest.json 同步保存本次第 9 周运行清单。"
---

# 第 9 周：横截面机器学习

本周把每个交易日的股票视为一个横截面，用动量、低波动和小市值三个标准化特征预测固定期限未来收益。模型采用 Ridge 回归，并与三个因子简单等权平均的基线在同一预测日期比较。核心不是“机器学习击败基线”，而是建立无随机打散、边界可审计、预处理只在训练折拟合的最小正确流程。

## 学习目标

1. 写出 Ridge 目标函数，解释正则化对相关特征和估计方差的影响。
2. 读懂 `(date, symbol)` 面板、标签期限、滚动训练窗和重训间隔。
3. 从 `folds.csv` 审计每折训练与预测边界。
4. 解释为什么填缺失和标准化必须在训练折内拟合。
5. 在相同日期上比较 Ridge 与简单等权因子基线，不隐去失败结果。

## 前置知识与数据结构

特征索引必须是严格排序且不重复的 MultiIndex：`date, symbol`。三列特征为 `momentum`、`low_volatility`、`small_size`，均按日横截面 z-score。标签 `label` 是未来 3 日（quick）或 5 日（完整）的收益，与同一 `(date, symbol)` 对齐。

横截面任务的预测单位是“某日某股票”，评价单位却是“某日全体股票的排序”。因此不能随机拆分所有行；那会把未来日期样本放进训练集，也会让同日截面同时出现在训练和测试中。

## 核心理论：Ridge 回归

给定训练样本 \(X\)、标签 \(y\)，Ridge 求解

\[
\hat\beta=\arg\min_\beta
\left\{\sum_j(y_j-x_j^\top\beta)^2+\alpha\|\beta\|_2^2\right\}.
\]

\(\alpha\) 越大，系数越向零收缩，通常降低方差、增加偏差。它不会自动选择少量特征，也不会消除数据泄漏。标准化很重要，因为惩罚作用于系数尺度；本实现 Pipeline 顺序为训练折中位数填充、训练折 `StandardScaler`、Ridge。默认 `ridge_alpha=10.0`。

当特征高度相关时，Ridge 往往分摊系数而不是任意保留一个，因此单个系数不宜被解释为因果贡献。模型预测值的绝对量纲也不是目标仓位；本周只按同日预测排序计算 Rank IC。

## 理论：Walk-forward

配置包含：

- quick：`min_train_dates=18`、`train_window_dates=35`、标签期限 3 日、每 8 日重训；
- 完整：`min_train_dates=60`、`train_window_dates=100`、标签期限 5 日、每 20 日重训。

第一批预测必须等到“最少训练日 + 标签期限”之后。对预测位置 \(i\)，代码令 `train_end = i - label_horizon_dates`，再使用 Python 半开切片 `dates[train_start:train_end]`，所以最后训练特征日严格早于该边界。直观上，只有未来收益已经完整实现的历史标签才能进入训练。

模型在重训日拟合，随后沿用到该折 `prediction_end`。这不是每天偷看新标签重新训练。滚动窗最多保留 `train_window_dates` 个日期，既控制状态陈旧，也意味着更早历史被丢弃。

## 标签隔离与折内预处理

假设时点 \(t\) 的标签需要到 \(t+h\) 才实现。预测日为 \(T\) 时，若把靠近 \(T\) 的特征日及其尚未完全实现的标签用于训练，就发生标签泄漏。安全条件不仅是 `train_end < prediction_start`，还要结合标签期限理解中间空档。

填缺失、均值、标准差和模型参数都必须只从该折训练样本估计。若先对全样本标准化，即使没使用标签，也让未来分布进入过去变换，造成信息泄漏。本实现把 imputer 和 scaler 放在 sklearn Pipeline 中，每折重新 `fit`，预测只调用该折已拟合变换。

## 评价与基线

Ridge 日 Rank IC 为同一日期 `ridge_prediction` 与 `label` 的 Spearman 相关。基线是三列特征的行均值 `baseline_prediction`，并仅在 Ridge 有预测的样本位置参与评价，保证日期可比。

\[
\Delta IC=\overline{IC}_{Ridge}-\overline{IC}_{baseline}
\]

只是排序表现增量，不是成本后收益增量。若 Ridge 不优于基线，这是有效结果：复杂模型可能没有获得额外信息，或样本不足以稳定估计权重。

## 阅读顺序

先复习横截面 Rank IC 和简单因子基线，再读 Ridge 与标签隔离；运行后必须先审计 `folds.csv`，确认边界合法，才依次阅读 predictions、comparison、summary、累计 IC 图和 report。表现数字不能先于无泄漏检查，作业与验收放在复算之后。

## 实验步骤

1. 运行 `python scripts/learn.py 9`。
2. 先核对 manifest，再打开 `folds.csv`；在看模型表现前确认所有时间边界合法。
3. 抽一折核对训练窗口长度、标签隔离和预测覆盖区间。
4. 检查 `predictions.csv`：早期 Ridge 预测为空、标签尾部为空都应有时间原因。
5. 分日期独立计算 Ridge 与 baseline Rank IC，确认比较日期一致。
6. 对账 `model_comparison.csv` 和 `summary.csv`。
7. 阅读累计 IC 图时只比较路径和阶段稳定性，不把纵轴当净值。
8. 修改 alpha 的试验必须另行记录原参数、seed、结果及无改善试验，不能覆盖基线记录。

## 逐文件与字段解释（产物与字段字典）

### `predictions.csv`

写出 MultiIndex 后包含：

- `date`：特征和预测日期。
- `symbol`：证券代码。
- `label`：该日该股票的未来固定期限收益，只用于训练标签或事后评价。
- `ridge_prediction`：Ridge 预测；训练历史不足时为空。
- `baseline_prediction`：三个标准化特征的行均值；即使早期存在，也只在 Ridge 非空位置进入公平比较。

### `folds.csv`

- `fold`：从 0 开始的折编号。
- `train_start`：该折训练窗口首日。
- `train_end`：实际进入训练窗口的最后日期。
- `prediction_start`：该折第一次预测日期。
- `prediction_end`：计划由该模型覆盖的最后预测日期。
- `n_train_dates`：训练日期数。
- `n_train_samples`：标签非空并实际用于拟合的 `(date, symbol)` 样本数。
- `model`：配置模型名，本周为 `ridge`。

最后一折的 `prediction_end` 受数据末尾截断。仅验证日期字符串大小不够，读入时应解析成日期。

### `model_comparison.csv`

- `model`：`ridge` 或 `equal_factor_baseline`。
- `mean_rank_ic`：有效评价日期的平均日 Rank IC。
- `ic_positive_rate`：有效日 IC 大于 0 的比例。
- `valid_dates`：有效 IC 日期数。

### `summary.csv`

指标索引配 `week09` 值列：

- `ridge_mean_rank_ic`；
- `baseline_mean_rank_ic`；
- `folds`：训练折数；
- `prediction_dates`：Ridge 有效日 Rank IC 日期数。

### 图表解读：`ridge_walk_forward.png`

图中两条线分别是 Ridge 和等权因子基线的日 Rank IC 累计和。上升更快只表示该段平均 IC 更高；回撤表示连续负 IC，不是资金亏损。比较终点前应先确认有效日期一致。

### `report.md` 与控制文件

报告摘要折数和两个模型平均 IC，并声明折内预处理。它不包含逐折稳定性、显著性、交易成本或组合收益。作业文件不会被重跑覆盖；acceptance 和两个 manifest 的结构与前周相同。

## 动态指标判断与结果边界

可以判断时间拆分是否可审计、Ridge 是否在同一合成样本上比简单基线有更高平均排序相关，以及预测表现是否阶段性不稳定。不能据此声称模型有因果解释、真实市场盈利、成本后增量或未来持续优势。

最低正确性边界：

- 所有折 `train_start <= train_end < prediction_start <= prediction_end`；
- 训练日期数不超过滚动窗；
- 早期无预测与配置一致；
- Ridge 与基线使用相同有效日期；
- report、comparison 和 summary 可由 predictions 复算。

表现边界应预先声明，不能看到结果后才定义。即使 Ridge 均值更高，也应检查是否由少数日期驱动；即使更低，也不应删除试验。

## 常见误区（常见误读）

1. 随机打散面板行做交叉验证。
2. 先在全样本填缺失、标准化，再拆分时间。
3. 只验证 `train_end < prediction_start`，却不理解标签何时实现。
4. 将更多训练样本视为必然更好；旧状态可能失效。
5. 用零预测作为基线，而不是可用的简单因子规则。
6. 把累计 Rank IC 当累计收益。
7. 调很多 alpha 后只报告最佳值，形成选择偏差。
8. 把 Ridge 系数解释成因果效应或稳定经济暴露。

## 思考题

1. 为什么标签期限越长，预测日前需要隔离的日期越多？
2. 若每日横截面股票数差异很大，简单平均日 IC 与按样本数加权会有何区别？
3. 扩展窗和滚动窗各自适用于什么市场稳定性假设？
4. 为什么基线预测可在早期存在，却仍应限制到 Ridge 的有效评价区间？
5. 如何证明改变未来标签不会改变更早预测？

## 作业提示

从 `folds.csv` 逐折列出训练结束、预测开始和两者间的业务含义；不要只写布尔检查。改变 alpha 时保持数据、seed、折边界和评价口径不变。至少保留一次无改善结果，并解释是偏差—方差、样本不足还是信号本身有限，而不是把失败归因于“模型不够复杂”。

## 验收标准

- [ ] 逐折验证训练、标签和预测边界无泄漏。
- [ ] 能解释 Pipeline 中填充和标准化为何只在训练折拟合。
- [ ] 从 predictions 复算 Ridge 与基线的每日及平均 Rank IC。
- [ ] 两个模型使用相同有效日期，且未隐去基线或失败试验。
- [ ] 明确预测分数、Rank IC 与可交易组合收益的区别。
- [ ] report、PNG、comparison 与 summary 均能追溯到原始预测。
