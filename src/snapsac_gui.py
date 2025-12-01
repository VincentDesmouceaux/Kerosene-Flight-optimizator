# snapsac_gui.py
# UI "Neon Dark" : 3 graphes empilés (verticaux), KPIs à droite, palette néon
# Version "fast & smooth" :
# - Vent 0→300 par pas de 5 km/h (détails fins)
# - 1 frame = 1 point (pas de SUBSTEPS ni interpolation)
# - Marqueur glow collé sur la courbe (plus de séparation point/ligne)

from matplotlib.collections import PolyCollection
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
from matplotlib.figure import Figure
import numpy as np
import os
import math
import tkinter as tk
from tkinter import ttk
import traceback

# Matplotlib backend Tk
import matplotlib
matplotlib.use("TkAgg")

# ====== Build canari (pour vérifier que c’est bien cette version) ======
APP_BUILD = os.getenv("BUILD_ID", "dev")

# ====== Réglages animation ======
DEBUG = os.getenv("DEBUG", "0") == "1"
LOG_EVERY = max(1, int(os.getenv("LOG_EVERY", "10")))

# Plus de détails = pas de 5 km/h
VENT_STEPS = list(range(0, 301, 5))     # 0,5,10,...,300
SUBSTEPS = 1                            # 1 frame = 1 point
INTERVAL_MS = int(os.getenv("INTERVAL_MS", "30"))  # ~30 ms → ~1,8s le sweep
EASING = "linear"                       # plus utile ici, mais on garde le switch


def log(msg: str):
    if DEBUG:
        print(msg, flush=True)


# ====== Données métier ======
AVIONS = {
    "A320": {"poids_vide": 42000,  "conso_base": 2.4, "max_pax": 180, "sens_vent": 1.0, "vitesse": 840},
    "B737": {"poids_vide": 41413,  "conso_base": 2.6, "max_pax": 190, "sens_vent": 1.1, "vitesse": 842},
    "B777": {"poids_vide": 134800, "conso_base": 5.0, "max_pax": 396, "sens_vent": 1.3, "vitesse": 905},
    "A380": {"poids_vide": 277000, "conso_base": 8.0, "max_pax": 850, "sens_vent": 1.5, "vitesse": 945},
}
POIDS_PASSAGER = 80
POIDS_BAGAGE = 23
DIRECTIONS = ["head", "tail", "side"]
DISTANCES = [800, 1200, 1600, 2000]
PAX_LIST = [140, 160, 180, 200, 220, 240]

# ====== Thème sombre & néon ======
BG = "#0f1221"   # fond fenêtre
PANEL = "#14172a"   # fond panneaux
FG = "#E8EAF6"   # texte principal
MUTED = "#AAB1C6"
ACC = "#3FD0C9"   # accent

PALETTE = {
    "A320": "#11D6A3",  # menthe
    "B737": "#FF6B35",  # orange vif
    "B777": "#8E7CFF",  # violet néon
    "A380": "#FFC857",  # jaune miel
}

# ====== Métier ======


def calcule_etat(avion_key, direction, vent, pax, distance):
    specs = AVIONS[avion_key]
    if pax > specs["max_pax"]:
        return None
    masse = specs["poids_vide"] + pax * (POIDS_PASSAGER + POIDS_BAGAGE)
    if direction == "head":
        coef = vent * 0.005 * specs["sens_vent"]
        vitesse = specs["vitesse"] - vent
    elif direction == "tail":
        coef = vent * -0.003 * specs["sens_vent"]
        vitesse = specs["vitesse"] + vent
    else:
        coef = vent * 0.001 * specs["sens_vent"]
        vitesse = specs["vitesse"]
    vitesse = max(600, min(1000, vitesse))
    conso_km = specs["conso_base"] + (masse / 1000.0) * 0.1 + coef
    conso_L = conso_km * distance
    return {
        "conso_L": conso_L,
        "conso_L_pax": conso_L / pax,
        "duree_h": distance / vitesse,
        "vitesse": vitesse
    }


def ymax_sequence(direction, distance, pax, metric):
    y_max = 0.0
    # ici on peut garder un pas plus gros pour le bound
    for v in range(0, 301, 20):
        for avion in AVIONS:
            e = calcule_etat(avion, direction, v, pax, distance)
            if e:
                y_max = max(y_max, e[metric])
    return (y_max * 1.20) if y_max > 0 else 1.0


def sequence_generator():
    while True:
        for d in DIRECTIONS:
            for dist in DISTANCES:
                for pax in PAX_LIST:
                    yield {"direction": d, "distance": dist, "pax": pax}

# ====== Easing ======


