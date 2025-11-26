from matplotlib.animation import FuncAnimation, FFMpegWriter, writers
from matplotlib import pyplot as plt
import os
import time
import datetime
import sys
import random
import matplotlib
matplotlib.use("Agg")  # backend headless

print("[INFO] Python:", sys.version.split()[0])
print("[INFO] MPL backend:", matplotlib.get_backend())
print("[INFO] ffmpeg disponible:", writers.is_available("ffmpeg"))
print("[INFO] cwd:", os.getcwd())

LOOP_DELAY = int(os.getenv("LOOP_DELAY", "10"))
OUT_DIR = os.getenv("OUT_DIR", "/out")
FPS = int(os.getenv("FPS", "10"))
INTERVAL_MS = int(os.getenv("INTERVAL_MS", "90"))
SHUFFLE_SEQUENCES = os.getenv("SHUFFLE_SEQUENCES", "0")

AVIONS = {
    "A320": {"poids_vide": 42000,  "conso_base": 2.4, "max_pax": 180, "sens_vent": 1.0, "vitesse": 840},
    "B737": {"poids_vide": 41413,  "conso_base": 2.6, "max_pax": 190, "sens_vent": 1.1, "vitesse": 842},
    "B777": {"poids_vide": 134800, "conso_base": 5.0, "max_pax": 396, "sens_vent": 1.3, "vitesse": 905},
    "A380": {"poids_vide": 277000, "conso_base": 8.0, "max_pax": 850, "sens_vent": 1.5, "vitesse": 945},
}
POIDS_PASSAGER = 80
POIDS_BAGAGE = 23
VENTS = list(range(0, 301, 10))
DIRECTIONS = ["head", "tail", "side"]
DISTANCES = [800, 1200, 1600, 2000]
PAX_LIST = [140, 160, 180, 200, 220, 240]
COULEURS = {"A320": "#1f77b4", "B737": "#2ca02c",
            "B777": "#d62728", "A380": "#9467bd"}


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
    return {"conso_L": conso_L, "conso_L_pax": conso_L / pax, "duree_h": distance / vitesse, "vitesse": vitesse}


def ymax_sequence(direction: str, distance: int, pax: int, metric: str) -> float:
    y_max = 0.0
    for vent in VENTS:
        for avion in AVIONS:
            etat = calcule_etat(avion, direction, vent, pax, distance)
            if etat:
                y_max = max(y_max, etat[metric])
    return (y_max * 1.12) if y_max > 0 else 1.0


def all_sequences():
    seqs = [{"direction": d, "distance": dist, "pax": pax}
            for d in DIRECTIONS for dist in DISTANCES for pax in PAX_LIST]
    if SHUFFLE_SEQUENCES == "1":
        random.shuffle(seqs)
    return seqs


_SEQ_LIST = all_sequences()
_SEQ_INDEX = 0


def next_sequence():
    global _SEQ_INDEX, _SEQ_LIST
    if not _SEQ_LIST:
        _SEQ_LIST = all_sequences()
        _SEQ_INDEX = 0
    seq = _SEQ_LIST[_SEQ_INDEX]
    _SEQ_INDEX = (_SEQ_INDEX + 1) % len(_SEQ_LIST)
    return seq


