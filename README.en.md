# 🧩 Commodity Carry CTA

[简体中文](README.md) | **English**

> Cross-sectional commodity-futures factors (carry, momentum, basis, inventory) with a
> long-short variety-rotation backtest — filling the community's systematic-futures gap.

## 📖 What This Is

The community's only futures skill is `skill-futures-deepview-analyst`, which produces a
*single-variety positioning narrative*. This skill does a different job entirely:
**multi-variety cross-sectional factor portfolios**.

Factor family: `carry` (term-structure slope), `ts_momentum`, `xs_momentum`,
`basis_momentum`, `inventory`. The composite goes long the top and short the bottom for a
variety-rotation backtest.

**The main trap is continuous-contract stitching**: returns must be computed within each
contract and chained (ratio back-adjustment on roll days). A raw price concat injects
spurious jumps and fake alpha.

## 🚀 Quick Start

```bash
pip install -r requirements.txt
python scripts/commodity_cta.py --top-frac 0.25   # toy demo
python scripts/test_commodity_cta.py
```

The CLI produces both `commodity_factors.csv` and `cta_report.md`. Dominant mappings
are fetched with `underlying_symbol`; daily contract prices are fetched with the mapped
contract symbols. Roll-day returns therefore never divide a new contract by an old one.

## ⚠️ Disclaimer

Research only. Roll handling and point-in-time inventory alignment are mandatory. This skill
places no orders and is not investment advice. Community Project; validate outputs against
the cited data and local review requirements.

## 📜 License

GPL-3.0-only. See [LICENSE](LICENSE).

## 🐼 PandaAI / QUANTSKILLS Community

<div align="center">
  <img src="https://raw.githubusercontent.com/quantskills/.github/main/profile/assets/pandaai-community-qr.jpg" alt="PandaAI community QR code" width="220">
  <br>
  <sub>Scan the QR code to join the PandaAI community for QUANTSKILLS skills, agent workflows, and quantitative research practice.</sub>
</div>
