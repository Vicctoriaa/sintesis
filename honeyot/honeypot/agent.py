#!/usr/bin/env python3
"""
agent.py — Honeypot VM203
Lee /var/log/honeypot/honeypot.log en tiempo real y envía cada evento
nuevo a la API central (CT104) mediante HTTP POST.

Despliegue: /opt/honeypot/agent.py
Servicio:   honeypot-agent.service

Mejoras v2:
  - Throttling por (service, src_ip, action): máx THROTTLE_MAX eventos
    idénticos por ventana THROTTLE_WINDOW segundos. Evita saturar la API
    y SQLite durante scans masivos o floods de conexiones.
  - Deduplicación estricta en ventana de 1s: mismo (service, src_ip,
    action, username) dentro de 1 segundo → se descarta el duplicado.
    Captura el caso de clientes SSH que reenvían el mismo intento.
  - Métricas de tasa: el health check loguea eventos/min procesados,
    descartados por throttle y descartados por dedup.
  - El resto de la lógica (cola, retry, rotación de log) permanece igual.
"""

import json
import time
import os
import logging
import threading
from collections import deque, defaultdict
from datetime import datetime, timezone

import urllib.request
import urllib.error

# ─── Configuración ────────────────────────────────────────────────────────────

LOG_FILE    = "/var/log/honeypot/honeypot.log"
API_URL     = "http://192.168.1.112:5000/events"
API_TOKEN   = "honeypot-soc-2026"
RETRY_MAX   = 5
RETRY_DELAY = 2.0
QUEUE_MAX   = 500
POLL_SLEEP  = 0.2

# Throttling: máximo de eventos con la misma (service, src_ip, action)
# dentro de una ventana deslizante. Protege ante scans masivos.
THROTTLE_WINDOW = 10       # segundos
THROTTLE_MAX    = 5        # eventos permitidos por ventana

# Deduplicación: descarta eventos idénticos en menos de DEDUP_WINDOW segundos.
# Clave: (service, src_ip, action, username, path)
DEDUP_WINDOW    = 1.0      # segundos

# ─── Logging del propio agente ────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [agent] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/var/log/honeypot/agent.log"),
    ]
)
log = logging.getLogger("agent")

# ─── Cola en memoria ──────────────────────────────────────────────────────────

queue: deque = deque(maxlen=QUEUE_MAX)
queue_lock  = threading.Lock()

# ─── Throttling ───────────────────────────────────────────────────────────────
# { (service, src_ip, action) -> deque[timestamp_monotonic] }
_throttle: dict = defaultdict(lambda: deque())
_throttle_lock  = threading.Lock()

# ─── Deduplicación ────────────────────────────────────────────────────────────
# { dedup_key -> last_seen_monotonic }
_dedup: dict = {}
_dedup_lock  = threading.Lock()

# ─── Métricas internas ────────────────────────────────────────────────────────
_stats = {
    "processed":  0,   # eventos enviados a cola
    "throttled":  0,   # descartados por throttle
    "deduped":    0,   # descartados por deduplicación
    "since":      time.monotonic(),
}
_stats_lock = threading.Lock()


def _throttle_check(event: dict) -> bool:
    """
    Devuelve True si el evento debe enviarse, False si debe descartarse.
    Permite hasta THROTTLE_MAX eventos de la misma (service, src_ip, action)
    en THROTTLE_WINDOW segundos. Los eventos de acción 'brute_force' y
    'command' nunca se throttlean (siempre se envían).
    """
    action = event.get("action", "")
    # Acciones de alta prioridad: nunca throttlear
    if action in ("brute_force", "command", "port_scan",
                  "credential_stuffing", "decoy_file_access"):
        return True

    key = (
        event.get("service", ""),
        event.get("src_ip", ""),
        action,
    )
    now = time.monotonic()

    with _throttle_lock:
        q = _throttle[key]
        # Limpiar entradas fuera de la ventana
        while q and (now - q[0]) > THROTTLE_WINDOW:
            q.popleft()

        if len(q) >= THROTTLE_MAX:
            return False   # throttleado

        q.append(now)
        return True


def _dedup_check(event: dict) -> bool:
    """
    Devuelve True si el evento es nuevo, False si es duplicado reciente.
    Clave de deduplicación: (service, src_ip, action, username, path, command).
    """
    key = (
        event.get("service", ""),
        event.get("src_ip", ""),
        event.get("action", ""),
        event.get("username", ""),
        event.get("path", ""),
        event.get("command", ""),
    )
    now = time.monotonic()

    with _dedup_lock:
        last = _dedup.get(key)
        if last is not None and (now - last) < DEDUP_WINDOW:
            return False   # duplicado
        _dedup[key] = now

        # Limpiar entradas antiguas cada ~1000 inserciones para evitar memory leak
        if len(_dedup) > 10_000:
            cutoff = now - DEDUP_WINDOW * 2
            to_del = [k for k, v in _dedup.items() if v < cutoff]
            for k in to_del:
                del _dedup[k]

        return True


# ─── Envío HTTP ───────────────────────────────────────────────────────────────

def send_event(event: dict) -> bool:
    payload = json.dumps(event).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type":  "application/json",
            "X-Agent-Token": API_TOKEN,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        log.warning("HTTP %s al enviar evento: %s", e.code, e.reason)
        return False
    except urllib.error.URLError as e:
        log.warning("Error de red al enviar evento: %s", e.reason)
        return False
    except Exception as e:
        log.warning("Error inesperado al enviar: %s", e)
        return False


