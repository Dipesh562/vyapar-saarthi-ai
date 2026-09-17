from flask import Blueprint, render_template, jsonify, Response

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@main_bp.route('/manifest.json', methods=['GET'])
def manifest():
    manifest_data = {
        "name": "Vyapar Saarthi - AI Kirana Assistant",
        "short_name": "VyaparSaarthi",
        "description": "Voice-first multilingual business assistant for kirana store owners",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#0ea5e9",
        "icons": [
            {
                "src": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "https://cdn-icons-png.flaticon.com/512/3135/3135715.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return jsonify(manifest_data)

@main_bp.route('/sw.js', methods=['GET'])
def service_worker():
    sw_code = """
// Network-first Service Worker for Vyapar Saarthi
self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', event => {
    // Network-first for all API and HTML page requests
    event.respondWith(
        fetch(event.request).catch(err => {
            console.log('Network request failed, falling back to cache if available:', event.request.url);
            return caches.match(event.request);
        })
    );
});
"""
    return Response(sw_code, mimetype='application/javascript')
