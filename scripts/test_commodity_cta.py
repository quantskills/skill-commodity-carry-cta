"""Smoke tests for the commodity CTA skeleton.

Run: python scripts/test_commodity_cta.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from commodity_cta import (
    CTAConfig,
    _stitch,
    assemble_panel,
    backtest_long_short,
    build_continuous,
    compute_variety_factors,
    make_toy,
    main,
    perf_stats,
    write_report,
)


def _toy_panel(cfg):
    panel = make_toy(n_var=10, n_days=300)
    return assemble_panel([panel[panel["variety"] == v] for v in panel["variety"].unique()], cfg)


def test_composite_built():
    cfg = CTAConfig()
    panel = _toy_panel(cfg)
    assert "composite" in panel.columns
    assert "xs_momentum" in panel.columns


def test_backtest_returns_nav():
    cfg = CTAConfig(top_frac=0.3)
    daily = backtest_long_short(_toy_panel(cfg), cfg)
    assert "nav" in daily.columns and "ls_ret" in daily.columns
    stats = perf_stats(daily)
    assert set(stats) == {"sharpe", "ann_ret", "max_dd"}


def test_stitch_uses_new_contract_own_return_on_roll_date():
    dates = pd.date_range("2026-01-01", periods=4)
    dominant = pd.DataFrame({
        "date": dates,
        "symbol": ["A1.DCE", "A1.DCE", "A2.DCE", "A2.DCE"],
    })
    daily = pd.DataFrame({
        "date": [dates[0], dates[1], dates[1], dates[2], dates[3]],
        "symbol": ["A1.DCE", "A1.DCE", "A2.DCE", "A2.DCE", "A2.DCE"],
        "close": [100.0, 101.0, 198.0, 200.0, 202.0],
    })
    stitched = _stitch(dominant, daily)
    assert len(stitched) == 4
    assert stitched["roll_flag"].tolist() == [False, False, True, False]
    assert np.isclose(stitched.loc[2, "ret"], 200.0 / 198.0 - 1.0)
    assert stitched.loc[2, "ret"] < 0.05


def test_factor_inputs_are_aligned_by_date():
    dates = pd.date_range("2026-01-01", periods=4)
    cont = pd.DataFrame({
        "date": dates,
        "close": [100.0, 101.0, 102.0, 103.0],
        "ret": [np.nan, 0.01, 0.0099, 0.0098],
        "roll_flag": [False] * 4,
    })
    basis = pd.DataFrame({
        "date": [dates[1], dates[3]],
        "basis_ratio": [1.0, 3.0],
    })
    inventory = pd.DataFrame({
        "date": [dates[0], dates[2]],
        "inventory_qty": [100.0, 90.0],
    })
    factors = compute_variety_factors(
        "A", cont, basis, pd.DataFrame(), inventory,
        CTAConfig(momentum_lookback=2, basis_lookback=1),
    )
    assert len(factors) == len(cont)
    assert np.isnan(factors.loc[0, "carry"])
    assert factors.loc[1, "carry"] == 1.0
    assert factors.loc[3, "carry"] == 3.0
    assert factors.loc[2, "inventory"] > 0


def test_top_fraction_rejects_overlapping_long_short_buckets():
    try:
        CTAConfig(top_frac=0.75)
    except ValueError:
        return
    raise AssertionError("top_frac > 0.5 must be rejected")


def test_build_continuous_uses_current_sdk_parameter_names():
    dates = pd.date_range("2026-01-01", periods=2)

    class FakeAPI:
        def __init__(self):
            self.dominant_kwargs = None
            self.daily_kwargs = None

        def get_future_dominant(self, **kwargs):
            self.dominant_kwargs = kwargs
            return pd.DataFrame({"date": dates, "symbol": ["A1.DCE", "A1.DCE"]})

        def get_future_daily(self, **kwargs):
            self.daily_kwargs = kwargs
            return pd.DataFrame({
                "date": dates, "symbol": ["A1.DCE", "A1.DCE"], "close": [100.0, 101.0],
            })

    api = FakeAPI()
    with patch("commodity_cta._load_panda_data", return_value=api):
        result = build_continuous("A", "20260101", "20260102")
    assert api.dominant_kwargs["underlying_symbol"] == "A"
    assert api.daily_kwargs["symbol"] == ["A1.DCE"]
    assert not result.empty


def test_report_contract_is_materialized():
    cfg = CTAConfig()
    panel = _toy_panel(cfg)
    daily = backtest_long_short(panel, cfg)
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "cta_report.md"
        write_report(str(report), panel, daily, cfg)
        text = report.read_text(encoding="utf-8")
        assert "# Commodity Carry CTA Report" in text
        assert "Roll cost assumption" in text


def test_single_variety_report_discloses_unavailable_cross_section():
    cfg = CTAConfig()
    one = make_toy(n_var=1, n_days=100)
    panel = assemble_panel([one], cfg)
    daily = backtest_long_short(panel, cfg)
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "cta_report.md"
        write_report(str(report), panel, daily, cfg)
        assert "fewer than 4 varieties" in report.read_text(encoding="utf-8")


def test_optional_factor_source_failure_degrades_instead_of_crashing_cli():
    dates = pd.date_range("2026-01-01", periods=4)

    class PartiallyFailingAPI:
        def get_future_dominant(self, **kwargs):
            return pd.DataFrame({"date": dates, "symbol": ["CU1.SHF"] * 4})

        def get_future_daily(self, **kwargs):
            return pd.DataFrame({
                "date": dates, "symbol": ["CU1.SHF"] * 4,
                "close": [100.0, 101.0, 102.0, 103.0],
            })

        def get_future_basis(self, **kwargs):
            return pd.DataFrame({"date": dates, "basis_ratio": [1.0, 1.1, 1.2, 1.3]})

        def get_future_term_structure(self, **kwargs):
            raise RuntimeError("term unavailable")

        def get_future_inventory(self, **kwargs):
            raise RuntimeError("inventory unavailable")

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "factors.csv"
        report = Path(tmp) / "cta_report.md"
        argv = [
            "commodity_cta.py", "--varieties", "CU",
            "--start-date", "20260101", "--end-date", "20260104",
            "--out", str(out), "--report", str(report),
        ]
        with patch("commodity_cta._load_panda_data", return_value=PartiallyFailingAPI()):
            with patch.object(sys, "argv", argv):
                assert main() == 0
        text = report.read_text(encoding="utf-8")
        assert out.exists()
        assert "inventory unavailable" in text


if __name__ == "__main__":
    test_composite_built()
    test_backtest_returns_nav()
    test_stitch_uses_new_contract_own_return_on_roll_date()
    test_factor_inputs_are_aligned_by_date()
    test_top_fraction_rejects_overlapping_long_short_buckets()
    test_build_continuous_uses_current_sdk_parameter_names()
    test_report_contract_is_materialized()
    test_single_variety_report_discloses_unavailable_cross_section()
    test_optional_factor_source_failure_degrades_instead_of_crashing_cli()
    print("all smoke tests passed")
