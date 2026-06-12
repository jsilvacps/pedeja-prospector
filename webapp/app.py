"""
PedeJá Prospector – Web App (PWA)
Flask backend para uso no celular via Wi-Fi local.
"""
import csv
import io
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, render_template, request, send_file, stream_with_context

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent          # raiz do projeto
IS_CLOUD = os.getenv("RENDER") == "true" or os.getenv("RAILWAY_ENVIRONMENT") is not None

if IS_CLOUD:
    # Nuvem: usa /tmp (ephemeral, mas suficiente para sessão)
    APP_DIR = Path("/tmp/PedeJaProspector")
else:
    APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "PedeJaProspector"

DB_PATH     = APP_DIR / "leads.db"
CONFIG_PATH = APP_DIR / "config.json"
MUNI_PATH   = BASE_DIR / "assets" / "municipios.json"
APP_DIR.mkdir(parents=True, exist_ok=True)

# ── Flask ──────────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["JSON_ENSURE_ASCII"] = False

# ── Shared data ────────────────────────────────────────────────────────────────
@dataclass
class Lead:
    nome: str
    endereco: str = ""
    telefone: str = ""
    site: str = ""
    maps_url: str = ""
    cidade: str = ""
    estado: str = ""
    segmento: str = ""
    place_id: str = ""

def load_config() -> dict:
    cfg = {}
    # Variável de ambiente tem prioridade (produção/nuvem)
    env_key = os.getenv("GOOGLE_API_KEY", "")
    if env_key:
        cfg["api_key"] = env_key
    if CONFIG_PATH.exists():
        try:
            file_cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            # Mescla: env var sobrepõe arquivo em produção
            if not env_key and file_cfg.get("api_key"):
                cfg["api_key"] = file_cfg["api_key"]
            if file_cfg.get("message"):
                cfg["message"] = file_cfg["message"]
        except Exception:
            pass
    return cfg

def save_config(data: dict):
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT, endereco TEXT, telefone TEXT, site TEXT,
        maps_url TEXT, cidade TEXT, estado TEXT, segmento TEXT,
        place_id TEXT UNIQUE, created_at TEXT
    )""")
    conn.commit(); conn.close()

def save_leads_db(leads: list[Lead]):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for l in leads:
        cur.execute("""INSERT OR IGNORE INTO leads
            (nome,endereco,telefone,site,maps_url,cidade,estado,segmento,place_id,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (l.nome,l.endereco,l.telefone,l.site,l.maps_url,
             l.cidade,l.estado,l.segmento,l.place_id,
             datetime.now().isoformat(timespec="seconds")))
    conn.commit(); conn.close()

def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits: return ""
    if digits.startswith("55"): return digits
    if len(digits) in (10, 11): return "55" + digits
    return digits

def load_municipios() -> dict:
    if MUNI_PATH.exists():
        return json.loads(MUNI_PATH.read_text(encoding="utf-8"))
    return {}

MUNICIPIOS = load_municipios()
init_db()

# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/estados")
def api_estados():
    return jsonify(sorted(MUNICIPIOS.keys()))

@app.route("/api/cidades/<estado>")
def api_cidades(estado):
    return jsonify(MUNICIPIOS.get(estado.upper(), []))

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "POST":
        data = request.get_json()
        cfg = load_config()
        if "api_key" in data:
            cfg["api_key"] = data["api_key"]
        if "message" in data:
            cfg["message"] = data["message"]
        save_config(cfg)
        return jsonify({"ok": True})
    return jsonify(load_config())

