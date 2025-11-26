# app_stream.py - Version optimisée
import time
import threading
import io
import numpy as np
from matplotlib.animation import FuncAnimation
import matplotlib.pyplot as plt
from flask import Flask, Response, render_template_string
import matplotlib
matplotlib.use('Agg')

app = Flask(__name__)

# Template HTML amélioré
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Animation Live Streaming</title>
    <style>
        body { 
            margin: 0; 
            background: linear-gradient(45deg, #0f0f23, #1a1a2e);
            font-family: Arial, sans-serif;
            overflow: hidden;
        }
        .container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            color: white;
        }
        .video-container {
            border: 3px solid #00ffff;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.5);
            overflow: hidden;
        }
        .stats {
            margin-top: 20px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 Animation Live</h1>
        <div class="video-container">
            <img src="/video_feed" alt="Live Animation">
        </div>
        <div class="stats">
            <p>🔄 Stream en direct | 📊 Frame: <span id="frameCount">0</span></p>
        </div>
    </div>
    
    <script>
        let frameCount = 0;
        const img = document.querySelector('img');
        const frameElement = document.getElementById('frameCount');
        
        img.onload = function() {
            frameCount++;
            frameElement.textContent = frameCount;
        };
    </script>
</body>
</html>
'''


class AdvancedAnimation:
    def __init__(self):
        self.frame_num = 0
        self.fig, self.ax = plt.subplots(figsize=(12, 7))
        self.fig.patch.set_facecolor('#0f0f23')
        self.ax.set_facecolor('#1a1a2e')

    def update_frame(self):
        # Votre logique d'animation ici
        self.ax.clear()

        # Exemple d'animation complexe
        t = np.linspace(0, 4*np.pi, 200)
        phase = self.frame_num * 0.05

        # Créer des motifs animés
        for i in range(5):
            x = np.sin(t + phase + i) * np.cos(t * 2)
            y = np.cos(t + phase + i) * np.sin(t * 3)
            colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#feca57']
            self.ax.plot(x, y, color=colors[i], linewidth=2, alpha=0.8)

        self.ax.set_xlim(-1.5, 1.5)
        self.ylim = (-1.5, 1.5)
        self.ax.set_title(f'Animation Live - Frame {self.frame_num}',
                          color='white', fontsize=14, pad=20)
        self.ax.tick_params(colors='white')

        # Convertir en image
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=80,
                    bbox_inches='tight', facecolor='#0f0f23')
        img_buffer.seek(0)

        self.frame_num += 1
        return img_buffer.getvalue()


animator = AdvancedAnimation()


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/video_feed')
def video_feed():
    def generate():
        while True:
            frame = animator.update_frame()
            yield (b'--frame\r\n'
                   b'Content-Type: image/png\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.067)  # ~15 FPS

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
