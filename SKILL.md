---
name: commodity-carry-cta
description: "Build a systematic cross-sectional commodity-futures factor portfolio from Pandadata futures data: carry (basis / term-structure slope), time-series and cross-sectional momentum, basis momentum, and inventory / warehouse-receipt signals across varieties, with continuous dominant-contract stitching and a long-short variety backtest. Use when an agent needs systematic multi-variety commodity CTA factors rather than single-variety positioning narrative."
quantSkills:
  organization: QuantSkills
  organization_url: https://github.com/quantskills
  repository: skill-commodity-carry-cta
  repository_url: https://github.com/quantskills/skill-commodity-carry-cta
  project_type: skill
  collection: futures-factors
  license: GPL-3.0-only
  category: factor
  tags: [commodity, futures, cta, carry, term-structure, momentum, basis, inventory, cross-section]
  platforms: [claude-code, codex, openclaw]
  language: zh-en
  status: draft
  validation_level: runnable
  maintainer_type: community
  requires: []                 # 下游: skill-backtest / skill-factor-evaluate
  summary_zh: 跨品种构建商品期货 carry/动量/基差/库存横截面因子，做主连接续与多空品种轮动回测的系统化 CTA。
  summary_en: Systematic cross-sectional commodity-futures factors (carry, momentum, basis, inventory) with dominant-contract stitching and a long-short variety backtest.
---

# Commodity Carry CTA

Use this skill to build **systematic, multi-variety** commodity-futures factors and a
long-short variety-rotation backtest. It fills the community's futures gap: the existing
`skill-futures-deepview-analyst` produces a single-variety *positioning narrative* (席位
博弈 / 期限结构研判); this skill produces a *cross-sectional factor portfolio* across many
varieties — a different job entirely.

## Factor family

| Factor | Definition (cross-sectional across varieties) |
| --- | --- |
| `carry` | annualized basis / near-far term-structure slope (contango vs backwardation) |
| `ts_momentum` | own trailing return sign/strength per variety (time-series) |
| `xs_momentum` | trailing return ranked across varieties (cross-sectional) |
| `basis_momentum` | change in basis / roll yield over the lookback |
| `inventory` | inventory & warehouse-receipt change (tighter stock = bullish) |

Composite (default: equal-weight z-score of selected factors) ranks varieties into
long (top) and short (bottom) legs.

## Core Workflow

1. **Universe & stitching**: pick liquid varieties; build a continuous dominant-contract
   series via `get_future_dominant`, handling roll with explicit roll dates (no price jumps
   leaking into returns).
2. **Pull data**: daily prices, basis, term structure, inventory, warehouse receipts.
3. **Compute factors**: carry / momentum / basis-momentum / inventory per variety per day.
4. **Rank & form legs**: cross-sectional z-score → composite → long top / short bottom,
   risk-scaled (e.g. inverse-vol) variety weights.
5. **Backtest**: long-short variety portfolio with roll cost; report NAV, Sharpe, drawdown,
   and per-factor / per-variety attribution.

## Output Contract

Produce:

- `commodity_factors.csv` — `date, variety, carry, ts_momentum, xs_momentum, basis_momentum, inventory, composite`
- `cta_report.md` — long-short NAV, Sharpe/MDD, per-factor IC, per-variety contribution, roll-cost notes
- a fact/caveat summary

## Data Sources

- `panda_data.get_future_dominant`, `get_future_daily`
- `panda_data.get_future_basis`, `get_future_term_structure`
- `panda_data.get_future_inventory`, `get_future_warehouse_receipt`

## Limitations & Risk Boundary

- **Roll handling is the main trap**: returns must be computed on a properly stitched
  continuous series; a raw price concat injects spurious jumps and fake alpha.
- Commodity varieties differ in contract size, tick, trading hours, and liquidity; equal
  treatment across varieties can over-weight illiquid contracts. Use risk scaling.
- Inventory / warehouse-receipt data is exchange-reported with lags; align point-in-time.
- Backtest assumes fills at the stitched price with a roll-cost stub; no market impact / capacity.
- Research only — no orders, **not investment advice**.
- Community Project; validate outputs against the cited data and local review requirements.

## ✅ Quality Bar

Before delivering artifacts (degrade & disclose rather than pass silently):

- **Traceable**: every key figure maps to a specific Pandadata interface + data date; missing data goes to `degraded[]` — never fabricate or pass approximations off as real values.
- **Transparent degradation**: when any source is empty/limited, the report states it and lowers confidence.
- **Consistent conventions**: units, frequency, and benchmark conventions are stated explicitly.
- **Research only**: artifacts are for research/education, not investment advice, with no return promises.
- Long-short factor returns must be net of the stated fee/slippage assumption; dominant-contract roll dates disclosed.

## References

- `references/factor-spec.md` — factor formulas, dominant-contract stitching, roll-cost rules.
- `references/source_boundary.md` — allowed data sources.
