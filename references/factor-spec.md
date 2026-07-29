# Factor Spec — Commodity Carry CTA

因子公式、主连接续与换月成本规则。供 Agent 对齐 `scripts/commodity_cta.py`。

## 因子定义（跨品种横截面）

| 因子 | 公式 |
| --- | --- |
| `carry` | 优先使用年化基差；当前接口无年化字段时使用按日期对齐的 `basis_ratio` 代理（报告必须披露） |
| `ts_momentum` | 单品种自身 lookback 收益（时序动量） |
| `xs_momentum` | 把时序动量在品种间排名（横截面动量） |
| `basis_momentum` | 基差 / roll yield 在 lookback 内的变化 |
| `inventory` | 库存 + 仓单变化（库存收紧 = 看多，取负号） |

合成 = 选定因子逐日横截面 zscore 后等权平均 → 取头部做多、尾部做空，品种内按 inverse-vol 风险缩放。

## 主连接续（最大的坑）

- **绝不能**把不同合约的收盘价直接拼接 —— 换月跳空会注入虚假 alpha。
- 正确做法：在每个合约内部算收益再链接（roll 日按比例后复权 ratio back-adjust），并打 `roll_flag`。
- 若新合约在主连切换前已有行情，roll 日使用该新合约自身前收计算收益；若稀疏数据缺少前收，
  roll 日收益置零并保留 `roll_flag`，不得用新合约价除以旧合约价。
- 收益序列必须连续无跳空；价格序列可保留后复权值供展示。

## 换月成本

- 每次换月扣 `roll_cost_bp`（名义本金 bp）作为成本桩；真实应按近远月价差 + 手续费估。
- 库存/仓单为交易所发布、有滞后，按 point-in-time 对齐，避免用未来披露值。

## 品种差异

- 合约乘数、最小变动、交易时段、流动性差异大；等权处理会过配不流动品种 → 用风险缩放。
- 建议只选流动性充足的主力品种进入 universe。

## Pandadata 接口

- `get_future_dominant(underlying_symbol=...)`
- `get_future_daily(symbol=<主连映射返回的具体合约代码>)`
- `get_future_basis(underlying_symbol=...)`
- `get_future_term_structure(symbol=<具体合约代码>)`
- `get_future_inventory(symbol=<品种码>)`、`get_future_warehouse_receipt`

> 与 `skill-futures-deepview-analyst` 的区别：那个做**单品种席位/期限结构研判叙事**，
> 本 skill 做**多品种系统化因子 + 多空组合**。回测结论不构成投资建议。
