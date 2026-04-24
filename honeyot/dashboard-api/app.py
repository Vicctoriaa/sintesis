#!/usr/bin/env python3
"""
app.py — Dashboard API · CT104 (10.1.1.37)
Recibe eventos del honeypot (VM203) via HTTP POST y los sirve
como API REST al dashboard HTML.

Despliegue: /opt/dashboard-api/app.py
Puerto:     5000
Servicio:   dashboard-api.service
"""

import json
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from functools import wraps
from collections import defaultdict

from flask import Flask, request, jsonify, g

# ─── Configuración ────────────────────────────────────────────────────────────

API_TOKEN   = "honeypot-soc-2026"          # Igual que en agent.py
DB_PATH     = "/opt/dashboard-api/events.db"
MAX_EVENTS  = 10_000                        # Máximo de eventos en BD
CORS_ORIGIN = "*"                           # Dashboard en mismo servidor

app = Flask(__name__)

# ─── Base de datos SQLite ─────────────────────────────────────────────────────

DB_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT    NOT NULL,
    timestamp   TEXT,
    level       TEXT,
    service     TEXT,
    action      TEXT,
    src_ip      TEXT,
    src_port    INTEGER,
    data        TEXT    NOT NULL   -- JSON completo del evento
);

-- Índice principal: la mayoría de queries filtran por ventana temporal
CREATE INDEX IF NOT EXISTS idx_received
    ON events(received_at);

-- Índices compuestos para las queries más frecuentes en /stats y /events
-- (received_at, service) cubre: WHERE received_at > ? AND service = ?
CREATE INDEX IF NOT EXISTS idx_received_service
    ON events(received_at, service);

-- (received_at, action) cubre: brute_force count, login_attempt count
CREATE INDEX IF NOT EXISTS idx_received_action
    ON events(received_at, action);

-- (received_at, src_ip) cubre: top IPs y unique_ips en ventana
CREATE INDEX IF NOT EXISTS idx_received_ip
    ON events(received_at, src_ip);

-- Índice simple para filtros individuales en /events
CREATE INDEX IF NOT EXISTS idx_level    ON events(level);
CREATE INDEX IF NOT EXISTS idx_src_ip   ON events(src_ip);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
    print(f"[init] Base de datos inicializada: {DB_PATH}")


# Contador de inserts para limpieza lazy
_insert_count = 0
_CLEANUP_EVERY = 100   # ejecutar limpieza cada N inserts


