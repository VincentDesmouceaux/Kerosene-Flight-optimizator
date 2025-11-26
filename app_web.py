# app_web.py - Version optimisée sans dépendances lourdes
import time
import io
from flask import Flask, Response
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

app = Flask(__name__)


class AnimationStream:
    def __init__(self):
        self.frame_count = 0

    def generate_frame(self):
        try:
            # Créer une figure simple
            fig, ax = plt.subplots(figsize=(10, 6), dpi=80)

            # Votre animation - version simplifiée
            t = np.linspace(0, 4*np.pi, 100)
            phase = self.frame_count * 0.1

            # Animation basique
            x = np.sin(t + phase)
            y = np.cos(2*t + phase)

            ax.clear()
            ax.plot(x, y, 'b-', linewidth=2)
            ax.set_xlim(-1.5, 1.5)
            ax.set_ylim(-1.5, 1.5)
            ax.set_title(f"Animation Live - Frame {self.frame_count}")
            ax.grid(True, alpha=0.3)

            # Convertir en image
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', bbox_inches='tight')
            img_buffer.seek(0)
            img_data = img_buffer.getvalue()

            self.frame_count += 1
            return img_data

        except Exception as e:
            print(f"Erreur: {e}")
            # Fallback simple
            fig, ax = plt.subplots()
            ax.text(0.5, 0.5, "Animation en cours...",
                    ha='center', va='center')
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png')
            img_buffer.seek(0)
            return img_buffer.getvalue()
        finally:
            plt.close('all')


animation = AnimationStream()


def generate_frames():
    while True:
        frame = animation.generate_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/png\r\n\r\n' + frame + b'\r\n')
        time.sleep(0.1)


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
        <title>Animation Live</title>
        <style>
            body { margin: 0; background: #f0f0f0; font-family: Arial; }
            .container { text-align: center; padding: 20px; }
            img { max-width: 800px; border: 2px solid #333; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Animation en Direct</h1>
            <img src="/video_feed">
        </div>
    </body>
    </html>
    '''


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
