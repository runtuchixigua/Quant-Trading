# 实验清单（Manifest）规范

## 1. 目的

实验 manifest 是一次运行的不可变身份证，用于回答：谁在何时，使用哪版数据、代码、配置和环境，运行了什么方法，产生了哪些结果。正式结论不得引用没有 manifest 的运行。

推荐每次运行保存一个 UTF-8 YAML 文件。字段名使用英文以便机器读取，说明和研究内容可使用中文。manifest 创建后只允许补充运行状态、结束时间和产物校验值；若配置改变，必须生成新的 `experiment_id`。

## 2. 身份与命名

- `experiment_id`：全局唯一，建议 `YYYYMMDD-HHMMSS_<research-slug>_<short-hash>`。
- `parent_experiment_id`：派生实验的直接父实验；首个实验为空。
- `research_log_id`：对应研究日志。
- `stage`：`exploratory / validation / final_test / reproduction`。
- `status`：`planned / running / succeeded / failed / aborted / invalidated`。
- `created_at / started_at / finished_at`：带时区 ISO 8601。
- `owner / reviewer`：负责人和复核人。

同一 `experiment_id` 不得被重复执行后覆盖。重试也应生成新 ID，并通过 `parent_experiment_id` 连接。

## 3. 必填结构

```yaml
schema_version: "1.0.0"
experiment:
  experiment_id: "20260717-153000_factor-test_a1b2c3d4"
  parent_experiment_id: null
  research_log_id: "RL-2026-001"
  title: "质量因子样本外验证"
  stage: "validation"
  status: "planned"
  owner: "name"
  reviewer: "name"
  created_at: "2026-07-17T15:30:00+08:00"
  started_at: null
  finished_at: null

hypothesis:
  primary_question: "质量因子能否在成本后提供稳定的横截面增量？"
  expected_direction: "positive"
  mechanism: "盈利质量信息反映缓慢"
  falsification:
    - "样本外 Rank IC 的 95% 置信区间包含预设无效区间"
    - "成本后表现不优于简单基线"
  primary_metrics:
    - name: "rank_ic"
      pass_threshold: 0.02
    - name: "net_information_ratio"
      pass_threshold: 0.30

code:
  repository: "local-repository-name"
  commit: "<full-commit-hash>"
  dirty: false
  diff_hash: null
  entrypoint: "<reproduction-command>"

environment:
  os: "darwin"
  architecture: "arm64"
  language: "python"
  language_version: "<exact-version>"
  dependency_lock_hash: "<sha256>"
  timezone: "Asia/Shanghai"
  random_seeds: [20260717]
  deterministic: true
  non_determinism_notes: null

data:
  datasets:
    - dataset_id: "daily_equity"
      snapshot_time: "<ISO-8601>"
      schema_version: "1.0.0"
      source_version: "<vendor-version>"
      content_hash: "<sha256>"
      location: "<immutable-uri-or-path>"
      known_time_policy: "known_from <= as_of_time"
  universe:
    universe_id: "ashare_research"
    version: "1.0.0"
    as_of_policy: "historical"
  calendar_version: "<version>"
  start_date: "2015-01-01"
  end_date: "2025-12-31"

split:
  method: "nested_walk_forward"
  train_window: 756
  validation_window: 126
  test_window: 126
  purge_days: 20
  embargo_days: 20
  final_test_frozen: true

features:
  feature_set_id: "quality_v1"
  versions:
    roe_ttm: "1.0.0"
    accruals: "1.0.0"
  preprocessing:
    winsorize: "cross_section_mad_5"
    neutralize: ["industry", "log_market_cap"]
    standardize: "cross_section_zscore"
    fit_scope: "training_only"

model:
  model_id: "ridge_ranker"
  version: "1.0.0"
  hyperparameters:
    alpha: 1.0
  selection_rule: "inner_validation_rank_ic"

portfolio:
  rebalance: "monthly"
  weighting: "score_proportional"
  benchmark: "universe_equal_weight"
  constraints:
    max_single_weight: 0.02
    max_industry_active_weight: 0.05
    max_turnover: 0.40

execution:
  signal_time: "close"
  execution_delay_days: 1
  price: "next_open"
  commission_bps: 3.0
  minimum_commission: 5.0
  sell_tax_bps: 5.0
  slippage_model: "spread_participation_v1"
  max_participation: 0.10
  lot_size: 100
  t_plus_one: true

outputs:
  root: "<immutable-output-path>"
  required:
    - "metrics.json"
    - "predictions.parquet"
    - "positions.parquet"
    - "orders.parquet"
    - "data_quality.json"
  artifacts: []

result:
  primary_metrics: {}
  quality_gate_passed: null
  decision: null
  notes: null
```

