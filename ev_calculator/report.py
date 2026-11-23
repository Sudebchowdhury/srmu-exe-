"""CSV and PDF export."""
from __future__ import annotations

import csv
from datetime import datetime
from typing import List, Tuple

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from . import TEAM_MEMBERS, TEAM_NAME
from .model import SOURCES, SOURCE_LABELS, Inputs, Results, coal_curve, summary_sentence
from .plots import LIGHT, draw_dashboard
from .validation import format_report, run_all

Row = Tuple[str, str, str]


def input_rows(inp: Inputs) -> List[Row]:
    rows: List[Row] = [(f"Share of {SOURCE_LABELS[s]}", f"{inp.mix[s]:.1f}", "%") for s in SOURCES]
    rows += [(f"Emission factor of {SOURCE_LABELS[s]}", f"{inp.ef[s]:.3f}", "kg CO2/kWh") for s in SOURCES]
    rows += [
        ("Grid transmission & distribution losses", f"{inp.grid_loss_pct:.1f}", "%"),
        ("Charger efficiency", f"{inp.charger_eff_pct:.1f}", "%"),
        ("Solar generation per kWp", f"{inp.solar_kwh_per_kwp_day:.2f}", "kWh/kWp/day"),
        ("EV energy consumption (at battery)", f"{inp.ev_wh_per_km:.1f}", "Wh/km"),
        ("Petrol vehicle mileage", f"{inp.petrol_km_per_l:.1f}", "km/L"),
        ("Petrol CO2 per litre", f"{inp.petrol_kg_co2_per_l:.2f}", "kg CO2/L"),
        ("Daily distance", f"{inp.daily_km:.1f}", "km"),
    ]
    return rows


def result_rows(res: Results) -> List[Row]:
    if res.breakeven_status == "value":
        be = f"{res.breakeven_coal_pct:.2f}"
    else:
        be = "never" if res.breakeven_status == "never" else "already (0)"
    return [
        ("Grid emission factor (feeds Project 2)", f"{res.grid_ef:.4f}", "kg CO2/kWh"),
        ("Electricity generated per km (after charger & grid losses)", f"{res.generated_wh_per_km:.2f}", "Wh/km"),
        ("Energy at the plug per km", f"{res.plug_wh_per_km:.2f}", "Wh/km"),
        ("EV CO2 per km", f"{res.ev_g_per_km:.2f}", "g CO2/km"),
        ("Petrol CO2 per km", f"{res.petrol_g_per_km:.2f}", "g CO2/km"),
        ("EV as share of petrol", f"{res.ev_vs_petrol_pct:.1f}", "%"),
        ("Saving vs petrol", f"{res.reduction_pct:.1f}", "%"),
        ("Break-even coal share (EV = petrol)", be, "% coal"),
        ("Daily charging energy at the plug", f"{res.daily_plug_kwh:.3f}", "kWh/day"),
        ("Rooftop solar size for zero-emission charging", f"{res.solar_kwp:.3f}", "kWp"),
        ("EV CO2 per day", f"{res.ev_kg_per_day:.3f}", "kg"),
        ("Petrol CO2 per day", f"{res.petrol_kg_per_day:.3f}", "kg"),
        ("Saving per day", f"{res.saving_kg_per_day:.3f}", "kg CO2"),
        ("Saving per year", f"{res.saving_kg_per_year:.1f}", "kg CO2"),
    ]


def export_csv(path: str, inp: Inputs, res: Results) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:   # BOM so Excel shows subscripts correctly
        w = csv.writer(fh)
        w.writerow(["EV Charging Emission Calculator - Team 5", datetime.now().strftime("%Y-%m-%d %H:%M")])
        w.writerow([TEAM_NAME, ", ".join(TEAM_MEMBERS)])
        w.writerow([])
        w.writerow(["INPUTS"]); w.writerow(["Parameter", "Value", "Unit"])
        w.writerows(input_rows(inp))
        w.writerow([])
        w.writerow(["RESULTS"]); w.writerow(["Parameter", "Value", "Unit"])
        w.writerows(result_rows(res))
        w.writerow([])
        w.writerow(["COAL SWEEP (gas fixed, coal replaces clean sources)"])
        w.writerow(["Coal share (%)", "EV g CO2/km", "Petrol g CO2/km"])
        xs, ys = coal_curve(inp, 46)
        for x, y in zip(xs, ys):
            w.writerow([f"{x:.2f}", f"{y:.2f}", f"{res.petrol_g_per_km:.2f}"])


def _text_page(title: str, blocks: List[Tuple[str, List[str]]]) -> Figure:
    fig = Figure(figsize=(8.27, 11.69))
    fig.text(0.07, 0.95, title, fontsize=16, fontweight="bold", color=LIGHT["text"])
    y = 0.91
    for head, lines in blocks:
        fig.text(0.07, y, head, fontsize=11, fontweight="bold", color=LIGHT["accent"])
        y -= 0.025
        for ln in lines:
            fig.text(0.08, y, ln, fontsize=8.5, color=LIGHT["text"], family="monospace")
            y -= 0.0185
        y -= 0.015
    return fig


def export_pdf(path: str, inp: Inputs, res: Results) -> None:
    import textwrap

    fmt = lambda rows: [f"{a[:58]:<58} {b:>10}  {c}" for a, b, c in rows]
    answer = textwrap.wrap(summary_sentence(inp, res), 95)
    with PdfPages(path) as pdf:
        page1 = _text_page("EV Charging Emission Report - Team 5", [
            (f"{TEAM_NAME} members", textwrap.wrap(", ".join(TEAM_MEMBERS), 95)),
            ("Answer", answer),
            ("Inputs", fmt(input_rows(inp))),
            ("Results", fmt(result_rows(res))),
        ])
        pdf.savefig(page1)

        fig = Figure(figsize=(11.69, 8.27), layout="constrained")
        draw_dashboard(fig, inp, res, LIGHT)
        pdf.savefig(fig)

        cases = run_all()
        lines = []
        for ln in format_report(cases).splitlines():
            lines.extend(textwrap.wrap(ln, 100, subsequent_indent="    ") or [""])
        pdf.savefig(_text_page("Validation test cases", [("Results", lines)]))
