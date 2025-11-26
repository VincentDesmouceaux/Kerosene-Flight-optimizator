import os
import sys
import subprocess

mode = os.getenv("MODE", "gui").lower()
os.environ.setdefault("BUILD_ID", os.getenv("BUILD_ID", "dev"))

if mode == "gui":
    os.environ.setdefault("MPLBACKEND", "TkAgg")
    print(
        f"[LAUNCH] MODE=gui → snapsac_gui.py  (BUILD {os.getenv('BUILD_ID')})", flush=True)
    sys.exit(subprocess.call([sys.executable, "snapsac_gui.py"]))
elif mode == "render":
    os.environ.setdefault("MPLBACKEND", "Agg")
    print(
        f"[LAUNCH] MODE=render → snapsac_render.py  (BUILD {os.getenv('BUILD_ID')})", flush=True)
    sys.exit(subprocess.call([sys.executable, "snapsac_render.py"]))
else:
    print(
        f"[LAUNCH] MODE inconnu: {mode}  (utiliser 'gui' ou 'render')", file=sys.stderr)
    sys.exit(2)