@app.route("/api/search")
def api_search():
    """SSE endpoint — envia progresso + leads em tempo real."""
    api_key  = request.args.get("api_key", "").strip()
    segmento = request.args.get("segmento", "").strip()
    estado   = request.args.get("estado", "").strip()
    cidade   = request.args.get("cidade", "").strip()
    try:
        max_r = int(request.args.get("max", 20))
    except ValueError:
        max_r = 20
    try:
        lat = float(request.args.get("lat", ""))
        lng = float(request.args.get("lng", ""))
        has_location = True
    except (ValueError, TypeError):
        lat = lng = 0.0
        has_location = False

    def generate():
        def send(event: str, data):
            payload = json.dumps(data, ensure_ascii=False)
            yield f"event: {event}\ndata: {payload}\n\n"

        if not api_key:
            yield from send("error", {"msg": "API Key não informada."})
            return
        if not segmento:
            yield from send("error", {"msg": "Informe o segmento."})
            return

        leads: list[dict] = []
        next_token = None

        if has_location:
            base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                "location": f"{lat},{lng}",
                "rankby": "distance",
                "keyword": segmento,
                "key": api_key,
                "language": "pt-BR",
            }
        else:
            base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {"query": f"{segmento} em {cidade} {estado} Brasil",
                      "key": api_key, "language": "pt-BR", "region": "br"}

        try:
            while len(leads) < max_r:
                if next_token:
                    time.sleep(2.2)
                    params = {"pagetoken": next_token, "key": api_key,
                              "language": "pt-BR", "region": "br"}

                pct = min(90, int(len(leads) / max(1, max_r) * 100))
                yield from send("progress", {"pct": pct, "msg": "Buscando estabelecimentos…"})

                resp = requests.get(base_url, params=params, timeout=25)
                data = resp.json()
                status = data.get("status")
                if status not in ("OK", "ZERO_RESULTS"):
                    yield from send("error", {"msg": data.get("error_message") or status})
                    return
                if status == "ZERO_RESULTS":
                    break

                for item in data.get("results", []):
                    if len(leads) >= max_r:
                        break
                    place_id = item.get("place_id", "")
                    details  = _get_details(place_id, api_key)
                    lead = {
                        "nome":     details.get("name") or item.get("name", ""),
                        "endereco": details.get("formatted_address") or item.get("formatted_address", ""),
                        "telefone": details.get("formatted_phone_number", ""),
                        "site":     details.get("website", ""),
                        "maps_url": details.get("url", ""),
                        "cidade":   cidade,
                        "estado":   estado,
                        "segmento": segmento,
                        "place_id": place_id,
                    }
                    leads.append(lead)
                    pct2 = min(95, int(len(leads) / max(1, max_r) * 100))
                    yield from send("lead", {"pct": pct2, "lead": lead})

                next_token = data.get("next_page_token")
                if not next_token:
                    break

            # Save to DB
            db_leads = [Lead(**l) for l in leads]
            save_leads_db(db_leads)
            yield from send("done", {"total": len(leads)})

        except Exception as exc:
            yield from send("error", {"msg": str(exc)})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

def _get_details(place_id: str, api_key: str) -> dict:
    if not place_id:
        return {}
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/details/json",
            params={"place_id": place_id,
                    "fields": "name,formatted_address,formatted_phone_number,website,url",
                    "key": api_key, "language": "pt-BR"},
            timeout=25,
        )
        data = resp.json()
        return data.get("result", {}) if data.get("status") == "OK" else {}
    except Exception:
        return {}

@app.route("/api/leads")
def api_leads():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM leads ORDER BY created_at DESC LIMIT 200"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/export/csv")
def api_export_csv():
    leads_data = request.args.get("data", "")
    if not leads_data:
        return "Sem dados", 400
    leads = json.loads(leads_data)
    if not leads:
        return "Sem leads", 400

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=leads[0].keys(), delimiter=";")
    writer.writeheader()
    writer.writerows(leads)
    output.seek(0)

    return Response(
        "﻿" + output.getvalue(),   # BOM para Excel
        mimetype="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=leads_pedeja.csv"},
    )

if __name__ == "__main__":
    import socket
    host = "0.0.0.0"
    port = int(os.getenv("PORT", 5000))

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    print("\n" + "═" * 52)
    print("  PedeJá Prospector  –  Web App")
    print("═" * 52)
    print(f"  💻  PC:      http://localhost:{port}")
    print(f"  📱  Celular: http://{local_ip}:{port}")
    print("  (celular e PC precisam estar no mesmo Wi-Fi)")
    print("═" * 52)
    print("  Pressione Ctrl+C para encerrar.\n")

    app.run(host=host, port=port, debug=False, threaded=True)
