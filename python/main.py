import json
import datetime
from zoneinfo import ZoneInfo
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from arduino.app_utils import App, Bridge

print("Python ready", flush=True)

_lock = threading.Lock()

_state = {
    "lat": None,
    "long": None,
    "jour": None,
    "mois": None,
    "annee": None,
    "heure": None,
    "minute": None,
    "seconde": None,
    "numsat": None,
    "altitude": None,
}

def now_local_fr():
    # ex: 31/10/2026 14:22:29
    return datetime.datetime.now(ZoneInfo("Europe/Paris")).strftime("%d/%m/%Y %H:%M:%S")


def update_gps(lat, long, jour, mois, annee, heure, minute, seconde, numsat, altitude):
    with _lock:
        _state.update(
            lat = lat,
            long = long, 
            jour = jour, 
            mois = mois, 
            annee = annee,
            heure = heure,
            minute = minute, 
            seconde = seconde,
            numsat = numsat, 
            altitude = altitude,
        )

Bridge.provide("update_gps", update_gps)

def api_state():
    with _lock:
        payload = dict(_state)
    payload["now_local"] = now_local_fr()
    return payload

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/state":
            body = json.dumps(api_state(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass  # pas de logs à chaque requête

PORT = 8000
server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
print(f"Serveur JSON sur le port {PORT}", flush=True)

App.run()
