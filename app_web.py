# app_web.py - Version corrigée
import time
import io
from flask import Flask, Response
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Backend non-interactif

app = Flask(__name__)


class AnimationStream:
    def __init__(self):
        self.frame_count = 0

    def generate_frame(self):
        try:
            # Créer une nouvelle figure à chaque frame
            fig, ax = plt.subplots(figsize=(10, 6), facecolor='black')

            # Animation exemple - à adapter avec votre code snapsac
            t = np.linspace(0, 4*np.pi, 100)
            phase = self.frame_count * 0.1
            x = np.sin(t + phase)
            y = np.cos(2*t + phase)

            ax.clear()
            ax.set_facecolor('black')
            ax.plot(x, y, 'cyan', linewidth=2)
            ax.set_xlim(-1.5, 1.5)
            ax.set_ylim(-1.5, 1.5)
            ax.set_title(
                f"Animation Live - Frame {self.frame_count}", color='white')
            ax.tick_params(colors='white')

            # Convertir en image
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png', dpi=80, bbox_inches='tight',
                        facecolor='black', edgecolor='none')
            img_buffer.seek(0)
            img_data = img_buffer.getvalue()

            self.frame_count += 1
            return img_data

        except Exception as e:
            print(f"Erreur génération frame: {e}")
            # Frame d'erreur
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, f"Erreur: {e}", ha='center', va='center')
            img_buffer = io.BytesIO()
            plt.savefig(img_buffer, format='png')
            img_buffer.seek(0)
            return img_buffer.getvalue()
        finally:
            plt.close('all')  # Nettoyer toutes les figures


animation = AnimationStream()


def generate_frames():
    while True:
        try:
            frame = animation.generate_frame()
            yield (b'--frame\r\n'
                   b'Content-Type: image/png\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.1)  # 10 FPS
        except Exception as e:
            print(f"Erreur dans generate_frames: {e}")
            time.sleep(1)


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Animation Live</title>
        <meta charset="utf-8">
        <style>
            body { 
                margin: 0; 
                background: #000;
                font-family: Arial, sans-serif;
                color: white;
            }
            .container { 
                display: flex; 
                flex-direction: column;
                justify-content: center; 
                align-items: center; 
                min-height: 100vh;
            }
            .video-container {
                border: 2px solid #00ffff;
                border-radius: 10px;
                padding: 10px;
                background: #111;
            }
            img { 
                max-width: 90vw; 
                max-height: 80vh; 
                display: block;
            }
            .info {
                margin-top: 20px;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎨 Animation en Direct</h1>
            <div class="video-container">
                <img src="/video_feed" alt="Live Animation Stream">
            </div>
            <div class="info">
                <p>Streaming live • FPS: 10 • <span id="frameCounter">Frame: 0</span></p>
            </div>
        </div>
        
        <script>
            let frameCount = 0;
            const img = document.querySelector('img');
            const counter = document.getElementById('frameCounter');
            
            img.onload = function() {
                frameCount++;
                counter.textContent = `Frame: ${frameCount}`;
            };
            
            img.onerror = function() {
                console.error('Erreur de chargement du stream');
            };
        </script>
    </body>
    </html>
    '''


@app.route('/health')
def health():
    return 'OK'


if __name__ == '__main__':
    print("Démarrage de l'application Flask...")
    print("Accédez à: http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