def ease_in_out(t):   # cosinus (accélère puis décélère)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def ease_t(t):
    if EASING == "ease_in_out":
        return ease_in_out(t)
    return t  # ici t=0 tout le temps, mais on garde la fonction pour compat


# ====== Style matplotlib ======


def set_axis_style(ax, title, ylabel):
    ax.set_facecolor(PANEL)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10, color=FG)
    ax.set_xlabel("Vent (km/h)", fontsize=11, color=MUTED)
    ax.set_ylabel(ylabel,       fontsize=11, color=MUTED)
    ax.grid(True, alpha=0.28, linestyle=":", linewidth=0.9, color="#4C5277")
    ax.tick_params(colors="#CAD0EA", labelsize=9)
    for sp in ax.spines.values():
        sp.set_color("#2a2f4a")
        sp.set_linewidth(1.0)


def add_glow_marker(ax, color):
    outer = ax.scatter([], [], s=160, color=color,
                       alpha=0.22, zorder=6, edgecolor="none")
    inner = ax.scatter([], [], s=58,  color=color, alpha=0.98,
                       zorder=7, edgecolor="#FFFFFF", linewidths=1.0)
    return outer, inner

# ====== Sidebar: lignes KPI (GRID ONLY) ======


def kpi_row(parent, row, label, init_value="—"):
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_columnconfigure(1, weight=1)

    lab = ttk.Label(parent, text=label, style="Muted.TLabel",
                    font=("Helvetica", 10))
    val = ttk.Label(parent, text=init_value, style="Panel.TLabel",
                    font=("Helvetica", 11, "bold"))

    lab.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=2)
    val.grid(row=row, column=1, sticky="e", padx=(8, 0), pady=2)
    return val

# ====== App ======


