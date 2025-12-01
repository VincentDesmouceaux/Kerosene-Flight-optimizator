# app_web.py - SnapSac Live Web Version - IMPROVED (ENGLISH UI)
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import os
import math
import time
import io
from flask import Flask, Response, request, jsonify
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrow   # for weather compass
import matplotlib
matplotlib.use('Agg')

try:
    from data_sources import fetch_current_wind, fetch_opensky_states
except Exception:
    # Data sources optional; fallback will be local data
    fetch_current_wind = None
    fetch_opensky_states = None

app = Flask(__name__)

# ====== Build id ======
APP_BUILD = os.getenv("BUILD_ID", "kerosene-optimisator")

# ====== Animation settings ======
DEBUG = os.getenv("DEBUG", "0") == "1"

# Wind step (km/h) – override via env VENT_STEP
VENT_STEP = int(os.getenv("VENT_STEP", "20"))
VENT_STEPS = list(range(0, 301, VENT_STEP))

# Substeps inside each wind step (for interpolation)
# ↓ default 4 for faster motion (compass & wind move quicker)
SUBSTEPS = int(os.getenv("SUBSTEPS", "4"))

EASING = "ease_in_out"

# Target FPS – override via env TARGET_FPS
TARGET_FPS = int(os.getenv("TARGET_FPS", "30"))

# ====== Aircraft data ======
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

# Optional initial forced direction from env (head/tail/side)
FORCE_DIRECTION_ENV = os.getenv("FORCE_DIRECTION", "").strip().lower()
if FORCE_DIRECTION_ENV not in DIRECTIONS:
    FORCE_DIRECTION_ENV = None

# ====== Neon dark theme ======
BG = "#0f1221"
PANEL = "#14172a"
FG = "#E8EAF6"
MUTED = "#AAB1C6"
ACC = "#3FD0C9"

PALETTE = {
    "A320": "#11D6A3",  # Mint green
    "B737": "#FF3B30",  # Red (Apple-style)
    "B777": "#8E7CFF",  # Neon purple
    "A380": "#FFC857",  # Golden yellow
}

# ====== Business logic ======


def calcule_etat(avion_key, direction, vent, pax, distance):
    """Return flight state for given aircraft, direction, wind, pax, distance."""
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
    else:  # side / crosswind
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
        "mass_kg": masse,
        "wind_coef": coef,
    }


def ymax_sequence(direction, distance, pax, metric):
    y_max = 0.0
    for v in range(0, 301, 20):
        for avion in AVIONS:
            e = calcule_etat(avion, direction, v, pax, distance)
            if e:
                y_max = max(y_max, e[metric])
    return (y_max * 1.20) if y_max > 0 else 1.0


def sequence_generator():
    """
    Generate scenario sequence in AUTO mode:
    cycles over all directions, distances, pax.
    (When a direction is forced, we override it in _reset_sequence.)
    """
    while True:
        for d in DIRECTIONS:
            for dist in DISTANCES:
                for pax in PAX_LIST:
                    yield {"direction": d, "distance": dist, "pax": pax}

# ====== Easing & interpolation ======


def ease_in_out(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def lerp(a, b, t):
    return a + (b - a) * t


def ease_t(t):
    return ease_in_out(t) if EASING == "ease_in_out" else t

# ====== Matplotlib style helpers ======


def set_axis_style(ax, title, ylabel):
    ax.set_facecolor(PANEL)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10, color=FG)
    ax.set_xlabel("Wind (km/h)", fontsize=10, color=MUTED)
    ax.set_ylabel(ylabel, fontsize=10, color=MUTED)
    ax.grid(True, alpha=0.25, linestyle=":", linewidth=0.8, color="#4C5277")
    ax.tick_params(colors="#CAD0EA", labelsize=9)
    for sp in ax.spines.values():
        sp.set_color("#2a2f4a")
        sp.set_linewidth(1.2)


