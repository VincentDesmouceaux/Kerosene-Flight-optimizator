# app_web.py - SnapSac Live Web Version - AMÉLIORÉE
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import os
import math
import time
import io
from flask import Flask, Response
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib
matplotlib.use('Agg')
try:
    from data_sources import fetch_current_wind, fetch_opensky_states
except Exception:
    # Data sources optional; fallback will be local data
    fetch_current_wind = None
    fetch_opensky_states = None

app = Flask(__name__)

# ====== Build canari ======
APP_BUILD = os.getenv("BUILD_ID", "kerosene-optimisator")

# ====== Réglages animation ======
DEBUG = os.getenv("DEBUG", "0") == "1"
VENT_STEPS = list(range(0, 301, 20))
SUBSTEPS = 20  # increase interpolation steps for smoother motion (heavier CPU)
EASING = "ease_in_out"
TARGET_FPS = 30  # target frames per second for a professional look

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
BG = "#0f1221"
PANEL = "#14172a"
FG = "#E8EAF6"
MUTED = "#AAB1C6"
ACC = "#3FD0C9"

PALETTE = {
    "A320": "#11D6A3",  # Vert menthe
    "B737": "#FF6B35",  # Orange vif
    "B777": "#8E7CFF",  # Violet néon
    "A380": "#FFC857",  # Jaune doré
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
    return {"conso_L": conso_L, "conso_L_pax": conso_L / pax, "duree_h": distance / vitesse, "vitesse": vitesse}


def ymax_sequence(direction, distance, pax, metric):
    y_max = 0.0
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

# ====== Easing & interpolation ======


def ease_in_out(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def lerp(a, b, t):
    return a + (b - a) * t


def ease_t(t):
    return ease_in_out(t) if EASING == "ease_in_out" else t

# ====== Style matplotlib ======


def set_axis_style(ax, title, ylabel):
    ax.set_facecolor(PANEL)
    ax.set_title(title, fontsize=12, fontweight="bold", pad=10, color=FG)
    ax.set_xlabel("Vent (km/h)", fontsize=10, color=MUTED)
    ax.set_ylabel(ylabel, fontsize=10, color=MUTED)
    ax.grid(True, alpha=0.25, linestyle=":", linewidth=0.8, color="#4C5277")
    ax.tick_params(colors="#CAD0EA", labelsize=9)
    for sp in ax.spines.values():
        sp.set_color("#2a2f4a")
        sp.set_linewidth(1.2)


class SnapSacAnimation:
    METRICS = ("conso_L", "conso_L_pax", "duree_h")
    TITLES = {
        "conso_L": "Consommation totale (L) vs Vent",
        "conso_L_pax": "Consommation par passager (L/pax) vs Vent",
        "duree_h": "Durée estimée (h) vs Vent",
    }
    YLABS = {
        "conso_L": "Litres (L)", "conso_L_pax": "L/pax", "duree_h": "Heures (h)"}

    def __init__(self):
        # INITIALISER LES SÉRIES EN PREMIER ! (données)
        self.series = {m: {avion: {"x": [], "y": []}
                           for avion in AVIONS} for m in self.METRICS}
        self.frame_count = 0

        # PUIS initialiser la séquence
        self.seq_gen = sequence_generator()
        self.current_seq = next(self.seq_gen)

        # Free APIs mode - initialiser AVANT _reset_sequence (utilisé dans _reset_sequence)
        self.use_free_apis = os.getenv('USE_FREE_APIS', '0') in (
            '1', 'true', 'True') and fetch_current_wind is not None
        # center point for weather lookups (env or Paris default)
        try:
            self.center_lat = float(os.getenv('DEFAULT_LAT', '48.8566'))
            self.center_lon = float(os.getenv('DEFAULT_LON', '2.3522'))
        except Exception:
            self.center_lat, self.center_lon = 48.8566, 2.3522

        self._reset_sequence(self.current_seq)

        # Créer la figure et les axes une seule fois pour réutilisation (gain de perf)
        # DPI augmenté pour rendu professionnel (plus de charge CPU)
        self.fig = plt.figure(figsize=(12, 9), facecolor=BG, dpi=150)
        gs = self.fig.add_gridspec(3, 1, hspace=0.35, top=0.92, bottom=0.10)
        self.axes = {}
        self.lines = {m: {} for m in self.METRICS}
        for i, metric in enumerate(self.METRICS):
            ax = self.fig.add_subplot(gs[i])
            set_axis_style(ax, self.TITLES[metric], self.YLABS[metric])
            ax.set_xlim(0, 300)
            self.axes[metric] = ax
            # Pré-créer des Line2D pour chaque avion
            for avion, color in PALETTE.items():
                line, = ax.plot([], [], lw=3.5, color=color, alpha=0.95, antialiased=True,
                                solid_capstyle="round", zorder=3)
                self.lines[metric][avion] = line
                # marker mobile pour position courante
                marker = ax.scatter(
                    [], [], s=90, color=color, alpha=0.95, zorder=6, edgecolors='white', linewidths=0.8, antialiased=True)
                # label mobile pour le nom de l'avion
                label = ax.text(0, 0, "", fontsize=9, color=color,
                                bbox=dict(boxstyle="round,pad=0.2", facecolor=PANEL, alpha=0.8))
                label.set_visible(False)
                self.lines.setdefault('markers', {})
                self.lines.setdefault('labels', {})
                self.lines['markers'].setdefault(metric, {})
                self.lines['labels'].setdefault(metric, {})
                self.lines['markers'][metric][avion] = marker
                self.lines['labels'][metric][avion] = label

        # Canvas réutilisable
        self.canvas = FigureCanvas(self.fig)
        # Free APIs mode
        self.use_free_apis = os.getenv('USE_FREE_APIS', '0') in (
            '1', 'true', 'True') and fetch_current_wind is not None
        # center point for weather lookups (env or Paris default)
        try:
            self.center_lat = float(os.getenv('DEFAULT_LAT', '48.8566'))
            self.center_lon = float(os.getenv('DEFAULT_LON', '2.3522'))
        except Exception:
            self.center_lat, self.center_lon = 48.8566, 2.3522
        # Légende statique (sur le premier axe)
        legend_elements = []
        for avion, color in PALETTE.items():
            legend_elements.append(Line2D([0], [0], color=color, lw=4,
                                          label=f"{avion}", marker='o', markersize=8))
        self.axes[self.METRICS[0]].legend(handles=legend_elements, loc='upper left', fontsize=10,
                                          framealpha=0.9, facecolor=PANEL, edgecolor='#2a2f4a')
        # Progress bar axis (statique) — sera réutilisée et nettoyée à chaque frame
        self.progress_ax = self.fig.add_axes((0.1, 0.04, 0.8, 0.02))
        self.progress_ax.set_facecolor(PANEL)
        self.progress_ax.set_xlim(0, len(VENT_STEPS) * SUBSTEPS)
        self.progress_ax.set_ylim(0, 1)
        self.progress_ax.set_xticks([])
        self.progress_ax.set_yticks([])
        for sp in self.progress_ax.spines.values():
            sp.set_visible(False)
        # Footer statique
        footer_text = f"Animation en direct • {TARGET_FPS} FPS • Build: {APP_BUILD}"
        self.footer_artist = self.fig.text(0.5, 0.02, footer_text, fontsize=10, color=MUTED,
                                           ha='center', va='bottom')

    def _reset_sequence(self, seq):
        self.direction = seq["direction"]
        self.distance = seq["distance"]
        self.pax = seq["pax"]
        self.current_seq_info = f"{self.direction} | {self.distance}km | {self.pax}pax"

        # Reset séries - VIDE les listes existantes au lieu de réassigner
        for metric in self.METRICS:
            for avion in AVIONS:
                self.series[metric][avion]["x"].clear()
                self.series[metric][avion]["y"].clear()

        self.frame_count = 0
        # If requested, update VENT_STEPS around current real wind (best-effort)
        if self.use_free_apis and fetch_current_wind:
            try:
                w = fetch_current_wind(self.center_lat, self.center_lon)
                if w and 'windspeed_kmh' in w:
                    center = int(round(w['windspeed_kmh']))
                    # Build vent steps centered on current wind, clipped to 0-300
                    lo = max(0, center - 80)
                    hi = min(300, center + 80)
                    step = 20
                    new_steps = list(range(lo - (lo % step), hi + step, step))
                    if len(new_steps) >= 2:
                        global VENT_STEPS
                        VENT_STEPS = sorted(list(set(new_steps)))
            except Exception:
                pass

    def _etat(self, avion, vent):
        return calcule_etat(avion, self.direction, vent, self.pax, self.distance)

    def generate_frame(self):
        try:
            # Mettre à jour les limites Y et préparer axes (réutilisation)
            for metric in self.METRICS:
                ax = self.axes[metric]
                ymax = ymax_sequence(
                    self.direction, self.distance, self.pax, metric)
                ax.set_ylim(0, ymax)

            axes = self.axes

            # Avancement de l'animation
            total_frames = len(VENT_STEPS) * SUBSTEPS
            if self.frame_count >= total_frames:
                self.current_seq = next(self.seq_gen)
                self._reset_sequence(self.current_seq)
                self.frame_count = 0

            step_index = self.frame_count // SUBSTEPS
            substep = self.frame_count % SUBSTEPS
            t = ease_t(substep / SUBSTEPS)
            # defensive: ensure t is numeric (avoid accidental shadowing to a Text object)
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

            # Calcul des états et mise à jour des séries
            best_model, best_state, best_cpx = None, None, float("inf")

            for avion in AVIONS:
                e0 = self._etat(avion, v0)
                e1 = self._etat(avion, v1) if step_index < len(
                    VENT_STEPS) - 1 else e0

                if not e0:
                    continue

                # Ajouter point aux séries au début de chaque step
                if substep == 0:
                    for metric in self.METRICS:
                        self.series[metric][avion]["x"].append(v0)
                        self.series[metric][avion]["y"].append(e0[metric])

                # Calcul du meilleur (L/pax)
                y0c = e0["conso_L_pax"]
                y1c = (e1["conso_L_pax"] if e1 else y0c)
                cpx_cur = lerp(y0c, y1c, t)
                if cpx_cur < best_cpx:
                    best_cpx = cpx_cur
                    best_model = avion
                    best_state = e0

            # Dessiner les courbes en mettant à jour les Line2D existantes
            for metric, ax in axes.items():
                # Ligne de vent actuelle (rafraîchie)
                # supprimer l'ancienne ligne verticale si présente
                for ln in [ln for ln in list(ax.lines) if getattr(ln, '_is_vline', False)]:
                    try:
                        ln.remove()
                    except Exception:
                        pass
                vline = ax.axvline(v_cur, color="#7480b8", lw=2.0,
                                   ls="--", alpha=0.7, zorder=4)
                vline._is_vline = True
                # supprimer ancien texte de vent
                for txt in [txt for txt in list(ax.texts) if getattr(txt, '_is_vent', False)]:
                    try:
                        txt.remove()
                    except Exception:
                        pass
                vent_text = ax.text(v_cur + 5, ax.get_ylim()[1] * 0.95, f"Vent: {v_cur:.0f} km/h",
                                    fontsize=9, color="#7480b8", ha='left', va='top',
                                    bbox=dict(boxstyle="round,pad=0.3", facecolor=PANEL, alpha=0.8))
                vent_text._is_vent = True

                for avion, color in PALETTE.items():
                    s = self.series[metric][avion]
                    line = self.lines[metric][avion]
                    if len(s["x"]) > 0:
                        line.set_data(s["x"], s["y"])
                        # mettre à jour marker et label mobiles
                        marker = self.lines['markers'][metric][avion]
                        label = self.lines['labels'][metric][avion]
                        # calculer position interpolée pour ce metric
                        e0_marker = calcule_etat(
                            avion, self.direction, v0, self.pax, self.distance)
                        e1_marker = calcule_etat(avion, self.direction, v1, self.pax, self.distance) if step_index < len(
                            VENT_STEPS) - 1 else e0_marker
                        if e0_marker:
                            y0_marker = e0_marker[metric]
                            y1_marker = e1_marker[metric] if e1_marker else y0_marker
                            y_cur_marker = lerp(y0_marker, y1_marker, t)
                            try:
                                marker.set_offsets([[v_cur, y_cur_marker]])
                                # Si c'est le meilleur modèle : mise en évidence forte
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
                            # label: avancer avec le point, couleur spéciale si meilleur
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
                            # pas de donnée
                            marker.set_offsets(np.array([]).reshape(0, 2))
                            label.set_visible(False)
                    else:
                        line.set_data([], [])
                        # masquer marker et label
                        marker = self.lines['markers'][metric][avion]
                        label = self.lines['labels'][metric][avion]
                        marker.set_offsets(np.array([]).reshape(0, 2))
                        label.set_visible(False)

                # Texte best en haut à droite
                best_text = f"Best: {best_model}" if best_model else "Best: —"
                # remove previous best text if exists
                for old_best in [old for old in ax.texts if getattr(old, '_is_best', False)]:
                    old_best.remove()
                best_txt = ax.text(0.98, 0.96, best_text, transform=ax.transAxes,
                                   ha="right", va="top", fontsize=11, color="#C9CEEC", weight='bold',
                                   bbox=dict(boxstyle="round,pad=0.4", facecolor=PANEL, alpha=0.9))
                best_txt._is_best = True

                # (la légende est statique et déjà créée dans __init__)

            # Titre principal avec infos séquence
            direction_emoji = {"head": "↓", "tail": "↑", "side": "←"}
            emoji = direction_emoji.get(self.direction, "")

            title_text = f"{emoji} Kérosène Optimisator - Vent: {v_cur:.0f} km/h - {self.direction} - {self.distance} km - {self.pax} pax - Frame: {self.frame_count}"
            # remove previous suptitle texts
            for st_old in [st_old for st_old in self.fig.texts if getattr(st_old, '_is_suptitle', False)]:
                st_old.remove()
            st = self.fig.suptitle(
                title_text, fontsize=16, fontweight="bold", color=FG, y=0.98)
            st._is_suptitle = True

            # Barre de progression améliorée (réutilise self.progress_ax)
            # nettoyer anciens patches/textes
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
            # Barre de progression avec dégradé
            self.progress_ax.barh(0.5, self.frame_count, color=ACC, alpha=0.9, height=0.6,
                                  edgecolor=ACC, linewidth=1, zorder=3)
            self.progress_ax.barh(0.5, total_frames, color=PANEL,
                                  alpha=0.3, height=0.6, zorder=1)

            # Pourcentage de progression
            progress_pct = (self.frame_count / total_frames) * 100
            self.progress_ax.text(0.5, 0.5, f"{progress_pct:.1f}%", transform=self.progress_ax.transAxes,
                                  ha='center', va='center', color=FG, fontsize=9, weight='bold')

            # KPIs dans un encart amélioré
            kpi_text = "STATUT SIMULATION\n\n"
            kpi_text += f"Direction: {self.direction}\n"
            kpi_text += f"Distance: {self.distance} km\n"
            kpi_text += f"Passagers: {self.pax}\n\n"

            if best_model and best_state:
                kpi_text += f"MEILLEUR: {best_model}\n"
                kpi_text += f"Conso/pax: {best_state['conso_L_pax']:.1f} L\n"
                kpi_text += f"Conso tot: {best_state['conso_L']:,.0f} L\n"
                kpi_text += f"Durée: {best_state['duree_h']:.2f} h\n"
                kpi_text += f"Vitesse: {best_state['vitesse']:.0f} km/h"

            # KPIs: remplacer le précédent si présent
            for old_kpi in [old_kpi for old_kpi in self.fig.texts if getattr(old_kpi, '_is_kpi', False)]:
                old_kpi.remove()
            kpi_artist = self.fig.text(0.02, 0.82, kpi_text, fontsize=11, color=FG,
                                       verticalalignment='top', bbox=dict(boxstyle="round,pad=0.8",
                                                                          facecolor=PANEL, alpha=0.9, edgecolor=ACC))
            kpi_artist._is_kpi = True

            # Footer: statique créé en __init__ (self.footer_artist)

            # Convertir en image via canvas réutilisé (plus rapide)
            img_buffer = io.BytesIO()
            self.canvas.draw()
            self.canvas.print_png(img_buffer)
            img_buffer.seek(0)
            img_data = img_buffer.getvalue()

            self.frame_count += 1

            return img_data

        except Exception as e:
            print(f"Erreur génération frame: {e}")
            import traceback
            traceback.print_exc()
            # Fallback simple
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, f"Kérosène Optimisator\nErreur: {e}", ha='center', va='center',
                    fontsize=16, transform=ax.transAxes)
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png')
            img_buffer.seek(0)
            return img_buffer.getvalue()
        finally:
            # Ne pas fermer la figure persistante; on la réutilise pour chaque frame
            pass


# Initialiser l'animation
snapsac_anim = SnapSacAnimation()


def generate_frames():
    while True:
        try:
            frame = snapsac_anim.generate_frame()
            yield (b'--frame\r\n'
                   b'Content-Type: image/png\r\n\r\n' + frame + b'\r\n')
            time.sleep(1.0 / TARGET_FPS)
        except Exception as e:
            print(f"Erreur stream: {e}")
            time.sleep(1)


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/health')
def health():
    return 'OK'


@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Kérosène Optimisator - Simulation</title>
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
                margin-bottom: 25px;
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
                font-size: 1.2em;
                color: #AAB1C6;
                margin-top: 10px;
            }
            .video-container {
                border: 3px solid;
                border-image: linear-gradient(45deg, #11D6A3, #8E7CFF, #FFC857) 1;
                border-radius: 15px;
                padding: 10px;
                background: rgba(0, 0, 0, 0.7);
                box-shadow: 0 0 60px rgba(78, 205, 196, 0.4);
                margin-bottom: 20px;
            }
            img { 
                max-width: 95vw; 
                max-height: 75vh; 
                display: block;
                border-radius: 12px;
            }
            .stats {
                margin-top: 25px;
                text-align: center;
                color: #3FD0C9;
                font-size: 1.1em;
                line-height: 1.6;
            }
            .footer {
                margin-top: 25px;
                color: #666;
                font-size: 0.9em;
                text-align: center;
            }
            .legend-info {
                margin-top: 15px;
                color: #AAB1C6;
                font-size: 0.9em;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>✈️ Kérosène Optimisator</h1>
                <p>Simulation avancée de consommation carburant • Streaming temps réel 30 FPS</p>
            </div>
            
            <div class="video-container">
                <img src="/video_feed" alt="Kérosène Optimisator Live Simulation">
            </div>
            
            <div class="legend-info">
                <p>🎨 <strong>Légende:</strong> A320 (Vert) • B737 (Orange) • B777 (Violet) • A380 (Jaune)</p>
            </div>
            
            <div class="stats">
                <p>🎯 Simulation en temps réel • 📊 4 modèles d'avions analysés • 🌡️ Vent: 0-300 km/h</p>
                <p>⏱️ Durée par séquence: ~30s • 🔄 Changement automatique des paramètres</p>
            </div>
            
            <div class="footer">
                <p>Powered by Flask & Matplotlib • Northflank Deployment • BUILD: ''' + APP_BUILD + '''</p>
            </div>
        </div>
        
        <script>
            let frameCount = 0;
            const img = document.querySelector('img');
            
            img.onload = function() {
                frameCount++;
                console.log('Frame loaded:', frameCount);
            };
            
            img.onerror = function() {
                console.error('Error loading stream');
            };
        </script>
    </body>
    </html>
    '''


if __name__ == '__main__':
    print("🚀 Démarrage Kérosène Optimisator Web...")
    print("📡 Accédez à: http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
