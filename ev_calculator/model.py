"""Pure calculation model for the EV charging emission calculator.

No GUI imports live here, so the model can be unit-tested, reused, and used to
feed the grid emission factor into Project 2.

Unit cheat-sheet
----------------
* Emission factors are in kg CO2 / kWh, which is numerically equal to g CO2 / Wh.
* So:   EV g/km = (Wh drawn from the power station per km) x (grid EF in kg/kWh)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

SOURCES: Tuple[str, ...] = ("coal", "gas", "hydro", "nuclear", "solar", "wind")
SOURCE_LABELS: Dict[str, str] = {
    "coal": "Coal", "gas": "Natural gas", "hydro": "Hydro",
    "nuclear": "Nuclear", "solar": "Solar", "wind": "Wind",
}

# Operational emission factors, kg CO2 / kWh (editable in the app).
DEFAULT_EF: Dict[str, float] = {
    "coal": 0.95, "gas": 0.45, "hydro": 0.0, "nuclear": 0.0, "solar": 0.0, "wind": 0.0,
}

# Mix that reproduces the example graph in the project brief (coal 40 %, gas 10 %).
REFERENCE_MIX: Dict[str, float] = {
    "coal": 40.0, "gas": 10.0, "hydro": 20.0, "nuclear": 10.0, "solar": 10.0, "wind": 10.0,
}

PRESET_MIXES: Dict[str, Dict[str, float]] = {
    "Reference (brief graph)": REFERENCE_MIX,
    "Mixed national grid": {"coal": 60.0, "gas": 15.0, "hydro": 10.0,
                            "nuclear": 3.0, "solar": 6.0, "wind": 6.0},
    "100 % Coal": {"coal": 100.0, "gas": 0.0, "hydro": 0.0, "nuclear": 0.0, "solar": 0.0, "wind": 0.0},
    "100 % Gas": {"coal": 0.0, "gas": 100.0, "hydro": 0.0, "nuclear": 0.0, "solar": 0.0, "wind": 0.0},
    "100 % Hydro": {"coal": 0.0, "gas": 0.0, "hydro": 100.0, "nuclear": 0.0, "solar": 0.0, "wind": 0.0},
    "100 % Solar": {"coal": 0.0, "gas": 0.0, "hydro": 0.0, "nuclear": 0.0, "solar": 100.0, "wind": 0.0},
}

DAYS_PER_YEAR = 365
M2_PER_KWP = 6.0          # rough rooftop area per kWp (typical assumption, display only)
MIX_TOLERANCE = 0.05      # allowed deviation of the mix total from 100 %


@dataclass
class Inputs:
    mix: Dict[str, float] = field(default_factory=lambda: dict(REFERENCE_MIX))   # % each, total 100
    ef: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_EF))       # kg CO2 / kWh
    grid_loss_pct: float = 18.0          # transmission & distribution losses, %
    charger_eff_pct: float = 90.0        # charger efficiency, %
    solar_kwh_per_kwp_day: float = 4.0   # solar generation per kWp per day
    ev_wh_per_km: float = 150.0          # EV consumption measured at the battery
    petrol_km_per_l: float = 15.0        # petrol vehicle mileage
    petrol_kg_co2_per_l: float = 2.31    # kg CO2 per litre of petrol
    daily_km: float = 40.0               # daily distance

    def validate(self) -> None:
        for s in SOURCES:
            if s not in self.mix or s not in self.ef:
                raise ValueError(f"Missing data for source '{s}'.")
            if self.mix[s] < 0:
                raise ValueError(f"Share of {s} cannot be negative.")
            if self.ef[s] < 0:
                raise ValueError(f"Emission factor of {s} cannot be negative.")
        total = sum(self.mix[s] for s in SOURCES)
        if abs(total - 100.0) > MIX_TOLERANCE:
            raise ValueError(f"Electricity mix must total 100 % (currently {total:.2f} %).")
        if not 0 < self.charger_eff_pct <= 100:
            raise ValueError("Charger efficiency must be in (0, 100] %.")
        if not 0 <= self.grid_loss_pct < 100:
            raise ValueError("Grid losses must be in [0, 100) %.")
        if self.ev_wh_per_km <= 0:
            raise ValueError("EV consumption must be positive.")
        if self.petrol_km_per_l <= 0 or self.petrol_kg_co2_per_l <= 0:
            raise ValueError("Petrol mileage and CO2 per litre must be positive.")
        if self.daily_km < 0:
            raise ValueError("Daily distance cannot be negative.")
        if self.solar_kwh_per_kwp_day <= 0:
            raise ValueError("Solar generation per kWp must be positive.")


@dataclass
class Results:
    grid_ef: float                 # kg CO2 / kWh  (also the value to feed into Project 2)
    plug_wh_per_km: float          # Wh/km at the charger plug
    generated_wh_per_km: float     # Wh/km generated at the power station (after charger + grid losses)
    ev_g_per_km: float
    petrol_g_per_km: float
    ev_vs_petrol_pct: float        # EV as % of petrol
    reduction_pct: float           # saving vs petrol in % (negative if EV is worse)
    target_grid_ef: float          # grid EF at which EV == petrol, kg/kWh
    max_coal_pct: float            # coal can replace clean sources up to 100 % - gas %
    current_coal_pct: float
    breakeven_status: str          # "value" | "never" | "already"
    breakeven_coal_pct: Optional[float]
    daily_plug_kwh: float          # kWh/day at the plug
    daily_generated_kwh: float     # kWh/day generated at the power station
    solar_kwp: float               # rooftop kWp for zero-emission charging (net metering)
    ev_kg_per_day: float
    petrol_kg_per_day: float
    saving_kg_per_day: float
    saving_kg_per_year: float
    ev_kg_per_year: float
    petrol_kg_per_year: float

    @property
    def ev_is_cleaner(self) -> bool:
        return self.ev_g_per_km < self.petrol_g_per_km


# --------------------------------------------------------------------------- helpers
def grid_emission_factor(mix: Dict[str, float], ef: Dict[str, float]) -> float:
    """Grid emission factor = sum(share x source factor), kg CO2/kWh."""
    return sum(mix[s] / 100.0 * ef[s] for s in SOURCES)


def mix_with_coal(inp: Inputs, coal_pct: float) -> Dict[str, float]:
    """Mix with a given coal share: gas stays fixed, coal replaces the other (clean) sources,
    which keep their relative proportions."""
    gas = inp.mix["gas"]
    rest = [s for s in SOURCES if s not in ("coal", "gas")]
    room = 100.0 - gas - coal_pct
    base = sum(inp.mix[s] for s in rest)
    out = {"coal": coal_pct, "gas": gas}
    for s in rest:
        out[s] = room * inp.mix[s] / base if base > 0 else room / len(rest)
    return out


def ef_at_coal(inp: Inputs, coal_pct: float) -> float:
    return grid_emission_factor(mix_with_coal(inp, coal_pct), inp.ef)


def coal_curve(inp: Inputs, n: int = 91) -> Tuple[List[float], List[float]]:
    """EV g CO2/km versus coal share (0 .. 100 % - gas %) for Graph 1."""
    gen_wh = inp.ev_wh_per_km / (inp.charger_eff_pct / 100.0) / (1.0 - inp.grid_loss_pct / 100.0)
    max_coal = 100.0 - inp.mix["gas"]
    xs = [max_coal * i / (n - 1) for i in range(n)]
    return xs, [gen_wh * ef_at_coal(inp, x) for x in xs]


def normalize_mix(mix: Dict[str, float], decimals: int = 1) -> Dict[str, float]:
    """Scale a mix proportionally so that it totals exactly 100 %."""
    total = sum(mix[s] for s in SOURCES)
    if total <= 0:
        return dict(REFERENCE_MIX)
    return _round_to_100({s: mix[s] * 100.0 / total for s in SOURCES}, decimals)


def rebalance(mix: Dict[str, float], key: str, value: float, decimals: int = 1) -> Dict[str, float]:
    """Set `key` to `value` and rescale the other sources proportionally so the total stays 100 %."""
    value = round(min(max(value, 0.0), 100.0), decimals)
    others = [s for s in SOURCES if s != key]
    remaining = 100.0 - value
    tot = sum(mix[s] for s in others)
    raw = {key: value}
    for s in others:
        raw[s] = remaining * mix[s] / tot if tot > 0 else remaining / len(others)
    return _round_to_100(raw, decimals, pinned=key)


def _round_to_100(raw: Dict[str, float], decimals: int, pinned: Optional[str] = None) -> Dict[str, float]:
    out = {s: round(raw[s], decimals) for s in SOURCES}
    residual = round(100.0 - sum(out.values()), decimals + 3)
    if abs(residual) > 1e-9:
        candidates = [s for s in SOURCES if s != pinned] or list(SOURCES)
        target = max(candidates, key=lambda s: out[s])
        out[target] = round(max(out[target] + residual, 0.0), decimals)
    return out


# --------------------------------------------------------------------------- main model
def compute(inp: Inputs) -> Results:
    inp.validate()
    grid_ef = grid_emission_factor(inp.mix, inp.ef)

    plug_wh = inp.ev_wh_per_km / (inp.charger_eff_pct / 100.0)
    gen_wh = plug_wh / (1.0 - inp.grid_loss_pct / 100.0)
    ev_g = gen_wh * grid_ef                                       # Wh/km x kg/kWh = g/km
    petrol_g = inp.petrol_kg_co2_per_l / inp.petrol_km_per_l * 1000.0

    # Break-even coal share (gas fixed, coal replaces clean sources)
    gas = inp.mix["gas"]
    max_coal = 100.0 - gas
    target_ef = petrol_g / gen_wh
    ef_lo = ef_at_coal(inp, 0.0)
    ef_hi = ef_at_coal(inp, max_coal)
    if ef_lo >= target_ef:
        status, be = "already", 0.0
    elif ef_hi <= target_ef:
        status, be = "never", None
    else:
        status, be = "value", max_coal * (target_ef - ef_lo) / (ef_hi - ef_lo)

    daily_plug = inp.ev_wh_per_km * inp.daily_km / 1000.0 / (inp.charger_eff_pct / 100.0)
    daily_gen = gen_wh * inp.daily_km / 1000.0
    ev_day = ev_g * inp.daily_km / 1000.0
    petrol_day = petrol_g * inp.daily_km / 1000.0

    return Results(
        grid_ef=grid_ef,
        plug_wh_per_km=plug_wh,
        generated_wh_per_km=gen_wh,
        ev_g_per_km=ev_g,
        petrol_g_per_km=petrol_g,
        ev_vs_petrol_pct=ev_g / petrol_g * 100.0,
        reduction_pct=(petrol_g - ev_g) / petrol_g * 100.0,
        target_grid_ef=target_ef,
        max_coal_pct=max_coal,
        current_coal_pct=inp.mix["coal"],
        breakeven_status=status,
        breakeven_coal_pct=be,
        daily_plug_kwh=daily_plug,
        daily_generated_kwh=daily_gen,
        solar_kwp=daily_plug / inp.solar_kwh_per_kwp_day,
        ev_kg_per_day=ev_day,
        petrol_kg_per_day=petrol_day,
        saving_kg_per_day=petrol_day - ev_day,
        saving_kg_per_year=(petrol_day - ev_day) * DAYS_PER_YEAR,
        ev_kg_per_year=ev_day * DAYS_PER_YEAR,
        petrol_kg_per_year=petrol_day * DAYS_PER_YEAR,
    )


def summary_sentence(inp: Inputs, res: Results) -> str:
    """The 'final answer' sentence required by the project brief."""
    if res.breakeven_status == "value":
        z = f"Above {res.breakeven_coal_pct:.1f} % coal the EV loses its advantage."
    elif res.breakeven_status == "never":
        z = (f"The EV never loses its advantage: even at the maximum possible coal share "
             f"({res.max_coal_pct:.0f} %, gas fixed) it stays cleaner than petrol.")
    else:
        z = "With these inputs the EV is already no cleaner than petrol, even at 0 % coal."
    return (f"On this grid mix the EV emits {res.ev_g_per_km:.1f} g CO\u2082/km vs. "
            f"{res.petrol_g_per_km:.1f} g/km for petrol. {z} "
            f"A {res.solar_kwp:.2f} kWp solar panel makes it zero-emission.")
