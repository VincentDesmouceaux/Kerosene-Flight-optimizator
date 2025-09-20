# server.py
import os
import io
import datetime
from flask import Flask, send_file, jsonify
from snapsac_render import render_one_video

app = Flask(__name__)
OUT_DIR = os.getenv("OUT_DIR", "/out")


@app.get("/")
def health():
    return jsonify(status="ok", build=os.getenv("BUILD_ID", "dev"))


@app.post("/render")
def render_now():
    os.makedirs(OUT_DIR, exist_ok=True)
    # <-- fais renvoyer le chemin dans ta fonction
    path = render_one_video(OUT_DIR)
    return jsonify(ok=True, path=path)


@app.get("/last")
def last_file():
    if not os.path.isdir(OUT_DIR):
        return jsonify(error="no out dir"), 404
    files = [os.path.join(OUT_DIR, f) for f in os.listdir(
        OUT_DIR) if f.endswith((".mp4", ".gif"))]
    if not files:
        return jsonify(error="no files"), 404
    latest = max(files, key=os.path.getmtime)
    return send_file(latest, as_attachment=False)
