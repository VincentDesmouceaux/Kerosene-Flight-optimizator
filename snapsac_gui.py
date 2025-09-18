import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation

# =========================
# Données & constantes
# =========================
AVIONS = {
    "A320": {"poids_vide": 42000,  "conso_base": 2.4, "max_pax": 180, "sens_vent": 1.0, "vitesse": 840},
    "B737": {"poids_vide": 41413,  "conso_base": 2.6, "max_pax": 190, "sens_vent": 1.1, "vitesse": 842},
    "B777": {"poids_vide": 134800, "conso_base": 5.0, "max_pax": 396, "sens_vent": 1.3, "vitesse": 905},
    "A380": {"poids_vide": 277000, "conso_base": 8.0, "max_pax": 850, "sens_vent": 1.5, "vitesse": 945},
}
POIDS_PASSAGER = 80
POIDS_BAGAGE = 23
VENTS = list(range(0, 301, 10))               # 0 → 300 par 10
DIRECTIONS = ["head", "tail", "side"]
DISTANCES = [800, 1200, 1600, 2000]           # km
PAX_LIST = [140, 160, 180, 200, 220, 240]     # pax

# Couleurs par avion (cohérentes sur les 3 graphes)
COULEURS = {
    "A320": "#1f77b4",
    "B737": "#2ca02c",
    "B777": "#d62728",
    "A380": "#9467bd",
}

# Couleurs de fond par direction (repère visuel)
BG_DIR = {
    "head": (1.0, 0.93, 0.93),   # rouge très léger
    "tail": (0.93, 1.0, 0.93),   # vert très léger
    "side": (0.93, 0.95, 1.0),   # bleu très léger
}

METRICS = ("conso_L", "conso_L_pax", "duree_h")  # 3 graphes (gauche→droite)


# =========================
# Métier
# =========================
def calcule_etat(avion_key: str, direction: str, vent: int, pax: int, distance: int):
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
        "vitesse": vitesse,
    }


def ymax_sequence(direction: str, distance: int, pax: int, metric: str) -> float:
    """Calcule une borne Y stable pour une séquence (toutes vitesses de vent, tous avions) et une métrique."""
    y_max = 0.0
    for vent in VENTS:
        for avion in AVIONS:
            etat = calcule_etat(avion, direction, vent, pax, distance)
            if etat:
                y_max = max(y_max, etat[metric])
    return (y_max * 1.12) if y_max > 0 else 1.0


# =========================
# Générateur de séquences
# =========================
def sequence_generator():
    """Enchaîne les séquences (direction, distance, pax); à l'intérieur, on balaye le vent 0→300."""
    while True:
        for direction in DIRECTIONS:
            for distance in DISTANCES:
                for pax in PAX_LIST:
                    yield {"direction": direction, "distance": distance, "pax": pax}