def insert_event(event: dict):
    """
    Inserta un evento en la BD.
    La limpieza de eventos antiguos se ejecuta cada CLEANUP_EVERY inserts
    en lugar de en cada INSERT — reduce la carga en scans masivos.
    """
    global _insert_count
    received = event.get("received_at") or datetime.now(timezone.utc).isoformat()
    # Normalizar: quitar offset para comparación string correcta con SQLite
    received = received.replace("+00:00", "").replace("Z", "").strip()

    with DB_LOCK:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """INSERT INTO events
                   (received_at, timestamp, level, service, action, src_ip, src_port, data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    received,
                    event.get("timestamp"),
                    event.get("level"),
                    event.get("service"),
                    event.get("action"),
                    event.get("src_ip"),
                    event.get("src_port"),
                    json.dumps(event),
                ),
            )
            _insert_count += 1
            # Limpieza lazy: solo cada CLEANUP_EVERY inserts
            if _insert_count % _CLEANUP_EVERY == 0:
                conn.execute(
                    """DELETE FROM events WHERE id NOT IN (
                           SELECT id FROM events ORDER BY id DESC LIMIT ?
                       )""",
                    (MAX_EVENTS,),
                )


# ─── Autenticación ────────────────────────────────────────────────────────────

def require_token(f):
    """Decorador: requiere X-Agent-Token en las peticiones POST del agente."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Agent-Token", "")
        if token != API_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ─── CORS ─────────────────────────────────────────────────────────────────────

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = CORS_ORIGIN
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Agent-Token"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.route("/events", methods=["POST"])
@require_token
def receive_event():
    """Recibe un evento del agente (VM203)."""
    try:
        event = request.get_json(force=True, silent=True)
        if not event or not isinstance(event, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        insert_event(event)
        return jsonify({"ok": True}), 200
    except Exception as e:
        app.logger.error("Error insertando evento: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/events", methods=["GET"])
def get_events():
    """
    Devuelve los últimos eventos con filtros opcionales.

    Query params:
      limit    int    — máximo de eventos (default 100, max 1000)
      service  str    — filtrar por servicio (ssh, http, ftp, smb, rdp, https)
      action   str    — filtrar por acción
      level    str    — filtrar por nivel (INFO, WARNING, ERROR)
      src_ip   str    — filtrar por IP origen
      since    str    — ISO8601, solo eventos posteriores a esta fecha
    """
    try:
        limit   = min(int(request.args.get("limit", 100)), 1000)
        service = request.args.get("service")
        action  = request.args.get("action")
        level   = request.args.get("level")
        src_ip  = request.args.get("src_ip")
        since   = request.args.get("since")

        query  = "SELECT data FROM events WHERE 1=1"
        params = []

        if service: query += " AND service = ?";  params.append(service)
        if action:  query += " AND action = ?";   params.append(action)
        if level:   query += " AND level = ?";    params.append(level)
        if src_ip:  query += " AND src_ip = ?";   params.append(src_ip)
        if since:
            # SQLite almacena timestamps sin offset; normalizar quitando +00:00/Z
            since_norm = since.replace('+00:00', '').replace('Z', '').strip()
            query += " AND received_at > ?"
            params.append(since_norm)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        db = get_db()
        rows = db.execute(query, params).fetchall()
        events = [json.loads(row["data"]) for row in rows]
        return jsonify(events), 200

    except Exception as e:
        app.logger.error("Error en GET /events: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/stats", methods=["GET"])
def get_stats():
    """
    Devuelve estadísticas agregadas para el dashboard.

    Query params:
      hours  int  — ventana temporal en horas (default 24)
    """
    try:
        hours = int(request.args.get("hours", 24))
        since_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        since = since_dt.strftime('%Y-%m-%dT%H:%M:%S')  # sin offset para SQLite

        db = get_db()

        # Total eventos en ventana
        total = db.execute(
            "SELECT COUNT(*) FROM events WHERE received_at > ?", (since,)
        ).fetchone()[0]

        # Por servicio
        by_service = {}
        for row in db.execute(
            "SELECT service, COUNT(*) as n FROM events WHERE received_at > ? GROUP BY service",
            (since,),
        ):
            by_service[row["service"] or "unknown"] = row["n"]

        # Por acción
        by_action = {}
        for row in db.execute(
            "SELECT action, COUNT(*) as n FROM events WHERE received_at > ? GROUP BY action",
            (since,),
        ):
            by_action[row["action"] or "unknown"] = row["n"]

        # Por nivel
        by_level = {}
        for row in db.execute(
            "SELECT level, COUNT(*) as n FROM events WHERE received_at > ? GROUP BY level",
            (since,),
        ):
            by_level[row["level"] or "INFO"] = row["n"]

        # Top IPs (top 20)
        top_ips = []
        for row in db.execute(
            """SELECT src_ip, COUNT(*) as hits FROM events
               WHERE received_at > ? AND src_ip IS NOT NULL
               GROUP BY src_ip ORDER BY hits DESC LIMIT 20""",
            (since,),
        ):
            top_ips.append({"ip": row["src_ip"], "hits": row["hits"]})

        # Brute force count
        brute_force = db.execute(
            "SELECT COUNT(*) FROM events WHERE received_at > ? AND action = 'brute_force'",
            (since,),
        ).fetchone()[0]

        # Login attempts
        login_attempts = db.execute(
            "SELECT COUNT(*) FROM events WHERE received_at > ? AND action = 'login_attempt'",
            (since,),
        ).fetchone()[0]

        # Eventos por hora (últimas 24h para el gráfico de tráfico)
        # Formato: "2026-04-23T14:00:00Z" — debe coincidir exactamente con
        # lo que construye api.js: d.toISOString().slice(0,14) + "00:00Z"
        # SQLite strftime sobre timestamps ISO devuelve UTC directamente.
        by_hour_raw = {}
        for row in db.execute(
            """SELECT strftime('%Y-%m-%dT%H:00:00Z', received_at) as hour,
                      COUNT(*) as n
               FROM events
               WHERE received_at > ?
               GROUP BY hour
               ORDER BY hour""",
            (since,),
        ):
            if row["hour"]:  # descartar NULL si received_at tiene formato raro
                by_hour_raw[row["hour"]] = row["n"]

        # Rellenar huecos: garantizar las 24 claves aunque no haya eventos
        by_hour = {}
        now_utc = datetime.now(timezone.utc)
        for i in range(23, -1, -1):
            slot_dt = now_utc - timedelta(hours=i)
            key = slot_dt.strftime("%Y-%m-%dT%H:00:00Z")
            by_hour[key] = by_hour_raw.get(key, 0)

        # IPs únicas reales en la ventana (no solo el tamaño del top)
        unique_ips_row = db.execute(
            "SELECT COUNT(DISTINCT src_ip) FROM events WHERE received_at > ? AND src_ip IS NOT NULL",
            (since,),
        ).fetchone()
        unique_ips = unique_ips_row[0] if unique_ips_row else 0

        # Último evento
        last_row = db.execute(
            "SELECT received_at FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        last_event = last_row["received_at"] if last_row else None

        # Total acumulado
        total_all = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]

        return jsonify({
            "window_hours":   hours,
            "since":          since,
            "total":          total,
            "total_all":      total_all,
            "by_service":     by_service,
            "by_action":      by_action,
            "by_level":       by_level,
            "top_ips":        top_ips,
            "unique_ips":     unique_ips,
            "brute_force":    brute_force,
            "login_attempts": login_attempts,
            "by_hour":        by_hour,
            "last_event":     last_event,
        }), 200

    except Exception as e:
        app.logger.error("Error en GET /stats: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Endpoint de health check."""
    try:
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return jsonify({
            "status":      "ok",
            "total_events": total,
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500



@app.route("/export", methods=["GET"])
def export_events():
    """
    Exporta eventos a CSV o JSON descargable.

    Query params:
      format   str   — "csv" (default) o "json"
      hours    int   — ventana temporal en horas (default 24, 0 = todo)
      service  str   — filtrar por servicio
      action   str   — filtrar por acción
      level    str   — filtrar por nivel
      src_ip   str   — filtrar por IP
      limit    int   — máximo de filas (default 10000)
    """
    import csv, io
    from flask import Response

    try:
        fmt     = request.args.get("format", "csv").lower()
        hours   = int(request.args.get("hours", 24))
        service = request.args.get("service")
        action  = request.args.get("action")
        level   = request.args.get("level")
        src_ip  = request.args.get("src_ip")
        limit   = min(int(request.args.get("limit", 10_000)), 50_000)

        query  = "SELECT data FROM events WHERE 1=1"
        params = []

        if hours > 0:
            since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
            query += " AND received_at > ?"
            params.append(since)

        if service: query += " AND service = ?"; params.append(service)
        if action:  query += " AND action = ?";  params.append(action)
        if level:   query += " AND level = ?";   params.append(level)
        if src_ip:  query += " AND src_ip = ?";  params.append(src_ip)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        db   = get_db()
        rows = db.execute(query, params).fetchall()
        events = [json.loads(r["data"]) for r in rows]

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"honeypot_events_{ts}"

        # ── JSON ──────────────────────────────────────────────────────────
        if fmt == "json":
            out = json.dumps(events, indent=2, ensure_ascii=False)
            return Response(
                out,
                mimetype="application/json",
                headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
            )

        # ── CSV ───────────────────────────────────────────────────────────
        # Columnas fijas primero, luego campos extra del JSON
        FIXED_COLS = [
            "received_at", "timestamp", "level", "service", "action",
            "src_ip", "src_port", "hostname", "environment", "vlan",
            "username", "password", "result", "command",
            "path", "method", "user_agent", "file", "direction",
            "attempt_count", "window_seconds", "message",
        ]

        # Recopilar todas las claves presentes para columnas extra
        extra_keys: set = set()
        for ev in events:
            extra_keys.update(ev.keys())
        extra_cols = sorted(extra_keys - set(FIXED_COLS))
        columns = FIXED_COLS + extra_cols

        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=columns, extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for ev in events:
            writer.writerow({col: ev.get(col, "") for col in columns})

        return Response(
            buf.getvalue(),
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}.csv"',
                "X-Total-Events": str(len(events)),
            },
        )

    except Exception as e:
        app.logger.error("Error en GET /export: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/db/stats", methods=["GET"])
def db_stats():
    """Información sobre el estado de la base de datos."""
    import os
    try:
        db = get_db()

        total = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        oldest = db.execute("SELECT received_at FROM events ORDER BY id ASC LIMIT 1").fetchone()
        newest = db.execute("SELECT received_at FROM events ORDER BY id DESC LIMIT 1").fetchone()

        # Tamaño del fichero en disco
        db_size_bytes = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        db_size_mb    = round(db_size_bytes / 1_048_576, 2)

        # Distribución por servicio
        by_service = {}
        for row in db.execute("SELECT service, COUNT(*) as n FROM events GROUP BY service"):
            by_service[row["service"] or "unknown"] = row["n"]

        # Distribución por nivel
        by_level = {}
        for row in db.execute("SELECT level, COUNT(*) as n FROM events GROUP BY level"):
            by_level[row["level"] or "INFO"] = row["n"]

        return jsonify({
            "total_events":  total,
            "max_events":    MAX_EVENTS,
            "usage_pct":     round(total / MAX_EVENTS * 100, 1),
            "oldest_event":  oldest["received_at"] if oldest else None,
            "newest_event":  newest["received_at"] if newest else None,
            "db_size_mb":    db_size_mb,
            "by_service":    by_service,
            "by_level":      by_level,
        }), 200

    except Exception as e:
        app.logger.error("Error en GET /db/stats: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/geo", methods=["GET"])
def get_geo():
    """
    Geolocaliza las top IPs atacantes de las últimas 24h.
    Usa geoip2 + GeoLite2-City.mmdb si está disponible,
    con fallback graceful si no lo está.

    Instalación (opcional):
      pip install geoip2 --break-system-packages
      # Descargar GeoLite2-City.mmdb desde https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
      # Copiar a /opt/dashboard-api/GeoLite2-City.mmdb

    Respuesta: lista de { ip, hits, lat, lon, country, country_iso, city, flag, sev }
    """
    try:
        hours = int(request.args.get("hours", 24))
        since_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        since = since_dt.strftime("%Y-%m-%dT%H:%M:%S")

        db = get_db()
        rows = db.execute(
            """SELECT src_ip, COUNT(*) as hits
               FROM events
               WHERE received_at > ? AND src_ip IS NOT NULL
               GROUP BY src_ip ORDER BY hits DESC LIMIT 50""",
            (since,),
        ).fetchall()

        # Intentar cargar geoip2 + base de datos
        geo_reader = None
        MMDB_PATH = "/opt/dashboard-api/GeoLite2-City.mmdb"
        try:
            import geoip2.database, os
            if os.path.exists(MMDB_PATH):
                geo_reader = geoip2.database.Reader(MMDB_PATH)
        except ImportError:
            pass

        FLAG_MAP = {
            "CN":"\U0001F1E8\U0001F1F3","RU":"\U0001F1F7\U0001F1FA","US":"\U0001F1FA\U0001F1F8",
            "DE":"\U0001F1E9\U0001F1EA","NL":"\U0001F1F3\U0001F1F1","FR":"\U0001F1EB\U0001F1F7",
            "GB":"\U0001F1EC\U0001F1E7","BR":"\U0001F1E7\U0001F1F7","KR":"\U0001F1F0\U0001F1F7",
            "JP":"\U0001F1EF\U0001F1F5","IN":"\U0001F1EE\U0001F1F3","UA":"\U0001F1FA\U0001F1E6",
            "TR":"\U0001F1F9\U0001F1F7","PL":"\U0001F1F5\U0001F1F1","IT":"\U0001F1EE\U0001F1F9",
            "ES":"\U0001F1EA\U0001F1F8","IR":"\U0001F1EE\U0001F1F7","VN":"\U0001F1FB\U0001F1F3",
            "RO":"\U0001F1F7\U0001F1F4","HK":"\U0001F1ED\U0001F1F0","SG":"\U0001F1F8\U0001F1EC",
            "TW":"\U0001F1F9\U0001F1FC","AR":"\U0001F1E6\U0001F1F7","MX":"\U0001F1F2\U0001F1FD",
            "ZA":"\U0001F1FF\U0001F1E6","TH":"\U0001F1F9\U0001F1ED","ID":"\U0001F1EE\U0001F1E9",
        }

        result = []
        for row in rows:
            ip, hits = row["src_ip"], row["hits"]
            if   hits > 50: sev = "critico"
            elif hits > 20: sev = "alto"
            elif hits > 5:  sev = "medio"
            else:            sev = "bajo"

            entry = {
                "ip": ip, "hits": hits, "sev": sev,
                "lat": 0.0, "lon": 0.0,
                "country": "Desconocido", "country_iso": "",
                "city": "", "flag": "\U0001F310",
            }

            if geo_reader:
                try:
                    rec = geo_reader.city(ip)
                    entry["lat"]         = rec.location.latitude  or 0.0
                    entry["lon"]         = rec.location.longitude or 0.0
                    entry["country"]     = rec.country.name or "Desconocido"
                    entry["country_iso"] = rec.country.iso_code or ""
                    entry["city"]        = rec.city.name or ""
                    entry["flag"]        = FLAG_MAP.get(rec.country.iso_code or "", "\U0001F310")
                except Exception:
                    pass

            result.append(entry)

        if geo_reader:
            geo_reader.close()

        return jsonify(result), 200

    except Exception as e:
        app.logger.error("Error en GET /geo: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    return jsonify({"service": "honeypot-dashboard-api", "version": "1.0"}), 200


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("[api] Servidor arrancando en 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
