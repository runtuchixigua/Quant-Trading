---
week: 13
title: "Point-in-Time 数据工程与可追溯性"
phase: "数据与事件"
reading_order:
  - "先读 fundamentals_raw.csv：区分报告期、公告日与入库时间"
  - "再读 announcement_audit.csv：核对 as_of 日的信息可得性"
  - "然后读 pit_snapshot.csv：验证逐证券选取最新已公告记录"
  - "最后读 lineage.json：复核转换规则、行数与 SHA-256"
artifacts:
  fundamentals_raw.csv:
    summary: "按证券与报告期保存的合成基本面原始长表。"
    columns:
      symbol: "证券代码。"
      report_period: "财务报告归属期。"
      announcement_date: "公告公开日期。"
      ingested_at: "数据进入研究系统的日期。"
      revenue: "合成营业收入。"
      net_income: "合成净利润。"
      source: "数据来源标识。"
  pit_snapshot.csv:
    summary: "截至 as_of 日每只证券最新的已公告基本面快照。"
    columns:
      symbol: "证券代码。"
      report_period: "快照选中的最新财务报告归属期。"
      announcement_date: "该记录的公告公开日期。"
      ingested_at: "该记录进入研究系统的日期。"
      revenue: "合成营业收入。"
      net_income: "合成净利润。"
      source: "数据来源标识。"
  announcement_audit.csv:
    summary: "逐条记录公告可得性与相对 as_of 日期的审计明细。"
    columns:
      symbol: "证券代码。"
      report_period: "财务报告归属期。"
      announcement_date: "公告公开日期。"
      ingested_at: "数据进入研究系统的日期。"
      revenue: "合成营业收入。"
      net_income: "合成净利润。"
      source: "数据来源标识。"
      as_of: "统一审计时点。"
      available_on_as_of: "公告日是否不晚于审计时点。"
      days_from_announcement: "审计时点与公告日相差的日历天数。"
      violation: "实现定义的公告日违规标记。"
  lineage.json:
    summary: "保存快照规则、来源与快照哈希及行数的数据血缘记录。"
  homework.md:
    summary: "本周 PIT 快照与血缘审计作业。"
  acceptance.json:
    summary: "本周程序化验收条件。"
  manifest.json:
    summary: "本周运行模式与产物清单。"
---

# 第 13 周：Point-in-Time 数据工程与可追溯性

## 学习目标

本周把“当时能知道什么”落实成可审计的数据规则。完成后，你应能区分报告期、公告日和入库时间；按任意 `as_of` 日构造 PIT（Point-in-Time）快照；用 SHA-256 验证原始数据与快照是否被改变；并能从最终结果反查来源、筛选规则和行数。

PIT 的核心不是“使用历史数据”，而是“只使用决策时点已经公开且已进入系统的数据”。财务报表属于 3 月 31 日，并不表示 3 月 31 日可用；回测中真正决定可用性的通常是公告日，还可能需要叠加入库延迟。忽略这一区别，会把未来信息悄悄带入因子和组合。

## 前置知识

- 会使用 `pandas` 读取、排序、筛选和分组。
- 理解横截面因子在调仓日只能访问当时可得的信息。
- 了解哈希是内容指纹，不是加密，也不能单独证明来源真实。
- 建议先掌握无未来函数回测、财务报告期和交易日的区别。

## 核心理论

对证券 \(i\) 的第 \(k\) 条记录，记报告期为 \(p_{ik}\)，公告日为 \(a_{ik}\)，入库时间为 \(g_{ik}\)，研究时点为 \(t\)。本实验采用的可得性规则是：

\[
\mathcal A_i(t)=\{k:a_{ik}\le t\}
\]

并在可得集合中取最新报告期：

\[
k_i^*(t)=\arg\max_{k\in\mathcal A_i(t)}p_{ik}.
\]

代码中的规则明确写为 `announcement_date <= as_of; latest report_period per symbol`。生产环境若要求数据必须已经进入研究系统，应使用更严格的

\[
a_{ik}\le t\quad\text{且}\quad g_{ik}\le t.
\]

内容哈希为

\[
h=\operatorname{SHA256}(\text{file bytes}).
\]

同一文件逐字节相同，哈希应相同；数据、列顺序、浮点序列化或换行变化都可能改变哈希。哈希能够发现内容变化，但只有配合可信来源、权限控制和时间戳，才能形成完整证据链。

## 实验步骤：构造可审计 PIT 快照

运行第 13 周实验。完整模式为 12 只合成证券、8 个季度；`quick` 模式为 6 只证券、5 个季度。随机种子固定为 13，因此相同环境和序列化规则下可以复现。

1. 生成原始基本面长表。证券代码为 `600000.SH` 起的合成代码；每条记录包含报告期、公告日、入库时间、收入、净利润和来源。
2. 公告日在报告期后 25 至 59 天，入库时间固定为公告日后 1 天。这使“经济归属期”和“信息可见时间”明确分离。
3. 固定 `as_of = 2024-09-30`，仅保留 `announcement_date <= as_of` 的记录。
4. 按 `symbol`、`report_period`、`ingested_at` 排序，每只证券保留最后一条，得到 PIT 快照。
5. 对全部原始记录生成公告日审计表，记录是否在 `as_of` 可用以及距离公告日的天数。
6. 对原始表和快照计算 SHA-256，连同规则、行数和来源写入血缘文件。

特别注意：实验的快照准入只检查公告日，`ingested_at` 用于排序和审计语义，并未作为准入条件。讲义中可以提出更严格规则，但验收时必须准确描述当前实现。

## 逐文件与字段解释