def send_with_retry(event: dict) -> bool:
    for attempt in range(1, RETRY_MAX + 1):
        if send_event(event):
            return True
        if attempt < RETRY_MAX:
            wait = RETRY_DELAY * attempt
            log.debug("Reintento %d/%d en %.1fs...", attempt, RETRY_MAX, wait)
            time.sleep(wait)
    log.error("Evento descartado tras %d intentos: %s", RETRY_MAX, event.get("action", "?"))
    return False


# ─── Worker de envío ─────────────────────────────────────────────────────────

def sender_worker():
    log.info("Sender worker iniciado")
    while True:
        with queue_lock:
            event = queue.popleft() if queue else None

        if event:
            send_with_retry(event)
        else:
            time.sleep(0.1)


# ─── Lectura del log (tail -f) ────────────────────────────────────────────────

def tail_log():
    log.info("Leyendo log: %s", LOG_FILE)

    while not os.path.exists(LOG_FILE):
        log.warning("Log no encontrado, esperando...")
        time.sleep(5)

    f = open(LOG_FILE, "r", encoding="utf-8", errors="replace")
    f.seek(0, 2)
    current_inode = os.fstat(f.fileno()).st_ino

    log.info("Posicionado al final del log. Esperando eventos...")

    while True:
        line = f.readline()

        if line:
            line = line.strip()
            if line:
                process_line(line)
        else:
            time.sleep(POLL_SLEEP)

            # Detectar rotación del log
            try:
                new_inode = os.stat(LOG_FILE).st_ino
                if new_inode != current_inode:
                    log.info("Rotación de log detectada, reabriendo...")
                    f.close()
                    f = open(LOG_FILE, "r", encoding="utf-8", errors="replace")
                    current_inode = new_inode
                    log.info("Log reabierto tras rotación")
            except FileNotFoundError:
                log.warning("Log desaparecido, esperando...")
                time.sleep(5)


# ─── Procesado de línea ───────────────────────────────────────────────────────

def process_line(line: str):
    """
    Parsea una línea JSON, aplica deduplicación y throttling,
    y encola el evento para envío si pasa los filtros.
    """
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        log.debug("Línea no-JSON ignorada: %s", line[:80])
        return

    if "received_at" not in event:
        event["received_at"] = datetime.now(timezone.utc).isoformat()

    # ── Deduplicación ────────────────────────────────────────────────
    if not _dedup_check(event):
        with _stats_lock:
            _stats["deduped"] += 1
        log.debug(
            "Evento deduplicado: service=%s action=%s src_ip=%s",
            event.get("service", "?"),
            event.get("action", "?"),
            event.get("src_ip", "?"),
        )
        return

    # ── Throttling ───────────────────────────────────────────────────
    if not _throttle_check(event):
        with _stats_lock:
            _stats["throttled"] += 1
        log.debug(
            "Evento throttleado: service=%s action=%s src_ip=%s",
            event.get("service", "?"),
            event.get("action", "?"),
            event.get("src_ip", "?"),
        )
        return

    # ── Encolar ──────────────────────────────────────────────────────
    with queue_lock:
        if len(queue) >= QUEUE_MAX:
            log.warning("Cola llena (%d), descartando evento más antiguo", QUEUE_MAX)
        queue.append(event)

    with _stats_lock:
        _stats["processed"] += 1

    log.debug(
        "Evento encolado: service=%s action=%s src_ip=%s",
        event.get("service", "?"),
        event.get("action", "?"),
        event.get("src_ip", "?"),
    )


# ─── Health check periódico ───────────────────────────────────────────────────

def health_check_worker():
    """Loguea estado de la cola y métricas de tasa cada 5 minutos."""
    while True:
        time.sleep(300)

        with queue_lock:
            pending = len(queue)

        with _stats_lock:
            elapsed = max(time.monotonic() - _stats["since"], 1)
            rate    = _stats["processed"] / (elapsed / 60)
            log.info(
                "Health check — cola: %d | procesados: %d (%.1f/min) | "
                "throttleados: %d | deduplicados: %d",
                pending,
                _stats["processed"],
                rate,
                _stats["throttled"],
                _stats["deduped"],
            )
            # Reset contadores para siguiente ventana
            _stats["processed"] = 0
            _stats["throttled"] = 0
            _stats["deduped"]   = 0
            _stats["since"]     = time.monotonic()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("=" * 50)
    log.info("Honeypot Agent arrancando")
    log.info("Log:        %s", LOG_FILE)
    log.info("API URL:    %s", API_URL)
    log.info("Throttle:   max %d eventos/%ds por (service,ip,action)",
             THROTTLE_MAX, THROTTLE_WINDOW)
    log.info("Dedup:      ventana %.1fs", DEDUP_WINDOW)
    log.info("=" * 50)

    t_sender = threading.Thread(target=sender_worker, daemon=True, name="sender")
    t_sender.start()

    t_health = threading.Thread(target=health_check_worker, daemon=True, name="health")
    t_health.start()

    try:
        tail_log()
    except KeyboardInterrupt:
        log.info("Agente detenido por señal")


if __name__ == "__main__":
    main()
