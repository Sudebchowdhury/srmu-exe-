"""Run with:  python -m pytest -v"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ev_calculator.model import (DEFAULT_EF, PRESET_MIXES, REFERENCE_MIX, SOURCES, Inputs, compute,  # noqa: E402
                                 grid_emission_factor, mix_with_coal, normalize_mix, rebalance)
from ev_calculator.validation import CASES  # noqa: E402


@pytest.mark.parametrize("case_fn", CASES, ids=[c.__name__.strip("_") for c in CASES])
def test_validation_case(case_fn):
    case = case_fn()
    assert case.passed, f"{case.name}: expected {case.expected}, got {case.actual}"


def test_brief_example_numbers():
    r = compute(Inputs())                       # EV 150 Wh/km, petrol 15 km/L, gas 10 %, losses 18 %, charger 90 %
    assert r.petrol_g_per_km == pytest.approx(154.0)
    assert r.generated_wh_per_km == pytest.approx(150 / 0.738)
    assert r.breakeven_coal_pct == pytest.approx(75.0, abs=0.05)


def test_website_demo_numbers():
    mix = {"coal": 0, "gas": 20, "hydro": 20, "nuclear": 20, "solar": 20, "wind": 20}
    r = compute(Inputs(mix=mix, petrol_km_per_l=16))
    assert r.grid_ef * 1000 == pytest.approx(90.0)
    assert r.ev_g_per_km == pytest.approx(18.3, abs=0.05)
    assert r.petrol_g_per_km == pytest.approx(144.4, abs=0.05)
    assert r.reduction_pct == pytest.approx(87.3, abs=0.05)
    assert r.breakeven_coal_pct == pytest.approx(65.3, abs=0.05)
    assert r.solar_kwp == pytest.approx(1.67, abs=0.005)
    assert r.saving_kg_per_year == pytest.approx(1840.8, abs=0.5)


def test_breakeven_is_a_true_crossing():
    inp = Inputs()
    r = compute(inp)
    mix = mix_with_coal(inp, r.breakeven_coal_pct)
    ef = grid_emission_factor(mix, DEFAULT_EF)
    assert ef * r.generated_wh_per_km == pytest.approx(r.petrol_g_per_km)
    assert sum(mix.values()) == pytest.approx(100.0)


def test_monotonic_in_losses_and_consumption():
    base = compute(Inputs()).ev_g_per_km
    assert compute(Inputs(grid_loss_pct=30)).ev_g_per_km > base
    assert compute(Inputs(charger_eff_pct=70)).ev_g_per_km > base
    assert compute(Inputs(ev_wh_per_km=200)).ev_g_per_km > base


@pytest.mark.parametrize("key", SOURCES)
@pytest.mark.parametrize("value", [0, 12.34, 50, 99.9, 100])
def test_rebalance_keeps_total_100(key, value):
    out = rebalance(PRESET_MIXES["Mixed national grid"], key, value)
    assert sum(out.values()) == pytest.approx(100.0, abs=1e-9)
    assert all(v >= 0 for v in out.values())
    assert out[key] == pytest.approx(value, abs=0.05)


def test_normalize_mix():
    out = normalize_mix({s: 10.0 for s in SOURCES})
    assert sum(out.values()) == pytest.approx(100.0)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        compute(Inputs(mix={**REFERENCE_MIX, "coal": 50.0}))       # total != 100
    with pytest.raises(ValueError):
        compute(Inputs(charger_eff_pct=0))
    with pytest.raises(ValueError):
        compute(Inputs(grid_loss_pct=100))