### `fundamentals_raw.csv`

原始基本面记录，是血缘链的起点。

- `symbol`：证券代码。
- `report_period`：财务报告归属期。
- `announcement_date`：公告公开日，也是本实验的 PIT 可用性门槛。
- `ingested_at`：数据进入系统的时间，本实验设为公告日后一天。
- `revenue`：合成营业收入。
- `net_income`：合成净利润。
- `source`：来源标识，固定为 `synthetic_exchange_filing`。

### `pit_snapshot.csv`

截至 `2024-09-30` 每只证券最新的已公告记录。字段与 `fundamentals_raw.csv` 相同。验收重点是任何一行都满足 `announcement_date <= as_of`，且在该证券的合格记录中 `report_period` 最新。

### `announcement_audit.csv`

在原始字段后增加：

- `as_of`：统一审计时点。
- `available_on_as_of`：公告日是否不晚于 `as_of`。
- `days_from_announcement`：`as_of - announcement_date` 的日历天数；负值表示当时尚未公告。
- `violation`：实现中的审计标记。当前表达式为“已可用且公告日又晚于 `as_of`”，逻辑上应恒为假；真正的快照违规数还应直接检查快照的公告日。

### `lineage.json`

- `schema_version`：血缘结构版本，当前为 1。
- `as_of`：ISO 格式的快照时点。
- `source`：来源文件名 `fundamentals_raw.csv`。
- `transform`：筛选和取最新记录的规则文本。
- `source_sha256`：原始文件 SHA-256。
- `snapshot_sha256`：快照文件 SHA-256。
- `row_count`：快照行数。

### 框架产物

- `homework.md`：安全写入的作业记录，不覆盖已有作业。
- `acceptance.json`：第 13 周验收条件。
- `manifest.json`：周数、运行模式及全部产物清单。

## 阅读顺序

1. 先看 `fundamentals_raw.csv`，任选证券画出报告期、公告日、入库日时间线。
2. 再看 `announcement_audit.csv`，理解 `available_on_as_of` 和负的 `days_from_announcement`。
3. 对照 `pit_snapshot.csv`，手工验证至少两只证券的“先准入、后取最新”过程。
4. 最后读 `lineage.json`，复算两个哈希并核对行数与转换规则。
5. 用 `manifest.json` 检查产物是否齐全，再填写 `homework.md` 和核对 `acceptance.json`。

## 图表解读

本周 runner 不生成图表，因为 PIT 验收的核心是逐行可得性、版本选择和哈希一致性，表格与血缘文件比汇总图片更适合审计。建议自行绘制两类图：其一，对任选证券画 `report_period`、`announcement_date`、`ingested_at` 三条时间标记，并用竖线标出 `as_of`；标记落在竖线右侧的记录不应进入快照。其二，按报告期画 `announcement_date - report_period` 的延迟分布，观察公告延迟是否存在异常长尾。图形只用于辅助发现问题，最终仍应回到原始行和哈希验证。

## 动态指标判断

- `future_announcement_violations` 必须为 0。
- 快照每只证券最多一行，且每行公告日不晚于 `as_of`。
- 在不改文件的情况下重算 SHA-256，应与 `lineage.json` 完全一致。
- 改变 `as_of` 后，合格记录集合或最新记录发生变化时，快照哈希通常会变化；若内容未变，哈希也可以不变。
- `row_count` 必须等于 `pit_snapshot.csv` 的数据行数。
- 能从快照行追溯到原始文件，并说清筛选、排序、分组和取尾记录的每一步。

## 常见误区

- 用 `report_period <= as_of` 代替公告日判断，造成未来函数。
- 认为公告当天一定可以交易；真实系统还需考虑公告时刻、盘前盘后、交易日映射和入库延迟。
- 只保存最终快照，不保存原始版本、修订记录和转换规则。
- 把哈希当成真实性证明。哈希只证明“内容是否相同”，不能证明内容来自交易所。
- 误以为 `violation` 列已覆盖所有审计。当前表达式天然互斥，仍须对快照直接做未来公告检查。
- 用自然日直接映射交易决策日，却没有规定周末、节假日和停牌处理。

## 思考题

1. 一份年报先发布、后更正，应如何同时保存“当时版本”和“最终版本”？
2. 公告在收盘后发布，最早可用于哪一个交易日？若只有日期没有时刻怎么办？
3. 为什么相同表格内容在不同 CSV 浮点格式下可能产生不同哈希？
4. 除来源与转换规则外，生产血缘还应记录哪些代码版本、参数、依赖和权限信息？
5. 如果 `ingested_at > as_of`，即使公告日合格，研究系统当时是否真的能使用？

## 作业提示

- 独立重建快照时，不要直接复制实验的 `tail(1)`；先写出可用集合，再证明排序键足以唯一决定版本。
- 修改 `as_of` 后，同时报告新增/删除证券、报告期变化和哈希变化，不要只说“哈希不同”。
- 公告延迟可定义为 `announcement_date - report_period`，应报告分布而非只报告均值。
- 扩展血缘字段时，可考虑代码提交号、运行参数、依赖版本、生成时间、操作者、上游数据版本和签名。

## 验收标准

- [ ] 快照不存在未来公告记录。
- [ ] 能复算并匹配来源文件与快照的 SHA-256。
- [ ] 能准确解释报告期、公告日、入库时间和 `as_of` 的区别。
- [ ] 能逐字段说明四个核心产物和三个框架产物。
- [ ] 能从快照追溯到原始数据、转换规则、行数和哈希。
- [ ] 能指出当前实验只以公告日准入，以及生产环境需要的更严格控制。
