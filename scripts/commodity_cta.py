"""Systematic cross-sectional commodity-futures factors + long-short variety backtest.

Skeleton implementation for skill-commodity-carry-cta.

Factors: carry (term-structure slope), time-series & cross-sectional momentum, basis
momentum, inventory/warehouse-receipt signal. Built on a properly stitched continuous
dominant-contract series — raw price concat would inject spurious roll jumps.

Research scaffold, not investment advice. It places no orders.
"""

from __future__ import annotations

import argparse
import importlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class CTAConfig:
    momentum_lookback: int = 60       # trading days
    basis_lookback: int = 20
    factors: list[str] = field(default_factory=lambda: [
        "carry", "ts_momentum", "xs_momentum", "basis_momentum", "inventory"])
    top_frac: float = 0.25            # long top / short bottom fraction of varieties
    roll_cost_bp: float = 5.0         # per-roll cost stub (bp of notional)

    def __post_init__(self):
        if not 0 < self.top_frac <= 0.5:
            raise ValueError("top_frac must be in (0, 0.5] so long/short buckets do not overlap")


def _load_panda_data():
    return importlib.import_module("panda_data")


# --------------------------------------------------------------------------- #
# Continuous dominant-contract stitching (the main trap)
# --------------------------------------------------------------------------- #
def build_continuous(variety: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Return a continuous series for one variety: date, close, ret, roll_flag.

    Returns are computed WITHIN each contract and chained, so roll-day price gaps never
    leak into the return series (back-adjustment by ratio on roll days).
    """
    pd_api = _load_panda_data()
    dom = pd.DataFrame(pd_api.get_future_dominant(
        underlying_symbol=variety, start_date=start_date, end_date=end_date))
    contracts = dom.get("symbol", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()
    if not contracts:
        return pd.DataFrame(
            columns=["date", "contract", "raw_close", "close", "ret", "roll_flag"])
    daily = pd.DataFrame(pd_api.get_future_daily(
        symbol=contracts, start_date=start_date, end_date=end_date))
    return _stitch(dom, daily)


def _stitch(dom: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Stitch date-to-dominant mappings using each contract's own daily return.

    On a roll date the selected new contract's return is computed against that same
    contract's previous observation. It is never computed as new-contract close divided
    by old-contract close. The returned ``close`` is a chained continuous index;
    ``raw_close`` retains the selected traded-contract price for audit.
    """
    columns = ["date", "contract", "raw_close", "close", "ret", "roll_flag"]
    if dom.empty or daily.empty or "date" not in dom or "date" not in daily or "close" not in daily:
        return pd.DataFrame(columns=columns)

    dominant = dom.copy()
    contract_col = "symbol" if "symbol" in dominant else "contract"
    daily_contract_col = "symbol" if "symbol" in daily else "contract"
    if contract_col not in dominant or daily_contract_col not in daily:
        return pd.DataFrame(columns=columns)

    dominant["date"] = pd.to_datetime(dominant["date"])
    dominant["contract"] = dominant[contract_col].astype(str)
    dominant = dominant[["date", "contract"]].drop_duplicates("date", keep="last")

    prices = daily.copy()
    prices["date"] = pd.to_datetime(prices["date"])
    prices["contract"] = prices[daily_contract_col].astype(str)
    prices["raw_close"] = pd.to_numeric(prices["close"], errors="coerce")
    prices = prices.sort_values(["contract", "date"]).drop_duplicates(
        ["date", "contract"], keep="last")
    prices["contract_ret"] = prices.groupby("contract", sort=False)["raw_close"].pct_change()

    selected = dominant.merge(
        prices[["date", "contract", "raw_close", "contract_ret"]],
        on=["date", "contract"],
        how="left",
        validate="one_to_one",
    ).sort_values("date").reset_index(drop=True)
    selected["roll_flag"] = selected["contract"].ne(selected["contract"].shift()).fillna(False)
    if not selected.empty:
        selected.loc[0, "roll_flag"] = False
    selected["ret"] = selected["contract_ret"]
    # A newly dominant contract can lack a pre-roll observation in sparse data. A zero
    # roll-day return is transparent and avoids inventing a cross-contract price return.
    selected.loc[selected["roll_flag"] & selected["ret"].isna(), "ret"] = 0.0
    selected["close"] = (
        selected["raw_close"].dropna().iloc[0]
        if selected["raw_close"].notna().any() else 1.0
    ) * (1.0 + selected["ret"].fillna(0.0)).cumprod()
    return selected[columns]


# --------------------------------------------------------------------------- #
# Per-variety factor computation
# --------------------------------------------------------------------------- #
def compute_variety_factors(variety: str, cont: pd.DataFrame, basis: pd.DataFrame,
                            term: pd.DataFrame, inv: pd.DataFrame, cfg: CTAConfig) -> pd.DataFrame:
    """Return date-indexed factor frame for one variety."""
    del term  # Current Pandadata endpoint is per-contract; basis_ratio is the aligned carry proxy.
    out = cont[["date", "close", "ret", "roll_flag"]].copy()
    out["date"] = pd.to_datetime(out["date"])
    out["variety"] = variety
    out["ts_momentum"] = out["ret"].rolling(cfg.momentum_lookback).sum()

    if isinstance(basis, pd.DataFrame) and not basis.empty and "date" in basis:
        basis_aligned = basis.copy()
        basis_aligned["date"] = pd.to_datetime(basis_aligned["date"])
        basis_col = "annualized_basis" if "annualized_basis" in basis_aligned else "basis_ratio"
        if basis_col in basis_aligned:
            basis_aligned["carry"] = pd.to_numeric(basis_aligned[basis_col], errors="coerce")
            basis_aligned["basis_momentum"] = basis_aligned["carry"].diff(cfg.basis_lookback)
            out = out.merge(
                basis_aligned[["date", "carry", "basis_momentum"]].drop_duplicates("date"),
                on="date", how="left", validate="one_to_one")
    if "carry" not in out:
        out["carry"] = np.nan
        out["basis_momentum"] = np.nan

    if isinstance(inv, pd.DataFrame) and not inv.empty and "date" in inv:
        inv_aligned = inv.copy()
        inv_aligned["date"] = pd.to_datetime(inv_aligned["date"])
        if "inventory_change" in inv_aligned:
            inv_aligned["inventory"] = -pd.to_numeric(
                inv_aligned["inventory_change"], errors="coerce")
        elif "inventory_qty" in inv_aligned:
            qty = pd.to_numeric(inv_aligned["inventory_qty"], errors="coerce")
            inv_aligned["inventory"] = -qty.pct_change(fill_method=None)
        if "inventory" in inv_aligned:
            out = out.merge(
                inv_aligned[["date", "inventory"]].drop_duplicates("date"),
                on="date", how="left", validate="one_to_one")
    if "inventory" not in out:
        out["inventory"] = np.nan

    out["_close"] = out.pop("close")
    return out


# --------------------------------------------------------------------------- #
# Cross-sectional assembly
# --------------------------------------------------------------------------- #
def assemble_panel(per_variety: list[pd.DataFrame], cfg: CTAConfig) -> pd.DataFrame:
    panel = pd.concat(per_variety, ignore_index=True)
    # cross-sectional momentum from time-series momentum ranked across varieties
    panel["xs_momentum"] = panel.groupby("date")["ts_momentum"].rank(pct=True) - 0.5

    use = [f for f in cfg.factors if f in panel.columns]
    grouped = panel.groupby("date")
    z = pd.DataFrame(index=panel.index)
    for col in use:
        z[col] = (
            panel[col] - grouped[col].transform("mean")
        ) / (grouped[col].transform("std") + 1e-12)
    panel["composite"] = z.mean(axis=1)
    return panel


# --------------------------------------------------------------------------- #
# Long-short variety backtest
# --------------------------------------------------------------------------- #
def backtest_long_short(panel: pd.DataFrame, cfg: CTAConfig) -> pd.DataFrame:
    """Form long-top / short-bottom legs by composite; return daily portfolio returns."""
    panel = panel.sort_values("date")
    panel["fwd_ret"] = panel.groupby("variety")["_close"].transform(
        lambda s: s.pct_change().shift(-1))

    def _port_ret(g):
        g = g.dropna(subset=["composite", "fwd_ret"])
        if len(g) < 4:
            return pd.Series({"gross_ls_ret": np.nan, "roll_cost": 0.0})
        k = max(1, int(len(g) * cfg.top_frac))
        ranked = g.sort_values("composite")
        short_leg = ranked.head(k)["fwd_ret"].mean()
        long_leg = ranked.tail(k)["fwd_ret"].mean()
        selected = pd.concat([ranked.head(k), ranked.tail(k)])
        roll_rate = (
            selected["roll_flag"].fillna(False).astype(float).mean()
            if "roll_flag" in selected else 0.0
        )
        return pd.Series({
            "gross_ls_ret": long_leg - short_leg,
            "roll_cost": roll_rate * cfg.roll_cost_bp / 10_000.0,
        })

    daily = panel.groupby("date", group_keys=False).apply(_port_ret)
    if isinstance(daily, pd.Series):
        daily = daily.unstack()
    daily["ls_ret"] = daily["gross_ls_ret"] - daily["roll_cost"]
    daily["nav"] = (1 + daily["ls_ret"].fillna(0)).cumprod()
    return daily


def perf_stats(daily: pd.DataFrame) -> dict:
    r = daily["ls_ret"].dropna()
    if r.empty:
        return {"sharpe": float("nan"), "ann_ret": float("nan"), "max_dd": float("nan")}
    sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() else float("nan")
    nav = daily["nav"].dropna()
    max_dd = float((nav / nav.cummax() - 1).min())
    return {"sharpe": round(float(sharpe), 3),
            "ann_ret": round(float(r.mean() * 252), 4),
            "max_dd": round(max_dd, 4)}


# --------------------------------------------------------------------------- #
# Toy data / CLI
# --------------------------------------------------------------------------- #
def make_toy(n_var: int = 12, n_days: int = 500, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-01", periods=n_days)
    frames = []
    for v in range(n_var):
        drift = rng.normal(0, 0.0003)
        close = 1000 * np.exp(np.cumsum(rng.normal(drift, 0.015, n_days)))
        f = pd.DataFrame({"date": dates, "variety": f"V{v:02d}"})
        f["_close"] = close
        f["carry"] = rng.normal(0, 1, n_days)
        f["ts_momentum"] = pd.Series(close).pct_change(60).to_numpy()
        f["basis_momentum"] = rng.normal(0, 1, n_days)
        f["inventory"] = rng.normal(0, 1, n_days)
        f["roll_flag"] = False
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def write_report(path: str, panel: pd.DataFrame, daily: pd.DataFrame, cfg: CTAConfig,
                 degraded: list[str] | None = None) -> None:
    """Write the report artifact promised by the skill output contract."""
    degraded = list(degraded or [])
    if panel["variety"].nunique() < 4:
        degraded.append(
            "fewer than 4 varieties: cross-sectional long-short performance is unavailable"
        )
    stats = perf_stats(daily)
    factor_ic = {}
    for factor in cfg.factors:
        if factor in panel and "fwd_ret" in panel:
            value = panel[[factor, "fwd_ret"]].corr(method="spearman").iloc[0, 1]
            factor_ic[factor] = value
    if panel[cfg.factors].notna().mean().min() < 0.5:
        degraded.append("one or more factor sources have below-50% aligned-date coverage")
    roll_count = int(panel.get("roll_flag", pd.Series(dtype=bool)).fillna(False).sum())
    lines = [
        "# Commodity Carry CTA Report",
        "",
        "## Scope & Performance",
        "",
        f"- Varieties / dates: {panel['variety'].nunique()} / {panel['date'].nunique()}",
        f"- Net annualized return: {stats['ann_ret']}",
        f"- Net Sharpe: {stats['sharpe']}",
        f"- Maximum drawdown: {stats['max_dd']}",
        f"- Dominant-contract roll observations: {roll_count}",
        f"- Roll cost assumption: {cfg.roll_cost_bp:.2f} bp per selected roll observation",
        "",
        "## Per-factor Rank IC",
        "",
    ]
    lines.extend([
        f"- `{name}`: {value:.4f}" if np.isfinite(value) else f"- `{name}`: unavailable"
        for name, value in factor_ic.items()
    ] or ["- unavailable"])
    lines.extend([
        "",
        "## Degradation & Caveats",
        "",
    ])
    lines.extend([f"- {item}" for item in degraded] or ["- None detected by automated checks."])
    lines.extend([
        "- Carry uses date-aligned `basis_ratio` when annualized basis is unavailable.",
        "- Roll-day returns use the new contract's own prior close; sparse missing priors are set to zero and flagged.",
        "- Inventory is exchange-reported and may be sparse or publication-lagged.",
        "- Research/education only; no orders are placed.",
        "",
    ])
    report = Path(path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-sectional commodity CTA factors + backtest.")
    ap.add_argument("--varieties", help="comma-separated variety codes (omit for toy)")
    ap.add_argument("--start-date")
    ap.add_argument("--end-date")
    ap.add_argument("--top-frac", type=float, default=0.25)
    ap.add_argument("--roll-cost-bp", type=float, default=5.0)
    ap.add_argument("--out", default="commodity_factors.csv")
    ap.add_argument("--report", default="cta_report.md")
    args = ap.parse_args()

    cfg = CTAConfig(top_frac=args.top_frac, roll_cost_bp=args.roll_cost_bp)
    degraded = []
    if args.varieties and args.start_date and args.end_date:
        per = []
        for v in args.varieties.split(","):
            cont = build_continuous(v, args.start_date, args.end_date)
            pd_api = _load_panda_data()
            basis = pd.DataFrame(pd_api.get_future_basis(
                underlying_symbol=v, start_date=args.start_date, end_date=args.end_date))
            contracts = cont.get("contract", pd.Series(dtype=str)).dropna().unique().tolist()
            try:
                term = pd.DataFrame(pd_api.get_future_term_structure(
                    symbol=contracts, start_date=args.start_date, end_date=args.end_date))
            except Exception as exc:
                term = pd.DataFrame()
                degraded.append(f"{v}: term structure unavailable ({type(exc).__name__})")
            try:
                inv = pd.DataFrame(pd_api.get_future_inventory(
                    symbol=v, start_date=args.start_date, end_date=args.end_date))
            except Exception as exc:
                inv = pd.DataFrame()
                degraded.append(f"{v}: inventory unavailable ({type(exc).__name__}: {exc})")
            for name, frame in (("continuous", cont), ("basis", basis), ("inventory", inv)):
                if frame.empty:
                    degraded.append(f"{v}: {name} source returned no rows")
            per.append(compute_variety_factors(v, cont, basis, term, inv, cfg))
        panel = assemble_panel(per, cfg)
    else:
        print("[info] no inputs; running toy demo")
        panel = make_toy()
        panel = assemble_panel([panel[panel["variety"] == v] for v in panel["variety"].unique()], cfg)

    panel.drop(columns=["_close"], errors="ignore").to_csv(args.out, index=False)
    daily = backtest_long_short(panel, cfg)
    write_report(args.report, panel, daily, cfg, degraded)
    print(f"[ok] wrote {args.out} ({panel['variety'].nunique()} varieties)")
    print(f"[ok] wrote {args.report}")
    print("long-short perf:", perf_stats(daily))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