# =========================
# App Tkinter – 3 graphes côte à côte
# =========================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Snapsac — 3 tableaux côte à côte (animés)")
        self.root.geometry("1400x650")

        # Layout principal
        self.main = ttk.Frame(root, padding=10)
        self.main.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        self.main.rowconfigure(1, weight=1)
        self.main.columnconfigure(0, weight=1)

        ttk.Label(self.main, text="Simulation dynamique – Consommation / Consommation par passager / Durée",
                  font=("Helvetica", 14, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))

        # Figure avec 1 ligne × 3 colonnes (côte à côte)
        self.fig = Figure(figsize=(13.5, 4.8), dpi=100)
        self.ax = {
            "conso_L":     self.fig.add_subplot(1, 3, 1),
            "conso_L_pax": self.fig.add_subplot(1, 3, 2),
            "duree_h":     self.fig.add_subplot(1, 3, 3),
        }

        titles = {
            "conso_L": "Conso totale (L) vs Vent",
            "conso_L_pax": "Conso par passager (L/pax) vs Vent",
            "duree_h": "Durée estimée (h) vs Vent",
        }
        ylabels = {
            "conso_L": "Litres",
            "conso_L_pax": "Litres / passager",
            "duree_h": "Heures",
        }

        # séries + annotations (étiquettes avion) + ligne du vent courant
        self.series = {m: {} for m in METRICS}
        self.labels = {m: {} for m in METRICS}
        self.wind_lines = {}

        for metric in METRICS:
            ax = self.ax[metric]
            ax.set_title(titles[metric], fontsize=11, pad=8)
            ax.set_xlabel("Vent (km/h)")
            ax.set_ylabel(ylabels[metric])
            ax.set_xlim(0, max(VENTS))
            ax.grid(True, alpha=0.25)

            # ligne verticale (vent courant)
            self.wind_lines[metric] = ax.axvline(
                0, color="#444444", lw=1.2, ls="--", alpha=0.6)

            # séries par avion + étiquette avion (texte qui suit le dernier point)
            for avion, color in COULEURS.items():
                line, = ax.plot([], [], lw=2.4, color=color,
                                label=avion, solid_capstyle="round")
                self.series[metric][avion] = {"x": [], "y": [], "line": line}
                # annotation placée et mise à jour à chaque frame
                self.labels[metric][avion] = ax.text(
                    0, 0, "", color=color, fontsize=9, ha="left", va="center", alpha=0.8
                )

            ax.legend(loc="upper left", frameon=False, fontsize=9)

        # Canvas tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.main)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")

        # Générateurs & animation
        self.seq_gen = sequence_generator()
        self.current_seq = next(self.seq_gen)
        self.vent_index = 0
        self._reset_sequence(self.current_seq)

        # Animation unique, pilote les 3 graphes
        self.anim = FuncAnimation(
            self.fig, self._update, interval=90, blit=False)

    def _apply_direction_style(self, direction: str):
        # fond par direction
        bg = BG_DIR.get(direction, (1, 1, 1))
        for metric in METRICS:
            self.ax[metric].set_facecolor(bg)

    def _reset_sequence(self, seq):
        self.direction = seq["direction"]
        self.distance = seq["distance"]
        self.pax = seq["pax"]
        self._apply_direction_style(self.direction)

        # remettre toutes les séries + étiquettes à zéro, fixer Y pour la séquence
        for metric in METRICS:
            ax = self.ax[metric]
            for avion, s in self.series[metric].items():
                s["x"].clear()
                s["y"].clear()
                s["line"].set_data([], [])
                self.labels[metric][avion].set_text("")
            y_max = ymax_sequence(
                self.direction, self.distance, self.pax, metric)
            ax.set_ylim(0, y_max)
            base_title = ax.get_title().split(" — ")[0]
            ax.set_title(
                f"{base_title} — {self.direction} | {self.distance} km | {self.pax} pax", fontsize=11, pad=8)
            self.wind_lines[metric].set_xdata([0, 0])

        self.fig.suptitle(f"Snapsac — Vent {self.direction} | {self.distance} km | {self.pax} pax",
                          fontsize=12, fontweight="bold")
        self.canvas.draw()
        self.vent_index = 0

    def _update(self, _):
        vent = VENTS[self.vent_index]

        best_model, best_cpx, best_state = None, float("inf"), None

        # mise à jour des séries
        for avion in AVIONS:
            etat = calcule_etat(avion, self.direction,
                                vent, self.pax, self.distance)
            if not etat:
                continue

            # Ajout des points + mise à jour du tracé
            for metric in METRICS:
                value = etat[metric]
                s = self.series[metric][avion]
                s["x"].append(vent)
                s["y"].append(value)
                s["line"].set_data(s["x"], s["y"])

                # annotation (étiquette avion) sur le dernier point
                self.labels[metric][avion].set_text(avion)
                self.labels[metric][avion].set_position((vent + 4, value))

            # meilleur avion sur critère conso/pax
            if etat["conso_L_pax"] < best_cpx:
                best_cpx = etat["conso_L_pax"]
                best_model = avion
                best_state = etat

        # ligne verticale = vent courant
        for metric in METRICS:
            self.wind_lines[metric].set_xdata([vent, vent])

        # mise en avant du gagnant
        for metric in METRICS:
            for avion, s in self.series[metric].items():
                s["line"].set_linewidth(3.2 if avion == best_model else 2.0)
                s["line"].set_alpha(1.0 if avion == best_model else 0.55)

        # titre principal enrichi (inclut vent)
        if best_model and best_state:
            self.fig.suptitle(
                f"Snapsac — {self.direction} | Vent {vent} km/h | {self.distance} km | {self.pax} pax  "
                f"→ Best: {best_model}  (L/pax {best_state['conso_L_pax']:.1f}, Durée {best_state['duree_h']:.2f} h, "
                f"Vitesse {best_state['vitesse']:.0f} km/h)",
                fontsize=12, fontweight="bold"
            )
        else:
            self.fig.suptitle(
                f"Snapsac — {self.direction} | Vent {vent} km/h | {self.distance} km | {self.pax} pax",
                fontsize=12, fontweight="bold"
            )

        # frame suivante
        self.vent_index += 1
        if self.vent_index >= len(VENTS):
            # nouvelle séquence (direction/distance/pax changent)
            self.current_seq = next(self.seq_gen)
            self._reset_sequence(self.current_seq)

        self.canvas.draw()
        return []


if __name__ == "__main__":
    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass
    app = App(root)
    root.mainloop()