class App:
    METRICS = ("conso_L", "conso_L_pax", "duree_h")
    TITLES = {
        "conso_L":     "Consommation totale (L) vs Vent",
        "conso_L_pax": "Consommation par passager (L/pax) vs Vent",
        "duree_h":     "Durée estimée (h) vs Vent",
    }
    YLABS = {"conso_L": "Litres", "conso_L_pax": "L/pax", "duree_h": "Heures"}

    def __init__(self, root):
        self.root = root
        self.root.title(
            f"Kerosene Flight Optimizator — Live  [BUILD {APP_BUILD}]"
        )
        self.root.configure(bg=BG)
        self.root.geometry("1480x980")

        # ttk theme
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Panel.TLabel", background=PANEL, foreground=FG)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Title.TLabel", background=BG,
                        foreground=FG, font=("Helvetica", 16, "bold"))
        style.configure("Neon.Horizontal.TProgressbar",
                        troughcolor="#0b0e1a", background=ACC)

        # Layout principal
        self.main = ttk.Frame(self.root, style="TFrame", padding=12)
        self.main.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        self.main.columnconfigure(0, weight=5)   # graphes
        self.main.columnconfigure(1, weight=2)   # KPIs

        # ----- Colonne gauche (graphes) -----
        left = ttk.Frame(self.main, style="TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        ttk.Label(
            left,
            text="Simulation — Construction progressive des courbes",
            style="Title.TLabel"
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Figure 3x1 empilée
        self.fig = Figure(figsize=(10.8, 8.6), dpi=100, facecolor=BG)
        self.ax_conso = self.fig.add_subplot(3, 1, 1)
        self.ax_cpx = self.fig.add_subplot(3, 1, 2)
        self.ax_duree = self.fig.add_subplot(3, 1, 3)
        self.axes = {
            "conso_L": self.ax_conso,
            "conso_L_pax": self.ax_cpx,
            "duree_h": self.ax_duree,
        }
        for metric, ax in self.axes.items():
            set_axis_style(ax, self.TITLES[metric], self.YLABS[metric])
            ax.set_xlim(0, 300)

        # Séries & objets animés
        self.series = {m: {} for m in self.METRICS}
        self.fill_best: dict[str, PolyCollection | None] = {
            m: None for m in self.METRICS}
        self.wind_lines = {}
        self.best_text = {}

        for metric, ax in self.axes.items():
            self.wind_lines[metric] = ax.axvline(
                0, color="#7480b8", lw=1.6, ls="--", alpha=0.8, zorder=4)
            self.best_text[metric] = ax.text(
                0.985, 0.06, "Best: —", transform=ax.transAxes,
                ha="right", va="bottom", fontsize=10, color="#C9CEEC"
            )
            for avion, color in PALETTE.items():
                shadow, = ax.plot(
                    [], [], lw=6.0, color="#000000",
                    alpha=0.22, solid_capstyle="round", zorder=1
                )
                line,   = ax.plot(
                    [], [], lw=3.4, color=color, alpha=0.98,
                    solid_capstyle="round", zorder=3, label=avion
                )
                g_outer, g_inner = add_glow_marker(ax, color)
                self.series[metric][avion] = {
                    "x": [], "y": [], "line": line,
                    "shadow": shadow, "glow": (g_outer, g_inner)
                }
            leg = ax.legend(loc="upper left", frameon=False, fontsize=9)
            for txt in leg.get_texts():
                txt.set_color("#D9DEF9")

        self.canvas = FigureCanvasTkAgg(self.fig, master=left)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        self.prog = ttk.Progressbar(
            left,
            mode="determinate",
            style="Neon.Horizontal.TProgressbar",
            maximum=len(VENT_STEPS) * SUBSTEPS
        )
        self.prog.grid(row=2, column=0, sticky="ew", pady=(8, 0))

        # ----- Colonne droite (KPIs) -----
        right = ttk.Frame(self.main, style="Panel.TFrame", padding=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=1)

        ttk.Label(
            right, text="STATUT SIMULATION", style="Panel.TLabel",
            font=("Helvetica", 12, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        self.tag_dir = ttk.Label(
            right, text="Direction: —", style="Muted.TLabel")
        self.tag_dist = ttk.Label(
            right, text="Distance : —", style="Muted.TLabel")
        self.tag_pax = ttk.Label(
            right, text="Passagers: —", style="Muted.TLabel")
        self.tag_dir.grid(row=1, column=0, columnspan=2, sticky="w")
        self.tag_dist.grid(row=2, column=0, columnspan=2, sticky="w")
        self.tag_pax.grid(row=3, column=0, columnspan=2, sticky="w")

        ttk.Separator(right, orient="horizontal").grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=8
        )

        ttk.Label(
            right, text="MEILLEUR (L/pax)", style="Panel.TLabel",
            font=("Helvetica", 12, "bold")
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 4))

        self.kpi_model = kpi_row(
            right, row=6,  label="Modèle",         init_value="—")
        self.kpi_cpx = kpi_row(
            right, row=7,  label="L / pax",        init_value="—")
        self.kpi_conso = kpi_row(
            right, row=8,  label="Conso (L)",      init_value="—")
        self.kpi_duree = kpi_row(
            right, row=9,  label="Durée (h)",      init_value="—")
        self.kpi_vit = kpi_row(
            right, row=10, label="Vitesse (km/h)", init_value="—")

        ttk.Separator(right, orient="horizontal").grid(
            row=11, column=0, columnspan=2, sticky="ew", pady=8
        )
        ttk.Label(right, text="BUILD", style="Muted.TLabel").grid(
            row=12, column=0, sticky="w")
        ttk.Label(right, text=f"{APP_BUILD}", style="Muted.TLabel").grid(
            row=12, column=1, sticky="e")

        # État & séquences
        self.seq_gen = sequence_generator()
        self.current_seq = next(self.seq_gen)
        self.step_index = 0
        self._reset_sequence(self.current_seq)

        total_frames = len(VENT_STEPS) * SUBSTEPS
        self.anim = FuncAnimation(
            self.fig, self._update, frames=total_frames,
            interval=INTERVAL_MS, blit=False,
            cache_frame_data=False, save_count=total_frames
        )
        log("[GUI] animation initialisée — Neon Dark (fast, pas=5, no-substeps)")

    # ----- helpers -----
    def _reset_sequence(self, seq):
        self.direction = seq["direction"]
        self.distance = seq["distance"]
        self.pax = seq["pax"]
        self.tag_dir.config(text=f"Direction: {self.direction}")
        self.tag_dist.config(text=f"Distance : {self.distance} km")
        self.tag_pax.config(text=f"Passagers: {self.pax}")

        for metric, ax in self.axes.items():
            for avion, s in self.series[metric].items():
                s["x"].clear()
                s["y"].clear()
                s["line"].set_data([], [])
                s["shadow"].set_data([], [])
                outer, inner = s["glow"]
                outer.set_offsets([[np.nan, np.nan]])
                inner.set_offsets([[np.nan, np.nan]])
                outer.set_alpha(0.0)
                inner.set_alpha(0.0)

            ymax = ymax_sequence(
                self.direction, self.distance, self.pax, metric)
            ax.set_ylim(0, ymax)
            ax.set_title(
                f"{self.TITLES[metric]} — {self.direction} | {self.distance} km | {self.pax} pax",
                fontsize=13, fontweight="bold", color=FG, pad=10
            )
            self.wind_lines[metric].set_xdata([0, 0])
            self.best_text[metric].set_text("Best: —")

            fb = self.fill_best[metric]
            if isinstance(fb, PolyCollection):
                try:
                    fb.remove()
                except Exception:
                    pass
            self.fill_best[metric] = None

        self.fig.patch.set_facecolor(BG)
        self.fig.suptitle(
            f"Kerosene Flight Optimizator — {self.direction} | {self.distance} km | {self.pax} pax",
            fontsize=15, fontweight="bold", color=FG
        )
        self.canvas.draw()
        self.step_index = 0
        self.prog["value"] = 0

        # reset KPI
        self.kpi_model.config(text="—")
        self.kpi_cpx.config(text="—")
        self.kpi_conso.config(text="—")
        self.kpi_duree.config(text="—")
        self.kpi_vit.config(text="—")

    def _etat(self, avion, vent):
        return calcule_etat(avion, self.direction, vent, self.pax, self.distance)

    # ----- animation -----
    def _update(self, frame_id):
        try:
            self.step_index = frame_id  # 1 frame = 1 vent step
            if self.step_index >= len(VENT_STEPS):
                return []

            v_cur = VENT_STEPS[self.step_index]

            if (frame_id % LOG_EVERY) == 0:
                log(f"[GUI] frame={frame_id} | vent={v_cur} km/h")

            best_model, best_state, best_cpx = None, None, float("inf")

            # Ajout d'un nouveau point pour chaque avion
            for avion in AVIONS:
                e = self._etat(avion, v_cur)
                if not e:
                    continue

                # update séries
                for metric in self.METRICS:
                    s = self.series[metric][avion]
                    s["x"].append(v_cur)
                    s["y"].append(e[metric])
                    s["line"].set_data(s["x"], s["y"])
                    s["shadow"].set_data(s["x"], s["y"])

                # meilleur L/pax au vent courant
                cpx_cur = e["conso_L_pax"]
                if cpx_cur < best_cpx:
                    best_cpx = cpx_cur
                    best_model = avion
                    best_state = e

            # styliser gagnant, ligne de vent, remplissage & glow
            for metric, ax in self.axes.items():
                for avion, s in self.series[metric].items():
                    is_best = (avion == best_model)
                    s["line"].set_linewidth(3.8 if is_best else 2.4)
                    s["line"].set_alpha(1.0 if is_best else 0.70)
                    s["shadow"].set_alpha(0.30 if is_best else 0.14)

                self.wind_lines[metric].set_xdata([v_cur, v_cur])

                # remplissage sous la meilleure courbe — x déjà croissants
                if best_model:
                    bx = self.series[metric][best_model]["x"]
                    by = self.series[metric][best_model]["y"]
                    if len(bx) >= 2:
                        bx_np = np.asarray(bx, dtype=float)
                        by_np = np.asarray(by, dtype=float)

                        fb = self.fill_best[metric]
                        if isinstance(fb, PolyCollection):
                            try:
                                fb.remove()
                            except Exception:
                                pass
                        self.fill_best[metric] = ax.fill_between(
                            bx_np, by_np, step="pre",
                            color=PALETTE[best_model], alpha=0.10, zorder=0
                        )

                self.best_text[metric].set_text(
                    f"Best: {best_model if best_model else '—'}")

                # glow marker collé sur la courbe (pas de décalage)
                if best_model:
                    bx = self.series[metric][best_model]["x"]
                    by = self.series[metric][best_model]["y"]
                    if len(bx) > 0:
                        x_last = bx[-1]
                        y_last = by[-1]
                        outer, inner = self.series[metric][best_model]["glow"]
                        outer.set_offsets([[x_last, y_last]])
                        inner.set_offsets([[x_last, y_last]])
                        outer.set_alpha(0.28)
                        inner.set_alpha(1.0)

            # KPIs
            if best_model and best_state:
                self.kpi_model.config(text=best_model)
                self.kpi_cpx.config(text=f"{best_state['conso_L_pax']:.1f}")
                self.kpi_conso.config(
                    text=f"{best_state['conso_L']:,.0f}".replace(",", " "))
                self.kpi_duree.config(text=f"{best_state['duree_h']:.2f}")
                self.kpi_vit.config(text=f"{best_state['vitesse']:.0f}")

            self.fig.suptitle(
                f"Vent {v_cur:3.0f} km/h   |   {self.direction}   "
                f"|   {self.distance} km   |   {self.pax} pax",
                fontsize=14, fontweight="bold", color=FG
            )

            self.prog["value"] = frame_id + 1

            total_frames = len(VENT_STEPS) * SUBSTEPS
            if frame_id == total_frames - 1:
                self.current_seq = next(self.seq_gen)
                self._reset_sequence(self.current_seq)

            self.canvas.draw_idle()
            return []
        except Exception:
            traceback.print_exc()
            log("[GUI] ERROR in _update")
            return []


# ====== main ======
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
