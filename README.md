# 🧩 Commodity Carry CTA · 商品期货横截面因子库

**简体中文** | [English](README.en.md)

> 跨品种构建 carry / 动量 / 基差 / 库存横截面因子，做多空品种轮动的系统化 CTA —— 填补期货「系统化因子」盲区。

![type](https://img.shields.io/badge/type-agent--skill-blue)
![license](https://img.shields.io/badge/license-GPLv3-blue)
![validation](https://img.shields.io/badge/validation-Runnable-orange)

---

## 📖 这是什么

社区的期货能力只有 `skill-futures-deepview-analyst` —— 它做的是**单品种**的席位博弈、
期限结构「研判叙事」。本 skill 做的是完全不同的活：**多品种横截面因子组合**。

因子家族：`carry`（年化基差/期限结构斜率）、`ts_momentum`（时序动量）、
`xs_momentum`（横截面动量）、`basis_momentum`（基差动量）、`inventory`（库存/仓单）。
合成后取头部做多、尾部做空，做品种轮动回测。

**核心难点是主连接续**：必须在合约内部算收益再链接（roll 日比例后复权），
直接拼价会注入虚假 alpha —— 这是商品 CTA 最常见的隐性泄漏。

## 🚀 快速开始

```bash
cp -r skill-commodity-carry-cta ~/.claude/skills/commodity-carry-cta
pip install -r requirements.txt
# 玩具数据自检（无需凭证）
python scripts/commodity_cta.py --top-frac 0.25
python scripts/test_commodity_cta.py
```

真实数据：

```bash
python scripts/commodity_cta.py \
  --varieties RB,HC,I,J,JM,CU,AL,ZN \
  --start-date 2021-01-01 --end-date 2024-12-31 \
  --top-frac 0.25 --roll-cost-bp 5 \
  --out commodity_factors.csv --report cta_report.md
```

```text
触发示例 prompt：
「跑一个商品 carry + 动量 CTA，给我多空净值曲线和分品种贡献」
「比较 backwardation 品种和 contango 品种的横截面收益」
```

## 📦 目录结构

```text
skill-commodity-carry-cta/
├── SKILL.md
├── requirements.txt
├── references/
│   ├── factor-spec.md           # 因子公式 / 主连接续 / 换月成本
│   └── source_boundary.md
├── scripts/
│   ├── commodity_cta.py         # 核心: build_continuous + compute_variety_factors + backtest
│   ├── test_commodity_cta.py
│   └── login_pandadata.py
└── agents/
    └── openai.yaml
```

## 📐 核心约束

| 约束 | 说明 |
| --- | --- |
| 🔗 主连接续 | 合约内算收益再链接（比例后复权），禁止直接拼价 |
| ⚖️ 风险缩放 | 品种乘数/流动性差异大，等权会过配不流动品种 |
| ⏱️ Point-in-time | 库存/仓单有披露滞后，按当时点对齐 |
| 🚫 只述不荐 | 回测是研究产物，不构成任何投资建议 |

## ✅ 真实数据测试结论（2026-07-27）

- **smoke test**：`python scripts/test_commodity_cta.py` 全部通过。
- **真实数据验证**：用 MCP `get_future_basis(symbol="CU")` 拉真实沪铜基差（2026-07-15~22，basis 910/80/715/730/-360/740，basis_ratio、spot_price 齐全），字段解析正常，carry 信号 +0.4467%（正 carry / backwardation），方向正确；多空回测框架端到端跑通（toy 面板：夏普 0.61、年化 14.6%、最大回撤 -11.0%）。
- **接口边界（2026-07-29 文档复核）**：`get_future_dominant` 与
  `get_future_basis` 使用 `underlying_symbol`；`get_future_daily`、
  `get_future_inventory` 与 `get_future_term_structure` 使用 `symbol`。
  主连映射返回的具体合约代码用于拉取日线，避免把品种码误当具体合约。
- 结论：数据链路真实可用，代码可靠。

## ⚠️ 免责声明

本仓库仅提供商品期货因子的研究方法与代码骨架，不下单、不验证任何收益声明、不构成任何投资建议。
默认 Community Project；请结合引用的数据与本地审核要求复核输出。

## 📜 License

GPL-3.0-only，详见 [LICENSE](LICENSE)。

## 🐼 PandaAI / QUANTSKILLS 社群

<div align="center">
  <img src="https://raw.githubusercontent.com/quantskills/.github/main/profile/assets/pandaai-community-qr.jpg" alt="PandaAI 社群二维码" width="220">
  <br>
  <sub>扫码加入 PandaAI 社群，交流 QUANTSKILLS 技能、Agent 工作流与量化研究实践。</sub>
</div>
