"""Matplotlib dashboard, shared by the GUI (live redraw) and the PDF report."""
from __future__ import annotations

import numpy as np
from matplotlib.patches import Patch

from .model import SOURCES, SOURCE_LABELS, Inputs, Results, coal_curve

SOURCE_COLORS = {
    "coal": "#6b7280", "gas": "#f59e0b", "hydro": "#38bdf8",
    "nuclear": "#a78bfa", "solar": "#facc15", "wind": "#34d399",
}

DARK = dict(bg="#0b1220", panel="#111a2e", text="#e5e7eb", muted="#94a3b8", grid="#1f2a44",
            ev="#34d399", petrol="#f59e0b", bad="#ef4444", accent="#38bdf8")
LIGHT = dict(bg="#ffffff", panel="#f8fafc", text="#0f172a", muted="#475569", grid="#e2e8f0",
             ev="#0d9488", petrol="#d97706", bad="#dc2626", accent="#0284c7")


def _style(ax, th, title):
    ax.set_facecolor(th["panel"])
    ax.set_title(title, color=th["text"], fontsize=10, fontweight="bold", loc="left")
    for sp in ax.spines.values():
        sp.set_color(th["grid"])
    ax.tick_params(colors=th["muted"], labelsize=8)
    ax.xaxis.label.set_color(th["muted"])
    ax.yaxis.label.set_color(th["muted"])


def draw_dashboard(fig, inp: Inputs, res: Results, th=DARK) -> None:
    """Redraw all four charts on `fig` (cleared first)."""
    fig.clear()
    fig.set_facecolor(th["bg"])
    gs = fig.add_gridspec(2, 6, height_ratios=[1, 1.2])
    ax_mix = fig.add_subplot(gs[0, 0:2])
    ax_bar = fig.add_subplot(gs[0, 2:4])
    ax_led = fig.add_subplot(gs[0, 4:6])
    ax_sen = fig.add_subplot(gs[1, :])

    # --- 1. generation mix donut
    _style(ax_mix, th, "Generation mix")
    nz = [s for s in SOURCES if inp.mix[s] > 0]
    ax_mix.pie([inp.mix[s] for s in nz], colors=[SOURCE_COLORS[s] for s in nz], startangle=90,
               counterclock=False, wedgeprops=dict(width=0.38, edgecolor=th["panel"], linewidth=1.5))
    ax_mix.text(0, 0, f"{res.grid_ef * 1000:.0f}\ng/kWh", ha="center", va="center",
                color=th["text"], fontsize=11, fontweight="bold")
    ax_mix.legend(handles=[Patch(color=SOURCE_COLORS[s], label=f"{SOURCE_LABELS[s]} {inp.mix[s]:.1f}%") for s in SOURCES],
                  loc="upper center", bbox_to_anchor=(0.5, 0.02), ncol=2, fontsize=7, frameon=False,
                  labelcolor=th["text"])

    # --- 2. EV vs petrol per km
    _style(ax_bar, th, "EV vs petrol (g CO\u2082/km)")
    vals = [res.ev_g_per_km, res.petrol_g_per_km]
    ax_bar.barh(["EV", "Petrol"], vals, color=[th["ev"], th["petrol"]], height=0.55)
    ax_bar.invert_yaxis()
    top = max(vals) if max(vals) > 0 else 1.0
    ax_bar.set_xlim(0, top * 1.25)
    for i, v in enumerate(vals):
        ax_bar.text(v + top * 0.02, i, f"{v:.1f}", va="center", color=th["text"], fontsize=9, fontweight="bold")
    ax_bar.grid(axis="x", color=th["grid"], lw=0.6)
    ax_bar.set_axisbelow(True)

    # --- 3. annual impact ledger
    _style(ax_led, th, "Annual CO\u2082 at current daily distance (kg)")
    ann = [res.ev_kg_per_year, res.petrol_kg_per_year]
    ax_led.bar(["EV", "Petrol"], ann, color=[th["ev"], th["petrol"]], width=0.55)
    atop = max(ann) if max(ann) > 0 else 1.0
    ax_led.set_ylim(0, atop * 1.3)
    for i, v in enumerate(ann):
        ax_led.text(i, v + atop * 0.02, f"{v:,.0f}", ha="center", color=th["text"], fontsize=9, fontweight="bold")
    sign = "saves" if res.saving_kg_per_day >= 0 else "adds"
    ax_led.text(0.5, 0.97, f"EV {sign} {abs(res.saving_kg_per_day):.2f} kg/day  |  {abs(res.saving_kg_per_year):,.0f} kg/yr",
                transform=ax_led.transAxes, ha="center", va="top", color=th["muted"], fontsize=8)
    ax_led.grid(axis="y", color=th["grid"], lw=0.6)
    ax_led.set_axisbelow(True)

    # --- 4. Graph 1: coal share vs CO2 per km
    _style(ax_sen, th, "Graph 1 \u2013 Coal share vs. operational CO\u2082 per km (gas fixed, coal replaces clean sources)")
    xs, ys = coal_curve(inp)
    xs, ys = np.array(xs), np.array(ys)
    pet = res.petrol_g_per_km
    ax_sen.plot(xs, ys, color=th["ev"], lw=2.2, label="EV (including losses)")
    ax_sen.axhline(pet, color=th["petrol"], lw=2.0, label="Petrol car")
    ax_sen.fill_between(xs, ys, pet, where=ys > pet, interpolate=True, color=th["bad"], alpha=0.15,
                        label="EV dirtier than petrol")
    ax_sen.scatter([res.current_coal_pct], [res.ev_g_per_km], color=th["accent"], zorder=5, s=40)
    ax_sen.annotate(f"Current mix: {res.current_coal_pct:.0f}% coal\n{res.ev_g_per_km:.1f} g/km",
                    (res.current_coal_pct, res.ev_g_per_km), xytext=(10, -30), textcoords="offset points",
                    color=th["text"], fontsize=8)
    if res.breakeven_status == "value":
        be = res.breakeven_coal_pct
        ax_sen.axvline(be, color=th["muted"], ls=":", lw=1.3)
        ax_sen.scatter([be], [pet], color=th["text"], zorder=6, s=45)
        ax_sen.annotate(f"Break-even: {be:.1f}%", (be, pet), xytext=(6, -22), textcoords="offset points",
                        color=th["text"], fontsize=9, fontweight="bold")
    elif res.breakeven_status == "never":
        ax_sen.text(0.5, 0.06, "No break-even: EV stays cleaner than petrol at every coal share",
                    transform=ax_sen.transAxes, ha="center", color=th["muted"], fontsize=9)
    else:
        ax_sen.text(0.5, 0.06, "EV is already dirtier than petrol at 0 % coal",
                    transform=ax_sen.transAxes, ha="center", color=th["muted"], fontsize=9)
    ax_sen.set_xlim(0, max(res.max_coal_pct, 1.0))
    ax_sen.set_ylim(0, max(float(ys.max()), pet) * 1.12 or 1.0)
    ax_sen.set_xlabel("Coal share in electricity mix (%)")
    ax_sen.set_ylabel("CO\u2082 (g/km)")
    ax_sen.grid(color=th["grid"], lw=0.6)
    ax_sen.set_axisbelow(True)
    leg = ax_sen.legend(loc="upper left", fontsize=8, frameon=False)
    for t in leg.get_texts():
        t.set_color(th["text"])