class SnapSacAnimation:
    METRICS = ("conso_L", "conso_L_pax", "duree_h")
    TITLES = {
        "conso_L": "Total fuel burn (L) vs wind",
        "conso_L_pax": "Fuel per passenger (L/pax) vs wind",
        "duree_h": "Flight time (h) vs wind",
    }
    YLABS = {
        "conso_L": "Fuel (L)", "conso_L_pax": "Fuel / pax (L)",
        "duree_h": "Time (h)"
    }

    def __init__(self):
        # Data series first
        self.series = {m: {avion: {"x": [], "y": []}
                           for avion in AVIONS} for m in self.METRICS}
        self.frame_count = 0

        # Runtime control: None = AUTO, else "head"/"tail"/"side"
        self.force_direction = FORCE_DIRECTION_ENV

        # Sequence generator (AUTO base)
        self.seq_gen = sequence_generator()
        self.current_seq = next(self.seq_gen)

        # Free APIs / weather
        self.use_free_apis = os.getenv('USE_FREE_APIS', '0') in (
            '1', 'true', 'True') and fetch_current_wind is not None
        try:
            self.center_lat = float(os.getenv('DEFAULT_LAT', '48.8566'))
            self.center_lon = float(os.getenv('DEFAULT_LON', '2.3522'))
        except Exception:
            self.center_lat, self.center_lon = 48.8566, 2.3522

        _ang = os.getenv('DEFAULT_WIND_ANGLE')
        try:
            self.wind_angle = float(_ang) if _ang is not None else None
        except Exception:
            self.wind_angle = None
        self.wind_speed = None
        self.wind_source = None

        self._reset_sequence(self.current_seq)

        # Figure / axes
        self.fig = plt.figure(figsize=(12, 9), facecolor=BG, dpi=150)
        # Leave room at the bottom for log + progress bar
        gs = self.fig.add_gridspec(3, 1, hspace=0.32, top=0.94, bottom=0.32)

        self.axes = {}
        self.lines = {m: {} for m in self.METRICS}

        for i, metric in enumerate(self.METRICS):
            ax = self.fig.add_subplot(gs[i])
            set_axis_style(ax, self.TITLES[metric], self.YLABS[metric])
            ax.set_xlim(0, 300)
            self.axes[metric] = ax

            # Lines + moving markers/labels per aircraft
            for avion, color in PALETTE.items():
                line, = ax.plot([], [], lw=3.5, color=color, alpha=0.95,
                                antialiased=True, solid_capstyle="round", zorder=3)
                self.lines[metric][avion] = line

                marker = ax.scatter(
                    [], [], s=90, color=color, alpha=0.95, zorder=6,
                    edgecolors='white', linewidths=0.8, antialiased=True
                )
                label = ax.text(
                    0, 0, "", fontsize=9, color=color,
                    bbox=dict(boxstyle="round,pad=0.2",
                              facecolor=PANEL, alpha=0.8)
                )
                label.set_visible(False)

                self.lines.setdefault('markers', {})
                self.lines.setdefault('labels', {})
                self.lines['markers'].setdefault(metric, {})
                self.lines['labels'].setdefault(metric, {})
                self.lines['markers'][metric][avion] = marker
                self.lines['labels'][metric][avion] = label

        # Canvas
        self.canvas = FigureCanvas(self.fig)

        # Legend
        legend_elements = []
        for avion, color in PALETTE.items():
            legend_elements.append(
                Line2D([0], [0], color=color, lw=4,
                       label=f"{avion}", marker='o', markersize=8)
            )
        self.axes[self.METRICS[0]].legend(
            handles=legend_elements,
            loc='upper left',
            fontsize=10,
            framealpha=0.9,
            facecolor=PANEL,
            edgecolor='#2a2f4a'
        )

        # Log window (bottom)
        self.log_ax = self.fig.add_axes((0.08, 0.14, 0.84, 0.14))
        self.log_ax.set_facecolor(PANEL)
        self.log_ax.set_xticks([])
        self.log_ax.set_yticks([])
        for sp in self.log_ax.spines.values():
            sp.set_visible(False)

        # Left part: detailed numeric log
        self.log_text = self.log_ax.text(
            0.01, 0.95, "",
            transform=self.log_ax.transAxes,
            ha="left", va="top", fontsize=9,
            color=FG, family="monospace"
        )

        # Right part: KPI status panel (bottom-right) – bigger, simpler, more visual
        self.kpi_text_artist = self.log_ax.text(
            0.99, 0.95, "",
            transform=self.log_ax.transAxes,
            ha="right", va="top", fontsize=10,
            color=FG,
            bbox=dict(boxstyle="round,pad=0.6",
                      facecolor=PANEL, alpha=0.95, edgecolor=ACC)
        )

        # Progress bar (under log)
        self.progress_ax = self.fig.add_axes((0.08, 0.08, 0.84, 0.03))
        self.progress_ax.set_facecolor(PANEL)
        self.progress_ax.set_xlim(0, len(VENT_STEPS) * SUBSTEPS)
        self.progress_ax.set_ylim(0, 1)
        self.progress_ax.set_xticks([])
        self.progress_ax.set_yticks([])
        for sp in self.progress_ax.spines.values():
            sp.set_visible(False)

        # Mini weather COMPASS (top-right overlay)
        self.met_ax = self.fig.add_axes((0.80, 0.70, 0.18, 0.22))
        self.met_ax.set_facecolor("#101325")
        self.met_ax.set_xticks([])
        self.met_ax.set_yticks([])
        for sp in self.met_ax.spines.values():
            sp.set_visible(False)
        self.met_ax.set_xlim(0, 1)
        self.met_ax.set_ylim(0, 1)
        self.met_ax.set_aspect("equal")

        # Circle + cardinal points
        self.met_circle = Circle(
            (0.5, 0.55), 0.32,
            edgecolor="#4C5277", facecolor="none",
            linewidth=1.2, alpha=0.9
        )
        self.met_ax.add_patch(self.met_circle)
        self.met_ax.text(0.5, 0.90, "N", ha="center", va="center",
                         fontsize=8, color=MUTED)
        self.met_ax.text(0.5, 0.20, "S", ha="center", va="center",
                         fontsize=8, color=MUTED)
        self.met_ax.text(0.17, 0.55, "W", ha="center", va="center",
                         fontsize=8, color=MUTED)
        self.met_ax.text(0.83, 0.55, "E", ha="center", va="center",
                         fontsize=8, color=MUTED)

        self.met_title = self.met_ax.text(
            0.5, 0.97, "LIVE WEATHER",
            ha="center", va="top",
            fontsize=9, color=FG, weight="bold"
        )
        self.met_label = self.met_ax.text(
            0.5, 0.08, "",
            ha="center", va="bottom",
            fontsize=8, color=MUTED
        )
        # Arrow placeholder (will be updated each frame)
        self.met_arrow = None

        # Subtle background "watermark" with wind info
        self.weather_bg = self.fig.text(
            0.5, 0.50, "",
            fontsize=80, color="white",
            alpha=0.04, ha="center", va="center",
            weight="bold"
        )

        # Footer
        footer_text = f"Live animation • {TARGET_FPS} FPS • Build: {APP_BUILD}"
        self.footer_artist = self.fig.text(
            0.5, 0.02, footer_text,
            fontsize=10, color=MUTED,
            ha='center', va='bottom'
        )

    def _reset_sequence(self, seq):
        base_dir = seq["direction"]
        # If a direction is forced, override the auto one
        self.direction = self.force_direction if self.force_direction in DIRECTIONS else base_dir
        self.distance = seq["distance"]
        self.pax = seq["pax"]
        self.current_seq_info = f"{self.direction} | {self.distance} km | {self.pax} pax"

        # Reset series
        for metric in self.METRICS:
            for avion in AVIONS:
                self.series[metric][avion]["x"].clear()
                self.series[metric][avion]["y"].clear()

        self.frame_count = 0

        # Optionally re-center wind steps on real wind
        if self.use_free_apis and fetch_current_wind:
            try:
                w = fetch_current_wind(self.center_lat, self.center_lon)
                if w and 'windspeed_kmh' in w:
                    ws = w.get('windspeed_kmh')
                    try:
                        self.wind_speed = float(ws) if ws is not None else None
                    except Exception:
                        self.wind_speed = None

                    wd = w.get('winddirection')
                    if self.wind_angle is None and wd is not None:
                        try:
                            self.wind_angle = float(wd)
                        except Exception:
                            pass
                    self.wind_source = 'open-meteo'

                    center = int(round(w['windspeed_kmh']))
                    lo = max(0, center - 80)
                    hi = min(300, center + 80)
                    step = VENT_STEP
                    new_steps = list(range(lo - (lo % step), hi + step, step))
                    if len(new_steps) >= 2:
                        global VENT_STEPS
                        VENT_STEPS = sorted(list(set(new_steps)))
                        self.progress_ax.set_xlim(
                            0, len(VENT_STEPS) * SUBSTEPS)
            except Exception:
                pass

    def _etat(self, avion, vent):
        return calcule_etat(avion, self.direction, vent, self.pax, self.distance)

    def _update_weather_compass(self, sim_wind):
        """Update the small compass panel with real + simulated wind."""
        # Choose what to display
        disp_speed = self.wind_speed if self.wind_speed is not None else sim_wind
        disp_angle = self.wind_angle

        # Fallback: infer angle from scenario if not provided
        if disp_angle is None:
            if self.direction == "head":
                disp_angle = 180.0  # coming from the front
            elif self.direction == "tail":
                disp_angle = 0.0    # from behind
            else:
                disp_angle = 90.0   # side / crosswind

        # Arrow (remove previous one)
        if self.met_arrow is not None and self.met_arrow in self.met_ax.patches:
            try:
                self.met_arrow.remove()
            except Exception:
                pass

        # Convert meteo wind angle (deg from north, clockwise) to vector
        rad = math.radians(disp_angle)
        dx = math.sin(rad) * 0.25
        dy = math.cos(rad) * 0.25

        self.met_arrow = FancyArrow(
            0.5, 0.55, dx, dy,
            width=0.02,
            length_includes_head=True,
            head_width=0.10,
            head_length=0.10,
            color=ACC,
            alpha=0.95
        )
        self.met_ax.add_patch(self.met_arrow)

        # Text under the compass
        source = self.wind_source if self.wind_source else "sim only"
        label = f"{disp_speed:.0f} km/h  •  {disp_angle:.0f}°\nsource: {source}"
        self.met_label.set_text(label)

        # Big subtle background text (“image” feeling)
        self.weather_bg.set_text(f"{disp_speed:.0f} km/h\nWIND")

    def generate_frame(self):
        try:
            # Update Y-limits
            for metric in self.METRICS:
                ax = self.axes[metric]
                ymax = ymax_sequence(
                    self.direction, self.distance, self.pax, metric)
                ax.set_ylim(0, ymax)

            axes = self.axes

            # Animation progression
            total_frames = len(VENT_STEPS) * SUBSTEPS
            if self.frame_count >= total_frames:
                self.current_seq = next(self.seq_gen)
                self._reset_sequence(self.current_seq)
                self.frame_count = 0
                total_frames = len(VENT_STEPS) * SUBSTEPS
                self.progress_ax.set_xlim(0, total_frames)

            step_index = self.frame_count // SUBSTEPS
            substep = self.frame_count % SUBSTEPS
            t = ease_t(substep / SUBSTEPS)
            try:
                t = float(t)
            except Exception:
                try:
                    t = float(str(t))
                except Exception:
                    t = 0.0

            v0 = VENT_STEPS[step_index]
            v1 = VENT_STEPS[step_index +
                            1] if step_index < len(VENT_STEPS) - 1 else v0
            v_cur = lerp(v0, v1, t)

            # Compute states and update series
            best_model, best_state, best_cpx = None, None, float("inf")

            for avion in AVIONS:
                e0 = self._etat(avion, v0)
                e1 = self._etat(avion, v1) if step_index < len(
                    VENT_STEPS) - 1 else e0

                if not e0:
                    continue

                # Add point at the start of each step
                if substep == 0:
                    for metric in self.METRICS:
                        self.series[metric][avion]["x"].append(v0)
                        self.series[metric][avion]["y"].append(e0[metric])

                # Best by fuel per pax
                y0c = e0["conso_L_pax"]
                y1c = (e1["conso_L_pax"] if e1 else y0c)
                cpx_cur = lerp(y0c, y1c, t)
                if cpx_cur < best_cpx:
                    best_cpx = cpx_cur
                    best_model = avion
                    best_state = e0

            # Draw curves
            for metric, ax in axes.items():
                # Vertical wind line
                for ln in [ln for ln in list(ax.lines) if getattr(ln, '_is_vline', False)]:
                    try:
                        ln.remove()
                    except Exception:
                        pass
                vline = ax.axvline(
                    v_cur, color="#7480b8", lw=2.0,
                    ls="--", alpha=0.7, zorder=4
                )
                vline._is_vline = True

                # Wind text
                for txt in [txt for txt in list(ax.texts) if getattr(txt, '_is_vent', False)]:
                    try:
                        txt.remove()
                    except Exception:
                        pass
                vent_text = ax.text(
                    v_cur + 5, ax.get_ylim()[1] * 0.95,
                    f"Wind: {v_cur:.0f} km/h",
                    fontsize=9, color="#7480b8",
                    ha='left', va='top',
                    bbox=dict(boxstyle="round,pad=0.3",
                              facecolor=PANEL, alpha=0.8)
                )
                vent_text._is_vent = True

                for avion, color in PALETTE.items():
                    s = self.series[metric][avion]
                    line = self.lines[metric][avion]

                    if len(s["x"]) > 0:
                        line.set_data(s["x"], s["y"])

                        marker = self.lines['markers'][metric][avion]
                        label = self.lines['labels'][metric][avion]

                        e0_marker = calcule_etat(
                            avion, self.direction, v0, self.pax, self.distance)
                        e1_marker = calcule_etat(
                            avion, self.direction, v1, self.pax, self.distance
                        ) if step_index < len(VENT_STEPS) - 1 else e0_marker

                        if e0_marker:
                            y0_marker = e0_marker[metric]
                            y1_marker = e1_marker[metric] if e1_marker else y0_marker
                            y_cur_marker = lerp(y0_marker, y1_marker, t)
                            try:
                                marker.set_offsets([[v_cur, y_cur_marker]])

                                if avion == best_model:
                                    if avion == 'A320':
                                        marker.set_sizes([520])
                                        marker.set_edgecolors('white')
                                        marker.set_linewidths(1.8)
                                        marker.set_alpha(1.0)
                                        marker.set_zorder(14)
                                    else:
                                        marker.set_sizes([340])
                                        marker.set_edgecolors('white')
                                        marker.set_linewidths(1.4)
                                        marker.set_alpha(1.0)
                                        marker.set_zorder(13)
                                    try:
                                        line.set_linewidth(5.0)
                                        line.set_zorder(10)
                                    except Exception:
                                        pass
                                else:
                                    marker.set_sizes([110])
                                    marker.set_alpha(0.85)
                                    marker.set_zorder(6)
                                    try:
                                        line.set_linewidth(3.5)
                                        line.set_zorder(3)
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                            # Moving label
                            label.set_position((v_cur + 6, y_cur_marker))
                            label.set_text(avion)
                            if avion == best_model:
                                label.set_color(ACC)
                                label.set_fontweight('bold')
                            else:
                                label.set_color(color)
                                label.set_fontweight('normal')
                            label.set_visible(True)
                        else:
                            marker.set_offsets(np.array([]).reshape(0, 2))
                            label.set_visible(False)
                    else:
                        line.set_data([], [])
                        marker = self.lines['markers'][metric][avion]
                        label = self.lines['labels'][metric][avion]
                        marker.set_offsets(np.array([]).reshape(0, 2))
                        label.set_visible(False)

                # "Best" text
                best_text = f"Best: {best_model}" if best_model else "Best: —"
                for old_best in [old for old in ax.texts if getattr(old, '_is_best', False)]:
                    old_best.remove()
                best_txt = ax.text(
                    0.98, 0.96, best_text,
                    transform=ax.transAxes,
                    ha="right", va="top",
                    fontsize=11, color="#C9CEEC", weight='bold',
                    bbox=dict(boxstyle="round,pad=0.4",
                              facecolor=PANEL, alpha=0.9)
                )
                best_txt._is_best = True

            # Suptitle – more “product” style
            direction_emoji = {"head": "↓", "tail": "↑", "side": "↔"}
            emoji = direction_emoji.get(self.direction, "")
            title_text = (
                f"{emoji} Kerosene Optimisator • Live fuel comparison • "
                f"Wind {v_cur:.0f} km/h • {self.distance} km • {self.pax} pax"
            )
            for st_old in [st_old for st_old in self.fig.texts if getattr(st_old, '_is_suptitle', False)]:
                st_old.remove()
            st = self.fig.suptitle(
                title_text, fontsize=17, fontweight="bold", color=FG, y=0.98
            )
            st._is_suptitle = True

            # Progress bar
            for p in list(self.progress_ax.patches):
                try:
                    p.remove()
                except Exception:
                    pass
            for txt in list(self.progress_ax.texts):
                try:
                    txt.remove()
                except Exception:
                    pass

            self.progress_ax.barh(
                0.5, self.frame_count,
                color=ACC, alpha=0.9, height=0.6,
                edgecolor=ACC, linewidth=1, zorder=3
            )
            self.progress_ax.barh(
                0.5, total_frames,
                color=PANEL, alpha=0.3, height=0.6, zorder=1
            )
            progress_pct = (self.frame_count / total_frames) * 100
            self.progress_ax.text(
                0.5, 0.5, f"{progress_pct:.1f}%",
                transform=self.progress_ax.transAxes,
                ha='center', va='center',
                color=FG, fontsize=9, weight='bold'
            )

            # === Bottom LOG (detailed, English) ===
            log_lines = []
            log_lines.append(
                f"FRAME {self.frame_count:4d} • Wind {v_cur:5.1f} km/h • "
                f"dir={self.direction} • dist={self.distance} km • pax={self.pax}"
            )
            log_lines.append("-" * 90)
            log_lines.append(
                "ACFT | mass[t] | base L/km | wind_coef | fuel/pax[L] | fuel_tot[L] | time[h] | speed[km/h]"
            )
            log_lines.append("-" * 90)

            for avion in AVIONS:
                e = calcule_etat(avion, self.direction, v_cur,
                                 self.pax, self.distance)
                if e:
                    mass_t = e["mass_kg"] / 1000.0
                    coef = e["wind_coef"]
                    specs = AVIONS[avion]
                    base = specs["conso_base"]
                    log_lines.append(
                        f"{avion:4s} | {mass_t:6.1f} | {base:9.3f} | {coef:+9.3f} | "
                        f"{e['conso_L_pax']:11.2f} | {e['conso_L']:11.0f} | "
                        f"{e['duree_h']:7.3f} | {e['vitesse']:11.0f}"
                    )

            if best_model is not None:
                log_lines.append("")
                log_lines.append(
                    f"BEST MODEL → {best_model}  (fuel per pax = {best_cpx:5.1f} L)"
                )

            self.log_text.set_text("\n".join(log_lines))

            # === KPI PANEL (bottom-right, in log area) – simplified & bigger ===
            kpi_lines = []
            kpi_lines.append("RUN SNAPSHOT")
            kpi_lines.append(
                f"{self.direction.upper()} • {self.distance} km • {self.pax} pax"
            )

            # Compact wind line: sim vs real meteo
            wind_parts = [f"sim wind {v_cur:.0f} km/h"]
            if self.wind_speed is not None:
                wind_parts.append(f"meteo {self.wind_speed:.0f} km/h")
            if self.wind_angle is not None:
                wind_parts.append(f"{self.wind_angle:.0f}°")
            kpi_lines.append(" | ".join(wind_parts))

            kpi_lines.append("")

            if best_model and best_state:
                kpi_lines.append(f"BEST: {best_model}")
                kpi_lines.append(
                    f"Fuel / pax : {best_state['conso_L_pax']:.1f} L")
                kpi_lines.append(
                    f"Total fuel : {best_state['conso_L']:,.0f} L")
                kpi_lines.append(
                    f"Time       : {best_state['duree_h']:.2f} h")
                kpi_lines.append(
                    f"Speed      : {best_state['vitesse']:.0f} km/h")

            self.kpi_text_artist.set_text("\n".join(kpi_lines))

            # === Weather compass & background text ===
            self._update_weather_compass(v_cur)

            # Render frame
            img_buffer = io.BytesIO()
            self.canvas.draw()
            self.canvas.print_png(img_buffer)
            img_buffer.seek(0)
            img_data = img_buffer.getvalue()

            self.frame_count += 1
            return img_data

        except Exception as e:
            print(f"Frame generation error: {e}")
            import traceback
            traceback.print_exc()
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, f"Kerosene Optimisator\nError: {e}",
                    ha='center', va='center', fontsize=16,
                    transform=ax.transAxes)
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png')
            img_buffer.seek(0)
            return img_buffer.getvalue()
        finally:
            pass


