# EV Charging Emission Calculator – Grid Mix to g CO₂/km

**L&T EduTech · EV Mini-Project 5 · Fundamentals of Electric and Hybrid Electric Vehicle Technology**
SRMU · Team 5 · Electrical / Electronics

| Team 5 member | Department |
|---|---|
| Sudeb Chowdhury | EE |
| Gyandeep Yadav | EE |
| Rohan Choudhary | EC |
| Ansh Tyagi | EC |
| Kanishka Gupta | EE |


An interactive desktop app (Python · Tkinter · Matplotlib) that finds the **real CO₂ per km of charging an EV**
from the electricity mix, after charger and grid losses, and compares it with a petrol car.

> *On this grid mix the EV emits **X** g CO₂/km vs. **Y** g/km for petrol. Above **Z** % coal the EV loses its advantage.
> A **W** kWp solar panel makes it zero-emission.*  ← generated live by the app

![Dashboard](docs/dashboard.png)

## What it calculates (project brief → app)

| Brief requirement | Where in the app |
|---|---|
| Mix sliders (coal, gas, hydro, nuclear, solar, wind), total = 100 % | Section 01 – moving one slider rescales the others, so the total is always 100 % |
| Editable emission factors (coal 0.95, gas 0.45, others 0 kg CO₂/kWh) | Section 03 |
| T&D losses (18 %), charger efficiency (90 %), solar kWh/kWp/day (4) | Section 02 |
| EV Wh/km, petrol km/L (2.31 kg CO₂/L), daily distance | Section 02 |
| Grid emission factor (kg CO₂/kWh) – also the value to feed into Project 2 | KPI card + answer line |
| Electricity generated per km (Wh/km after charger and grid losses) | KPI card |
| EV g/km vs petrol g/km, and % | KPI cards + bar chart |
| Break-even coal share (gas fixed, coal replaces clean sources) or "never" | KPI card + Graph 1 |
| Daily charging energy at the plug (kWh/day) and rooftop solar size (kWp) | KPI cards |
| **Dynamic graphs** (update instantly on any input) | Mix donut · EV vs petrol · annual CO₂ · **Graph 1: coal share vs CO₂/km** |
| ≥ 5 validation test cases | **Validation tests** tab, `tests/`, `docs/VALIDATION.md` (11 cases) |
| Extras | CSV export, PDF report, presets (100 % coal/solar/hydro…), Reset |

## Formulas

```
EF_grid [kg/kWh]   = Σ ( share_i × EF_i )
Plug energy        = Wh/km at battery ÷ charger efficiency
Generated energy   = Plug energy ÷ (1 − grid loss)            # Wh/km at the power station
EV g/km            = Generated Wh/km × EF_grid                # Wh × kg/kWh = g
Petrol g/km        = (kg CO₂/L ÷ km/L) × 1000
Break-even coal    : EF(coal) is linear, solve EF(coal*) = Petrol g/km ÷ Generated Wh/km
Solar size [kWp]   = (Wh/km × daily km ÷ 1000 ÷ charger eff) ÷ (kWh per kWp per day)
```

## Run it

**Windows `.exe`** – download `EV-Charging-Emission-Calculator.exe` from the
[Releases](../../releases) page (or from the *Actions → latest run → Artifacts*) and double-click. No Python needed.

**From source** (Python 3.10+; Tkinter ships with the python.org installer):

```bash
pip install -r requirements.txt
python main.py                # GUI
python main.py --selftest     # validation cases in the terminal
python -m pip install -r requirements-dev.txt && python -m pytest -v
```

## Build the `.exe` yourself

On Windows, double-click **`build_exe.bat`** → `dist\EV-Charging-Emission-Calculator.exe`.
Or push to GitHub: the workflow in `.github/workflows/build-exe.yml` runs the tests and builds the `.exe` automatically
(tag a release with `git tag v1.0.0 && git push --tags` to attach it to a GitHub Release).

## Project structure

```
main.py                    entry point (GUI, or --selftest)
ev_calculator/model.py     pure calculation model (no GUI) – Inputs, compute(), rebalance()
ev_calculator/validation.py  11 validation cases with hand-calculated expected values
ev_calculator/plots.py     Matplotlib dashboard (shared by GUI and PDF)
ev_calculator/report.py    CSV + PDF export
ev_calculator/gui.py       Tkinter interface
tests/test_model.py        pytest suite
docs/                      validation write-up, sample CSV/PDF, dashboard image
build_exe.bat              local Windows build script
.github/workflows/         CI: test + build .exe
```

## Notes and assumptions
* Emission factors are **operational (tailpipe / stack)** values, as specified in the brief; life-cycle emissions are not included.
* "Break-even" holds gas fixed and lets coal replace the other sources in proportion, so the largest possible coal share is
  100 % − gas %. If even that keeps the EV cleaner the app reports **never**; if the EV is already dirtier at 0 % coal it reports **already**.
* Solar sizing is on a net-metering basis using the **plug** energy per day. Roof area (≈ 6 m² per kWp) is only an indicative display value.
