"""Interactive Tkinter GUI. Every slider / entry change recomputes and redraws all graphs instantly."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from . import TEAM_MEMBERS, TEAM_NAME, __version__
from .model import (DEFAULT_EF, M2_PER_KWP, PRESET_MIXES, REFERENCE_MIX, SOURCE_LABELS, SOURCES,
                    Inputs, compute, rebalance, summary_sentence)
from .plots import DARK, SOURCE_COLORS, draw_dashboard
from .report import export_csv, export_pdf
from .validation import run_all

BG, PANEL, INPUT, BORDER = "#0b1220", "#111a2e", "#0b1424", "#1f2a44"
TEXT, MUTED, ACCENT, BAD, WARN = "#e5e7eb", "#94a3b8", "#34d399", "#ef4444", "#f59e0b"
FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
FONT_S = ("Segoe UI", 8)

# name -> (label, min, max, step, default, unit, decimals)
PARAMS = {
    "ev_wh_per_km": ("EV consumption (at battery)", 50, 400, 1, 150, "Wh/km", 0),
    "petrol_km_per_l": ("Petrol vehicle mileage", 3, 40, 0.5, 15, "km/L", 1),
    "petrol_kg_co2_per_l": ("Petrol CO\u2082 per litre", 2.0, 2.8, 0.01, 2.31, "kg/L", 2),
    "daily_km": ("Daily distance", 0, 300, 1, 40, "km", 0),
    "grid_loss_pct": ("Transmission & distribution losses", 0, 40, 0.5, 18, "%", 1),
    "charger_eff_pct": ("Charger efficiency", 50, 100, 0.5, 90, "%", 1),
    "solar_kwh_per_kwp_day": ("Solar generation per kWp", 2, 7, 0.1, 4, "kWh/kWp/day", 1),
}


class SliderRow(tk.Frame):
    """Label + live value entry + slider. `on_user(value)` fires on user changes only."""

    def __init__(self, master, label, lo, hi, step, value, unit="", on_user=None, decimals=1, dot=None):
        super().__init__(master, bg=PANEL)
        self.lo, self.hi, self.decimals, self.on_user = lo, hi, decimals, on_user
        self._value = float(value)

        top = tk.Frame(self, bg=PANEL)
        top.pack(fill="x")
        if dot:
            tk.Label(top, text="\u25cf", fg=dot, bg=PANEL, font=FONT).pack(side="left")
        tk.Label(top, text=label, fg=TEXT, bg=PANEL, font=FONT).pack(side="left", padx=(3, 0))
        self.entry_var = tk.StringVar()
        entry = tk.Entry(top, textvariable=self.entry_var, width=7, justify="right", bg=INPUT, fg=TEXT,
                         insertbackground=TEXT, relief="flat", highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=ACCENT, font=FONT)
        entry.pack(side="right")
        tk.Label(top, text=unit, fg=MUTED, bg=PANEL, font=FONT_S).pack(side="right", padx=(0, 4))
        entry.bind("<Return>", self._commit)
        entry.bind("<FocusOut>", self._commit)

        self.scale = tk.Scale(self, from_=lo, to=hi, resolution=step, orient="horizontal", showvalue=False,
                              command=self._on_scale, bg=PANEL, troughcolor=BORDER, highlightthickness=0,
                              bd=0, sliderrelief="flat", activebackground=ACCENT, length=300)
        self.scale.pack(fill="x")
        self.set(value)

    def _fmt(self, v: float) -> str:
        return f"{v:.{self.decimals}f}"

    def get(self) -> float:
        return self._value

    def set(self, v: float) -> None:
        """Programmatic update (does not call on_user)."""
        v = min(max(float(v), self.lo), self.hi)
        self._value = v
        self.scale.set(v)
        self.entry_var.set(self._fmt(v))

    def _on_scale(self, raw) -> None:
        v = float(raw)
        if abs(v - self._value) < 1e-6:          # echo of a programmatic set()
            return
        self._value = v
        self.entry_var.set(self._fmt(v))
        if self.on_user:
            self.on_user(v)

    def _commit(self, _event=None) -> None:
        try:
            v = float(self.entry_var.get().replace(",", "."))
        except ValueError:
            self.entry_var.set(self._fmt(self._value))
            return
        v = min(max(v, self.lo), self.hi)
        changed = abs(v - self._value) > 1e-9
        self.set(v)
        if changed and self.on_user:
            self.on_user(v)


class Card(tk.Frame):
    def __init__(self, master, title):
        super().__init__(master, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        tk.Label(self, text=title.upper(), fg=MUTED, bg=PANEL, font=FONT_S, anchor="w").pack(fill="x", padx=10, pady=(8, 0))
        self.value = tk.Label(self, text="-", fg=ACCENT, bg=PANEL, font=("Consolas", 20, "bold"), anchor="w")
        self.value.pack(fill="x", padx=10)
        self.sub = tk.Label(self, text="", fg=MUTED, bg=PANEL, font=FONT_S, anchor="w", justify="left")
        self.sub.pack(fill="x", padx=10, pady=(0, 8))

    def set(self, value: str, sub: str, color: str = ACCENT) -> None:
        self.value.config(text=value, fg=color)
        self.sub.config(text=sub)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EV Carbon Calculator \u2013 Team 5 | Grid mix to g CO\u2082/km")
        self.geometry("1440x860")
        self.minsize(1100, 700)
        self.configure(bg=BG)
        self._setup_style()

        self.mix = dict(REFERENCE_MIX)
        self.ef = dict(DEFAULT_EF)
        self.rows = {}
        self.mix_rows = {}
        self.ef_vars = {}
        self._pending = None
        self._last = None

        self._build_header()
        footer = tk.Label(self, text=f"{TEAM_NAME}  \u00b7  " + "  \u00b7  ".join(TEAM_MEMBERS), fg=MUTED, bg=PANEL,
                          font=FONT_S, anchor="w", padx=14, pady=4)
        footer.pack(side="bottom", fill="x")
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        self._build_left(body)
        self._build_right(body)

        self._refresh()
        self._run_validation()

    # ------------------------------------------------------------------ styling / header
    def _setup_style(self) -> None:
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(14, 6), borderwidth=0)
        st.map("TNotebook.Tab", background=[("selected", BORDER)], foreground=[("selected", TEXT)])
        st.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=28,
                     borderwidth=0, font=FONT)
        st.configure("Treeview.Heading", background=BORDER, foreground=TEXT, font=FONT_B, borderwidth=0)
        st.configure("TCombobox", fieldbackground=INPUT, background=BORDER, foreground=TEXT, arrowcolor=TEXT)
        st.configure("Vertical.TScrollbar", background=BORDER, troughcolor=BG, borderwidth=0, arrowcolor=MUTED)

    def _btn(self, parent, text, cmd, primary=False):
        return tk.Button(parent, text=text, command=cmd, relief="flat", cursor="hand2", font=FONT_B,
                         bg=ACCENT if primary else BORDER, fg="#04130d" if primary else TEXT,
                         activebackground=TEXT, padx=12, pady=5, bd=0)

    def _build_header(self) -> None:
        bar = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        bar.pack(fill="x")
        tk.Label(bar, text="\u26a1 EV Carbon Calculator", fg=TEXT, bg=PANEL, font=("Segoe UI", 15, "bold")
                 ).pack(side="left", padx=14, pady=8)
        tk.Label(bar, text=f"TEAM 05 \u00b7 GRID MIX \u2192 g CO\u2082/km \u00b7 v{__version__}", fg=MUTED, bg=PANEL,
                 font=FONT_S).pack(side="left")
        self._btn(bar, "PDF report", self._export_pdf, primary=True).pack(side="right", padx=(4, 14), pady=8)
        self._btn(bar, "Export CSV", self._export_csv).pack(side="right", padx=4, pady=8)
        self._btn(bar, "Reset", self._reset).pack(side="right", padx=4, pady=8)
        self.status = tk.Label(bar, text="\u25cf MODEL LIVE", fg=ACCENT, bg=PANEL, font=FONT_B)
        self.status.pack(side="right", padx=14)

    # ------------------------------------------------------------------ left panel (inputs)
    def _build_left(self, parent) -> None:
        wrap = tk.Frame(parent, bg=BG, width=430)
        wrap.pack(side="left", fill="y")
        wrap.pack_propagate(False)
        canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG)
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

        def wheel(e):
            x0 = canvas.winfo_rootx()
            if not (x0 <= e.x_root <= x0 + canvas.winfo_width()):
                return
            step = -1 if (getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4) else 1
            canvas.yview_scroll(step, "units")

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, wheel)

        # 01 mix
        sec = self._section(inner, "01  Electricity generation mix")
        for s in SOURCES:
            row = SliderRow(sec, SOURCE_LABELS[s], 0, 100, 0.1, self.mix[s], "%",
                            on_user=lambda v, s=s: self._mix_changed(s, v), decimals=1, dot=SOURCE_COLORS[s])
            row.pack(fill="x", pady=3)
            self.mix_rows[s] = row
        self.total_lbl = tk.Label(sec, text="", fg=ACCENT, bg=PANEL, font=FONT_B, anchor="w")
        self.total_lbl.pack(fill="x", pady=(6, 0))
        tk.Label(sec, text="Moving one slider rescales the others so the total stays 100 %.", fg=MUTED,
                 bg=PANEL, font=FONT_S, anchor="w").pack(fill="x")
        preset_row = tk.Frame(sec, bg=PANEL)
        preset_row.pack(fill="x", pady=(8, 0))
        tk.Label(preset_row, text="Preset:", fg=MUTED, bg=PANEL, font=FONT).pack(side="left")
        self.preset = ttk.Combobox(preset_row, values=list(PRESET_MIXES), state="readonly", width=26)
        self.preset.pack(side="left", padx=6)
        self.preset.bind("<<ComboboxSelected>>", self._preset_selected)

        # 02 vehicle & charging
        sec = self._section(inner, "02  Vehicle, usage & charging")
        for name, (label, lo, hi, step, default, unit, dec) in PARAMS.items():
            row = SliderRow(sec, label, lo, hi, step, default, unit, on_user=lambda v: self._schedule(), decimals=dec)
            row.pack(fill="x", pady=3)
            self.rows[name] = row

        # 03 emission-factor library
        sec = self._section(inner, "03  Emission factors (kg CO\u2082/kWh, editable)")
        grid = tk.Frame(sec, bg=PANEL)
        grid.pack(fill="x")
        for i, s in enumerate(SOURCES):
            cell = tk.Frame(grid, bg=PANEL)
            cell.grid(row=i // 3, column=i % 3, padx=4, pady=4, sticky="w")
            tk.Label(cell, text=SOURCE_LABELS[s], fg=MUTED, bg=PANEL, font=FONT_S).pack(anchor="w")
            var = tk.StringVar(value=f"{self.ef[s]:.3f}")
            e = tk.Entry(cell, textvariable=var, width=9, justify="right", bg=INPUT, fg=TEXT, insertbackground=TEXT,
                         relief="flat", highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT, font=FONT)
            e.pack()
            e.bind("<Return>", lambda ev, s=s: self._ef_commit(s))
            e.bind("<FocusOut>", lambda ev, s=s: self._ef_commit(s))
            self.ef_vars[s] = var
        self._update_total()

    def _section(self, parent, title):
        tk.Label(parent, text=title, fg=TEXT, bg=BG, font=("Segoe UI", 11, "bold"), anchor="w"
                 ).pack(fill="x", padx=12, pady=(14, 4))
        box = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="x", padx=10)
        inner = tk.Frame(box, bg=PANEL)
        inner.pack(fill="x", padx=12, pady=10)
        return inner

    # ------------------------------------------------------------------ right panel (outputs)
    def _build_right(self, parent) -> None:
        right = tk.Frame(parent, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        dash = tk.Frame(nb, bg=BG)
        val = tk.Frame(nb, bg=BG)
        info = tk.Frame(nb, bg=BG)
        nb.add(dash, text="  Dashboard  ")
        nb.add(val, text="  Validation tests  ")
        nb.add(info, text="  Formulas  ")

        # dashboard: KPI cards
        cards = tk.Frame(dash, bg=BG)
        cards.pack(fill="x", pady=(4, 6))
        titles = [("grid_ef", "Grid emission factor"), ("gen", "Electricity generated / km"),
                  ("ev", "EV CO\u2082 per km"), ("petrol", "Petrol CO\u2082 per km"),
                  ("saving", "EV vs petrol"), ("be", "Break-even coal share"),
                  ("plug", "Daily charging energy"), ("solar", "Rooftop solar size")]
        self.cards = {}
        for i, (key, title) in enumerate(titles):
            c = Card(cards, title)
            c.grid(row=i // 4, column=i % 4, sticky="nsew", padx=4, pady=4)
            self.cards[key] = c
        for col in range(4):
            cards.grid_columnconfigure(col, weight=1, uniform="cards")

        self.answer = tk.Label(dash, text="", fg=TEXT, bg=PANEL, font=("Segoe UI", 11), justify="left", anchor="w",
                               wraplength=900, padx=12, pady=8, highlightthickness=1, highlightbackground=BORDER)
        self.answer.pack(fill="x", padx=4, pady=(0, 6))
        dash.bind("<Configure>", lambda e: self.answer.config(wraplength=max(300, e.width - 40)))

        self.fig = Figure(figsize=(9, 6), dpi=100, layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.fig, master=dash)
        self.canvas.get_tk_widget().configure(bg=BG, highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # validation tab
        top = tk.Frame(val, bg=BG)
        top.pack(fill="x", pady=8, padx=4)
        self._btn(top, "Run all tests", self._run_validation, primary=True).pack(side="left")
        self.val_summary = tk.Label(top, text="", fg=TEXT, bg=BG, font=FONT_B)
        self.val_summary.pack(side="left", padx=12)
        cols = ("n", "case", "expected", "actual", "status")
        self.tree = ttk.Treeview(val, columns=cols, show="headings", selectmode="none")
        for col, text, width in (("n", "#", 40), ("case", "Case", 200), ("expected", "Expected (manual)", 300),
                                 ("actual", "Program result", 300), ("status", "Status", 80)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor="w", stretch=col in ("expected", "actual"))
        self.tree.tag_configure("pass", foreground=ACCENT)
        self.tree.tag_configure("fail", foreground=BAD)
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)

        # formulas tab
        txt = tk.Text(info, bg=PANEL, fg=TEXT, relief="flat", font=("Consolas", 11), wrap="word", padx=16, pady=12)
        txt.insert("1.0", FORMULAS)
        txt.config(state="disabled")
        txt.pack(fill="both", expand=True, padx=4, pady=8)

    # ------------------------------------------------------------------ callbacks
    def _mix_changed(self, source: str, value: float) -> None:
        self.mix = rebalance(self.mix, source, value)
        for s, row in self.mix_rows.items():
            row.set(self.mix[s])
        self._update_total()
        self._schedule()

    def _update_total(self) -> None:
        total = sum(self.mix.values())
        ok = abs(total - 100) < 0.05
        mark = "\u2713" if ok else "\u26a0"
        note = "  (constraint satisfied)" if ok else ""
        self.total_lbl.config(text=f"{mark}  Total {total:.1f} %{note}", fg=ACCENT if ok else BAD)

    def _preset_selected(self, _event=None) -> None:
        self._set_mix(PRESET_MIXES[self.preset.get()])

    def _set_mix(self, mix) -> None:
        self.mix = dict(mix)
        for s, row in self.mix_rows.items():
            row.set(self.mix[s])
        self._update_total()
        self._schedule()

    def _ef_commit(self, s: str) -> None:
        try:
            v = float(self.ef_vars[s].get().replace(",", "."))
            if v < 0:
                raise ValueError
            self.ef[s] = v
        except ValueError:
            pass
        self.ef_vars[s].set(f"{self.ef[s]:.3f}")
        self._schedule()

    def _reset(self) -> None:
        self.ef = dict(DEFAULT_EF)
        for s, var in self.ef_vars.items():
            var.set(f"{self.ef[s]:.3f}")
        for name, row in self.rows.items():
            row.set(PARAMS[name][4])
        self.preset.set("")
        self._set_mix(REFERENCE_MIX)

    def _schedule(self) -> None:
        """Coalesce rapid slider events into one redraw."""
        if self._pending is None:
            self._pending = self.after(30, self._refresh)

    def _read_inputs(self) -> Inputs:
        r = self.rows
        return Inputs(mix=dict(self.mix), ef=dict(self.ef),
                      grid_loss_pct=r["grid_loss_pct"].get(), charger_eff_pct=r["charger_eff_pct"].get(),
                      solar_kwh_per_kwp_day=r["solar_kwh_per_kwp_day"].get(), ev_wh_per_km=r["ev_wh_per_km"].get(),
                      petrol_km_per_l=r["petrol_km_per_l"].get(), petrol_kg_co2_per_l=r["petrol_kg_co2_per_l"].get(),
                      daily_km=r["daily_km"].get())

    def _refresh(self) -> None:
        self._pending = None
        inp = self._read_inputs()
        try:
            res = compute(inp)
        except ValueError as exc:
            self.status.config(text=f"\u26a0 {exc}", fg=BAD)
            return
        self.status.config(text="\u25cf MODEL LIVE", fg=ACCENT)
        self._last = (inp, res)

        good = res.ev_is_cleaner
        c = self.cards
        c["grid_ef"].set(f"{res.grid_ef:.3f}", f"kg CO\u2082/kWh  ({res.grid_ef * 1000:.0f} g/kWh) \u2192 feeds Project 2")
        c["gen"].set(f"{res.generated_wh_per_km:.1f}", "Wh/km after charger & grid losses")
        c["ev"].set(f"{res.ev_g_per_km:.1f}", "g CO\u2082/km (EV, incl. losses)", ACCENT if good else BAD)
        c["petrol"].set(f"{res.petrol_g_per_km:.1f}", "g CO\u2082/km (petrol tailpipe)", WARN)
        if res.reduction_pct >= 0:
            c["saving"].set(f"{res.ev_vs_petrol_pct:.1f}%", f"of petrol \u2192 EV saves {res.reduction_pct:.1f}%")
        else:
            c["saving"].set(f"{res.ev_vs_petrol_pct:.1f}%", f"of petrol \u2192 EV emits {-res.reduction_pct:.1f}% MORE", BAD)
        if res.breakeven_status == "value":
            c["be"].set(f"{res.breakeven_coal_pct:.1f}%", "coal share where EV = petrol (gas fixed)", WARN)
        elif res.breakeven_status == "never":
            c["be"].set("never", f"EV stays cleaner even at {res.max_coal_pct:.0f}% coal", ACCENT)
        else:
            c["be"].set("already", "EV not cleaner even at 0% coal", BAD)
        c["plug"].set(f"{res.daily_plug_kwh:.2f}", "kWh/day at the plug")
        c["solar"].set(f"{res.solar_kwp:.2f}", f"kWp (\u2248 {res.solar_kwp * M2_PER_KWP:.0f} m\u00b2 roof @ {M2_PER_KWP:.0f} m\u00b2/kWp)")

        self.answer.config(text=summary_sentence(inp, res)
                           + f"\nGrid emission factor to feed into Project 2: {res.grid_ef:.4f} kg CO\u2082/kWh.")
        draw_dashboard(self.fig, inp, res, DARK)
        self.canvas.draw_idle()

    def _run_validation(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        cases = run_all()
        for i, case in enumerate(cases, 1):
            self.tree.insert("", "end", values=(i, case.name, case.expected, case.actual,
                                                "PASS" if case.passed else "FAIL"),
                             tags=("pass" if case.passed else "fail",))
        n_ok = sum(c.passed for c in cases)
        self.val_summary.config(text=f"{n_ok}/{len(cases)} validation cases passed",
                                fg=ACCENT if n_ok == len(cases) else BAD)

    # ------------------------------------------------------------------ export
    def _export_csv(self) -> None:
        if not self._last:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="ev_emissions.csv",
                                            filetypes=[("CSV file", "*.csv")])
        if path:
            try:
                export_csv(path, *self._last)
                messagebox.showinfo("Export CSV", f"Saved:\n{path}")
            except OSError as exc:
                messagebox.showerror("Export CSV", str(exc))

    def _export_pdf(self) -> None:
        if not self._last:
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile="ev_emissions_report.pdf",
                                            filetypes=[("PDF file", "*.pdf")])
        if path:
            try:
                export_pdf(path, *self._last)
                messagebox.showinfo("PDF report", f"Saved:\n{path}")
            except OSError as exc:
                messagebox.showerror("PDF report", str(exc))


FORMULAS = """\
GRID EMISSION FACTOR
  EF_grid [kg CO2/kWh] = \u03a3 ( share_i \u00d7 EF_i )

ENERGY PER KM
  Plug energy      = Wh/km at battery \u00f7 charger efficiency
  Generated energy = Plug energy \u00f7 (1 \u2212 grid T&D loss)

EMISSIONS PER KM
  EV g/km     = Generated Wh/km \u00d7 EF_grid          (Wh \u00d7 kg/kWh = g)
  Petrol g/km = (kg CO2 per litre \u00f7 km per litre) \u00d7 1000

BREAK-EVEN COAL SHARE (gas fixed, coal replaces the clean sources)
  EF_target = Petrol g/km \u00f7 Generated Wh/km
  EF(coal)  is linear in the coal share, so coal* = solve EF(coal*) = EF_target
  "never"   if even the maximum coal share (100 % \u2212 gas %) keeps the EV cleaner.

DAILY ENERGY AND SOLAR
  Daily plug energy [kWh] = Wh/km \u00d7 daily km \u00f7 1000 \u00f7 charger efficiency
  Solar size [kWp]        = Daily plug energy \u00f7 (kWh generated per kWp per day)
  Roof area (display only) \u2248 6 m\u00b2 per kWp
"""


def run() -> None:
    try:  # crisp text on high-DPI Windows screens
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()