# Init animation (global singleton)
snapsac_anim = SnapSacAnimation()


def generate_frames():
    while True:
        try:
            frame = snapsac_anim.generate_frame()
            yield (b'--frame\r\n'
                   b'Content-Type: image/png\r\n\r\n' + frame + b'\r\n')
            time.sleep(1.0 / TARGET_FPS)
        except Exception as e:
            print(f"Stream error: {e}")
            time.sleep(1)


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/health')
def health():
    return 'OK'


# ====== CONTROL ENDPOINT (for UI buttons) ======
@app.route('/control', methods=['POST'])
def control():
    """
    Simple JSON API:
    { "direction": "auto" | "head" | "tail" | "side" }
    """
    data = request.get_json(silent=True) or {}
    direction = str(data.get("direction", "")).strip().lower()

    if direction == "auto":
        snapsac_anim.force_direction = None
        snapsac_anim._reset_sequence(snapsac_anim.current_seq)
        return jsonify({"status": "ok", "mode": "auto"})

    if direction in DIRECTIONS:
        snapsac_anim.force_direction = direction
        snapsac_anim._reset_sequence(snapsac_anim.current_seq)
        return jsonify({"status": "ok", "mode": "forced", "direction": direction})

    return jsonify({"status": "error", "message": "invalid direction"}), 400