def render_one_video(out_dir=OUT_DIR):
    print(f"[RENDER] out_dir={out_dir}")
    os.makedirs(out_dir, exist_ok=True)
    assert os.path.isdir(
        out_dir), f"[ERR] Dossier sortie introuvable: {out_dir}"

    seq = next_sequence()
    direction, distance, pax = seq["direction"], seq["distance"], seq["pax"]
    print(
        f"[RENDER] sequence: direction={direction}, distance={distance}, pax={pax}")

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), dpi=100)
    ax_conso, ax_cpx, ax_duree = axes
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.set_xlim(0, max(VENTS))
    ax_conso.set_title("Conso totale (L) vs Vent")
    ax_conso.set_xlabel("Vent (km/h)")
    ax_conso.set_ylabel("Litres")
    ax_cpx.set_title("Conso par passager (L/pax) vs Vent")
    ax_cpx.set_xlabel("Vent (km/h)")
    ax_cpx.set_ylabel("L/pax")
    ax_duree.set_title("Durée estimée (h) vs Vent")
    ax_duree.set_xlabel("Vent (km/h)")
    ax_duree.set_ylabel("Heures")

    ax_conso.set_ylim(0, ymax_sequence(direction, distance, pax, "conso_L"))
    ax_cpx.set_ylim(0, ymax_sequence(direction, distance, pax, "conso_L_pax"))
    ax_duree.set_ylim(0, ymax_sequence(direction, distance, pax, "duree_h"))

    series = {"conso_L": {}, "conso_L_pax": {}, "duree_h": {}}
    wind_lines = {
        "conso_L": ax_conso.axvline(0, color="#444", lw=1.2, ls="--", alpha=0.6),
        "conso_L_pax": ax_cpx.axvline(0, color="#444", lw=1.2, ls="--", alpha=0.6),
        "duree_h": ax_duree.axvline(0, color="#444", lw=1.2, ls="--", alpha=0.6),
    }
    labels = {"conso_L": {}, "conso_L_pax": {}, "duree_h": {}}

    for avion, color in COULEURS.items():
        l1, = ax_conso.plot([], [], lw=2.4, color=color, label=avion)
        l2, = ax_cpx.plot([], [], lw=2.4, color=color, label=avion)
        l3, = ax_duree.plot([], [], lw=2.4, color=color, label=avion)
        series["conso_L"][avion] = {"x": [], "y": [], "line": l1}
        series["conso_L_pax"][avion] = {"x": [], "y": [], "line": l2}
        series["duree_h"][avion] = {"x": [], "y": [], "line": l3}
        labels["conso_L"][avion] = ax_conso.text(
            0, 0, "", color=color, fontsize=9, ha="left", va="center", alpha=0.8)
        labels["conso_L_pax"][avion] = ax_cpx.text(
            0, 0, "", color=color, fontsize=9, ha="left", va="center", alpha=0.8)
        labels["duree_h"][avion] = ax_duree.text(
            0, 0, "", color=color, fontsize=9, ha="left", va="center", alpha=0.8)

    ax_conso.legend(loc="upper left", frameon=False, fontsize=9)
    ax_cpx.legend(loc="upper left", frameon=False, fontsize=9)
    ax_duree.legend(loc="upper left", frameon=False, fontsize=9)

    fig.suptitle(
        f"Snapsac — {direction} | {distance} km | {pax} pax", fontsize=12, fontweight="bold")

    def update(frame_idx):
        vent = VENTS[frame_idx]
        best_model, best_cpx = None, float("inf")
        for avion in AVIONS:
            etat = calcule_etat(avion, direction, vent, pax, distance)
            if not etat:
                continue
            for metric, ax in (("conso_L", ax_conso), ("conso_L_pax", ax_cpx), ("duree_h", ax_duree)):
                value = etat[metric]
                s = series[metric][avion]
                s["x"].append(vent)
                s["y"].append(value)
                s["line"].set_data(s["x"], s["y"])
                labels[metric][avion].set_text(avion)
                labels[metric][avion].set_position((vent + 4, value))
            if etat["conso_L_pax"] < best_cpx:
                best_cpx = etat["conso_L_pax"]
                best_model = avion
        for metric in series:
            for avion, s in series[metric].items():
                s["line"].set_linewidth(3.2 if avion == best_model else 2.0)
                s["line"].set_alpha(1.0 if avion == best_model else 0.55)
            wind_lines[metric].set_xdata([vent, vent])
        fig.suptitle(
            f"Snapsac — {direction} | Vent {vent} km/h | {distance} km | {pax} pax — Best: {best_model}",
            fontsize=12, fontweight="bold"
        )
        return []

    fig.tight_layout(rect=(0, 0.03, 1, 0.95))

    try:
        anim = FuncAnimation(fig, update, frames=len(
            VENTS), interval=INTERVAL_MS, blit=False)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path_mp4 = os.path.join(
            out_dir, f"animation_{direction}_{distance}km_{pax}pax_{ts}.mp4")
        if writers.is_available("ffmpeg"):
            print("[RENDER] writing MP4:", out_path_mp4)
            writer = FFMpegWriter(
                fps=FPS, metadata={'artist': 'Kerosene-Flight-Optimizator'})
            anim.save(out_path_mp4, writer=writer, dpi=100)
            print("[RENDER] OK MP4:", out_path_mp4)
        else:
            out_path_gif = os.path.join(
                out_dir, f"animation_{direction}_{distance}km_{pax}pax_{ts}.gif")
            print("[RENDER] ffmpeg indisponible → GIF:", out_path_gif)
            anim.save(out_path_gif, writer="pillow", dpi=100)
            print("[RENDER] OK GIF:", out_path_gif)
    except Exception as e:
        print("[ERROR] render failed:", e, file=sys.stderr)
        raise
    finally:
        plt.close(fig)


def main():
    print("[MAIN] out_dir:", OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    while True:
        render_one_video(OUT_DIR)
        if LOOP_DELAY > 0:
            print(f"[MAIN] sleep {LOOP_DELAY}s…")
            time.sleep(LOOP_DELAY)
        else:
            break


if __name__ == "__main__":
    main()