## 4. 字段约束

### 代码

- `commit` 必须是完整提交哈希。
- 若 `dirty: true`，必须保存完整 diff 并填 `diff_hash`；最终测试和独立复现禁止脏工作区。
- `entrypoint` 必须是非交互、从项目根目录可执行的单条命令或明确工作流。

### 环境

- 依赖必须由锁文件或完整环境导出固定，并保存哈希。
- 所有随机源必须登记种子；GPU、并行归约等非确定性需声明。
- 环境变量只记录名称和是否存在，不得把密码、令牌写入 manifest。

### 数据

- 每个输入都必须有不可变位置和内容哈希；`latest`、在线动态链接或个人临时文件不合格。
- 数据字典模式版本、供应商版本和快照时间缺一不可。
- 衍生数据必须记录上游数据版本和转换版本。

### 验证

- 标签期限为 `h` 时，`purge_days` 不得小于产生重叠的实际期限。
- 最终测试的 `stage` 必须为 `final_test`，且 `final_test_frozen: true`。
- 主要指标和阈值必须在运行前填写；运行后修改会使实验变为探索性。

### 成交

- 佣金、最低佣金、税、滑点、参与率、整数手、T+1 与不可交易规则均需显式填写。
- 不能用 `zero` 或空值隐含“忽略成本”；无成本对照应明确写 0 并标为诊断实验。

### 产物

运行完成后将所有产物加入：

```yaml
outputs:
  artifacts:
    - path: "metrics.json"
      media_type: "application/json"
      sha256: "<hash>"
      size_bytes: 1234
      rows: null
    - path: "predictions.parquet"
      media_type: "application/vnd.apache.parquet"
      sha256: "<hash>"
      size_bytes: 123456
      rows: 100000
```

核心表图必须能从结构化产物重新生成；图片本身不是充分的研究证据。

## 5. 状态迁移

允许的状态迁移：

1. `planned → running`
2. `running → succeeded / failed / aborted`
3. `succeeded → invalidated`（发现数据泄漏、实现错误或治理问题）

禁止将 `failed` 原地改为 `succeeded`。修复后必须建立子实验。`invalidated` 的原因、发现时间、影响结论和替代实验 ID 必须追加记录，旧产物不得删除。

## 6. 质量门禁

正式验证和最终测试至少检查：

- manifest 模式校验通过，必填字段完整率 100%。
- 输入与输出哈希校验通过率 100%。
- 主键、时点、股票池和标签泄漏检查通过。
- 代码、环境和数据版本可获得。
- 指标可从结构化产物重算，差异在预设容差内。
- 研究日志中的预注册参数与 manifest 一致。
- 最终测试没有脏代码、动态数据或运行后修改阈值。

任一门禁失败时，`quality_gate_passed: false`，该实验不得支持正式结论。

## 7. 实验索引

项目应维护可追加的实验索引，至少包含：

| experiment_id | research_log_id | stage | parent_id | status | created_at | primary_metric | gate | decision |
|---|---|---|---|---|---|---|---|---|

索引必须包含失败、中止和作废实验。不得只导出成功实验，也不得删除“看起来重复”的尝试，否则无法估计真实搜索规模。

## 8. 独立复现

复现者应只获得仓库、锁定环境、manifest 和不可变数据入口，不依赖作者口头说明。复现后生成新 `experiment_id`，`stage: reproduction`，并将原实验设为父实验。

最低复现标准：

- 输入哈希一致。
- 运行命令无需手工改路径或参数。
- 必需产物全部生成。
- 确定性实验核心指标绝对误差小于 `1e-8` 或相对误差小于 `0.1%`。
- 非确定性实验在 manifest 预先声明的分布或容差内。
- 复现者记录耗时、环境差异、失败步骤和最终结论。