@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Kerosene Optimisator - Live Simulation</title>
        <meta charset="utf-8">
        <style>
            body { 
                margin: 0; 
                background: #0a0a0a;
                font-family: 'Arial', sans-serif;
                overflow: hidden;
            }
            .container { 
                display: flex; 
                flex-direction: column;
                justify-content: center; 
                align-items: center; 
                min-height: 100vh;
                background: radial-gradient(circle at center, #1a1a2e 0%, #0a0a0a 100%);
                padding: 20px;
            }
            .header {
                text-align: center;
                margin-bottom: 20px;
                color: white;
            }
            .header h1 {
                font-size: 2.8em;
                margin: 0;
                background: linear-gradient(45deg, #11D6A3, #8E7CFF, #FFC857);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                text-shadow: 0 0 30px rgba(78, 205, 196, 0.5);
            }
            .header p {
                font-size: 1.1em;
                color: #AAB1C6;
                margin-top: 8px;
            }
            .video-container {
                border: 3px solid;
                border-image: linear-gradient(45deg, #11D6A3, #8E7CFF, #FFC857) 1;
                border-radius: 15px;
                padding: 10px;
                background: rgba(0, 0, 0, 0.7);
                box-shadow: 0 0 60px rgba(78, 205, 196, 0.4);
                margin-bottom: 10px;
            }
            img { 
                max-width: 95vw; 
                max-height: 70vh; 
                display: block;
                border-radius: 12px;
            }
            .controls {
                margin-top: 10px;
                display: flex;
                gap: 10px;
                justify-content: center;
                flex-wrap: wrap;
            }
            .ctrl-btn {
                background: #14172a;
                border: 1px solid #3FD0C9;
                color: #E8EAF6;
                padding: 8px 16px;
                border-radius: 999px;
                font-size: 0.9em;
                cursor: pointer;
                transition: all 0.15s ease-out;
                letter-spacing: 0.03em;
            }
            .ctrl-btn:hover {
                background: #1f2438;
                box-shadow: 0 0 12px rgba(63, 208, 201, 0.4);
            }
            .ctrl-btn.active {
                background: #3FD0C9;
                color: #0f1221;
                box-shadow: 0 0 16px rgba(63, 208, 201, 0.8);
            }
            .legend-info {
                margin-top: 12px;
                color: #AAB1C6;
                font-size: 0.9em;
                text-align: center;
            }
            .stats {
                margin-top: 10px;
                text-align: center;
                color: #3FD0C9;
                font-size: 0.95em;
                line-height: 1.6;
            }
            .footer {
                margin-top: 15px;
                color: #666;
                font-size: 0.85em;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✈️ Kerosene Optimisator</h1>
                <p>Real-time fuel optimisation • Live streaming from a Python / Matplotlib engine</p>
            </div>
            
            <div class="video-container">
                <img src="/video_feed" alt="Kerosene Optimisator Live Simulation">
            </div>

            <div class="controls">
                <button class="ctrl-btn active" data-dir="auto">Auto</button>
                <button class="ctrl-btn" data-dir="head">Headwind</button>
                <button class="ctrl-btn" data-dir="tail">Tailwind</button>
                <button class="ctrl-btn" data-dir="side">Sidewind</button>
            </div>
            
            <div class="legend-info">
                <p>🎨 <strong>Legend:</strong> A320 (Green) • B737 (Red) • B777 (Purple) • A380 (Yellow)</p>
            </div>
            
            <div class="stats">
                <p>🎯 Live multi-aircraft comparison • 🌡️ Real wind overlay when available • 🧭 Compass shows meteo direction</p>
                <p>⏱️ Fast scenarios cycling in AUTO • 🔀 Or lock a specific wind direction with the controls above</p>
            </div>
            
            <div class="footer">
                <p>Powered by Flask & Matplotlib • Docker / Northflank-ready • BUILD: ''' + APP_BUILD + '''</p>
            </div>
        </div>
        
        <script>
            let frameCount = 0;
            const img = document.querySelector('img');
            const buttons = document.querySelectorAll('.ctrl-btn');
            
            img.onload = function() {
                frameCount++;
                console.log('Frame loaded:', frameCount);
            };
            
            img.onerror = function() {
                console.error('Error loading stream');
            };

            buttons.forEach(btn => {
                btn.addEventListener('click', () => {
                    const dir = btn.dataset.dir;
                    fetch('/control', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ direction: dir })
                    })
                    .then(r => r.json())
                    .then(data => {
                        console.log('Control response:', data);
                        if (data.status === 'ok') {
                            buttons.forEach(b => b.classList.remove('active'));
                            btn.classList.add('active');
                        } else {
                            console.warn('Control error:', data);
                        }
                    })
                    .catch(err => console.error('Control request failed:', err));
                });
            });
        </script>
    </body>
    </html>
    '''


if __name__ == '__main__':
    port = int(os.getenv("PORT", "8080"))
    print("🚀 Starting Kerosene Optimisator Web...")
    print(f"📡 Listening on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
