"""Validation suite (the brief asks for at least five test cases; there are 11 here).

The 'expected' values are written out as plain arithmetic, independent of model.compute(),
so each case compares the program against a manual calculation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

from .model import SOURCES, Inputs, compute, grid_emission_factor, REFERENCE_MIX, PRESET_MIXES


@dataclass
class Case:
    name: str
    description: str
    expected: str
    actual: str
    passed: bool


def _pure(source: str) -> Dict[str, float]:
    return {s: (100.0 if s == source else 0.0) for s in SOURCES}


def _close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


# ------------------------------------------------------------------ individual cases
def _solar() -> Case:
    r = compute(Inputs(mix=_pure("solar")))
    ok = _close(r.grid_ef, 0.0) and _close(r.ev_g_per_km, 0.0)
    return Case("100 % Solar grid", "Grid EF and EV emissions must be zero.",
                "0.000 kg/kWh and 0.00 g/km", f"{r.grid_ef:.3f} kg/kWh and {r.ev_g_per_km:.2f} g/km", ok)


def _hydro() -> Case:
    r = compute(Inputs(mix=_pure("hydro")))
    ok = _close(r.grid_ef, 0.0) and _close(r.ev_g_per_km, 0.0)
    return Case("100 % Hydro grid", "Hydro-only operational model: zero emissions.",
                "0.000 kg/kWh and 0.00 g/km", f"{r.grid_ef:.3f} kg/kWh and {r.ev_g_per_km:.2f} g/km", ok)


def _coal() -> Case:
    r = compute(Inputs(mix=_pure("coal")))
    exp_ev = 150 / (0.90 * 0.82) * 0.95            # = 193.09 g/km (manual)
    ok = _close(r.grid_ef, 0.95) and _close(r.ev_g_per_km, exp_ev, 1e-6) and r.ev_g_per_km > r.petrol_g_per_km
    return Case("100 % Coal grid", "Worst case: EF = 0.95 kg/kWh, EV dirtier than 154 g/km petrol.",
                f"0.950 kg/kWh, {exp_ev:.2f} g/km (> petrol 154.00)",
                f"{r.grid_ef:.3f} kg/kWh, {r.ev_g_per_km:.2f} g/km (petrol {r.petrol_g_per_km:.2f})", ok)


def _mixed() -> Case:
    r = compute(Inputs(mix=PRESET_MIXES["Mixed national grid"]))
    exp_ef = 0.60 * 0.95 + 0.15 * 0.45             # = 0.6375 kg/kWh (manual)
    exp_ev = 150 / (0.90 * 0.82) * exp_ef          # = 129.57 g/km (manual)
    ok = _close(r.grid_ef, exp_ef) and _close(r.ev_g_per_km, exp_ev, 1e-6)
    return Case("Mixed national grid", "60 % coal, 15 % gas, 10 % hydro, 3 % nuclear, 6 % solar, 6 % wind.",
                f"{exp_ef * 1000:.1f} g/kWh, {exp_ev:.2f} g/km", f"{r.grid_ef * 1000:.1f} g/kWh, {r.ev_g_per_km:.2f} g/km", ok)


def _losses() -> Case:
    mix = PRESET_MIXES["Mixed national grid"]
    base = compute(Inputs(mix=mix))
    worse = compute(Inputs(mix=mix, grid_loss_pct=20.0, charger_eff_pct=85.0))
    exp = 150 / (0.85 * 0.80) * 0.6375             # = 140.62 g/km (manual)
    ok = worse.ev_g_per_km > base.ev_g_per_km and _close(worse.ev_g_per_km, exp, 1e-6)
    return Case("Increased charging losses", "Grid loss 18->20 %, charger 90->85 %: EV g/km must rise.",
                f"{exp:.2f} g/km (> {base.ev_g_per_km:.2f})", f"{worse.ev_g_per_km:.2f} g/km", ok)


def _consumption() -> Case:
    mix = PRESET_MIXES["Mixed national grid"]
    a = compute(Inputs(mix=mix, ev_wh_per_km=150.0))
    b = compute(Inputs(mix=mix, ev_wh_per_km=180.0))
    ok = b.ev_g_per_km > a.ev_g_per_km and _close(b.ev_g_per_km / a.ev_g_per_km, 180 / 150, 1e-9)
    return Case("Higher Wh/km", "EV g/km scales linearly with consumption (180 vs 150 Wh/km = x1.20).",
                "ratio 1.2000", f"ratio {b.ev_g_per_km / a.ev_g_per_km:.4f}", ok)


def _breakeven() -> Case:
    r = compute(Inputs(mix=REFERENCE_MIX))          # EV 150 Wh/km, petrol 15 km/L, gas fixed 10 %
    target = (2.31 / 15 * 1000) / (150 / 0.738)    # 0.75768 kg/kWh needed for EV = petrol
    exp = 90 * (target - 0.045) / (0.90 - 0.045)   # = 75.02 %  (matches 75.0 % in the brief's graph)
    ok = r.breakeven_status == "value" and abs(r.breakeven_coal_pct - exp) < 1e-6 and abs(r.breakeven_coal_pct - 75.0) < 0.05
    got = f"{r.breakeven_coal_pct:.2f} %" if r.breakeven_coal_pct is not None else r.breakeven_status
    return Case("Break-even coal share", "Brief's example (gas fixed 10 %): break-even at 75.0 % coal.",
                f"{exp:.2f} % coal", got, ok)


def _never() -> Case:
    r = compute(Inputs(mix=REFERENCE_MIX, ev_wh_per_km=50.0, petrol_km_per_l=5.0))
    ok = r.breakeven_status == "never" and r.breakeven_coal_pct is None
    return Case("Break-even 'never'", "Very efficient EV vs thirsty petrol car: even max coal stays cleaner.",
                "never", r.breakeven_status, ok)


def _already() -> Case:
    mix = {"coal": 0.0, "gas": 40.0, "hydro": 20.0, "nuclear": 20.0, "solar": 10.0, "wind": 10.0}
    r = compute(Inputs(mix=mix, ev_wh_per_km=400.0, petrol_km_per_l=40.0))
    ok = r.breakeven_status == "already" and r.ev_g_per_km > r.petrol_g_per_km
    return Case("EV already worse", "Heavy EV vs 40 km/L petrol, 40 % gas: EV loses even at 0 % coal.",
                "already", f"{r.breakeven_status} ({r.ev_g_per_km:.1f} vs {r.petrol_g_per_km:.1f} g/km)", ok)


def _solar_size() -> Case:
    r = compute(Inputs())
    daily = 150 * 40 / 1000 / 0.90                  # = 6.667 kWh/day at the plug (manual)
    exp_kwp = daily / 4.0                           # = 1.667 kWp
    ok = _close(r.daily_plug_kwh, daily) and _close(r.solar_kwp, exp_kwp)
    return Case("Rooftop solar sizing", "kWp = daily plug kWh / solar generation per kWp (4 kWh/kWp/day).",
                f"{daily:.3f} kWh/day -> {exp_kwp:.3f} kWp", f"{r.daily_plug_kwh:.3f} kWh/day -> {r.solar_kwp:.3f} kWp", ok)


def _sum_formula() -> Case:
    mix = {"coal": 12.5, "gas": 31.5, "hydro": 20.0, "nuclear": 6.0, "solar": 18.0, "wind": 12.0}
    exp = 0.125 * 0.95 + 0.315 * 0.45               # = 0.2605 kg/kWh (manual)
    got = grid_emission_factor(mix, Inputs().ef)
    return Case("EF = sum(share x factor)", "Arbitrary mix checked by hand.",
                f"{exp:.4f} kg/kWh", f"{got:.4f} kg/kWh", _close(got, exp))


CASES: List[Callable[[], Case]] = [
    _solar, _hydro, _coal, _mixed, _losses, _consumption,
    _breakeven, _never, _already, _solar_size, _sum_formula,
]


def run_all() -> List[Case]:
    out: List[Case] = []
    for fn in CASES:
        try:
            out.append(fn())
        except Exception as exc:  # a crashing case is a failed case, not a crashed app
            out.append(Case(fn.__name__.strip("_"), "Raised an exception.", "no error", repr(exc), False))
    return out


def format_report(cases: List[Case]) -> str:
    lines = []
    for i, c in enumerate(cases, 1):
        lines.append(f"[{'PASS' if c.passed else 'FAIL'}] {i:02d}. {c.name}\n"
                     f"       expected: {c.expected}\n       actual  : {c.actual}")
    passed = sum(c.passed for c in cases)
    lines.append(f"\n{passed}/{len(cases)} validation cases passed.")
    return "\n".join(lines)
