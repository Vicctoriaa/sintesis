"""
core/alerts.py — Detección de amenazas
Honeypot VM203 · SOC honeycos

Detectores implementados:
  1. BruteForceDetector   — N intentos fallidos de login en ventana T (original)
  2. PortScanDetector     — misma IP toca ≥ PORT_SCAN_MIN servicios distintos
                            en PORT_SCAN_WINDOW segundos
  3. CredentialStuffingDetector — misma contraseña intentada contra
                            ≥ STUFFING_MIN usuarios distintos en ventana T
  4. DecoyFileDetector    — acceso a fichero señuelo de alta prioridad
                            (FTP download, SMB read, HTTP GET de fichero sensible)

Todos los detectores emiten un evento ERROR via el logger del honeypot,
con action específico, para que el agente lo reenvíe a la API y el
dashboard lo muestre como CRÍTICO.
"""

import time
from collections import defaultdict, deque
from typing import Deque

from core.logger import get_logger


# ─── Ficheros señuelo de alta prioridad ───────────────────────────────────────
# Si alguien accede a uno de estos → alerta inmediata independientemente
# del volumen de actividad previo.

DECOY_FILES = {
    # FTP
    "/passwords.txt", "/config.bak", "/database.sql", "/.env",
    "/private/credentials.txt", "/private/keys.pem", "/private/secret.conf",
    "/uploads/shell.php", "/uploads/malware.exe", "/uploads/config_dump.json",
    # SMB
    "credentials_backup.txt", "admin_accounts.txt", "vpn_config.ovpn",
    "deployment_notes.txt", "db_backup_2026-04-23.sql.gz",
    # HTTP
    "/.env", "/config.php", "/.git/config", "/actuator/env",
    "/backup.zip", "/backup.tar.gz", "/backup.sql",
}

# Rutas HTTP que siempre generan alerta de acceso (independiente del detector)
DECOY_HTTP_PATHS = {
    "/.env", "/config.php", "/.git/config",
    "/actuator/env", "/actuator/configprops",
    "/backup.zip", "/backup.tar.gz", "/backup.sql",
    "/wp-config.php", "/server-status",
}


class ThreatDetector:
    """
    Clase unificada que agrupa todos los detectores de amenazas.
    Se instancia una vez en main.py y se pasa a todos los servicios.
    """

    def __init__(self, cfg: dict):
        hp_cfg   = cfg["honeypot"]
        alert_cfg = cfg["alerts"]["brute_force"]

        self._base_extra = {
            "hostname":    hp_cfg["hostname"],
            "environment": hp_cfg["environment"],
            "vlan":        hp_cfg["vlan"],
            "host":        hp_cfg["hostname"],
        }

        self.whitelist: set = set(alert_cfg.get("whitelist", []))

        # ── Brute force ──────────────────────────────────────────────
        self._bf_threshold: int = alert_cfg["threshold"]
        self._bf_window:    int = alert_cfg["window_seconds"]
        # { (service, src_ip) -> deque[(ts_monotonic, username)] }
        self._bf_attempts: dict = defaultdict(deque)

        # ── Port scan ────────────────────────────────────────────────
        # Ventana y mínimo de servicios distintos para disparar la alerta
        self._ps_window: int = cfg.get("alerts", {}).get(
            "port_scan", {}).get("window_seconds", 30)
        self._ps_min:    int = cfg.get("alerts", {}).get(
            "port_scan", {}).get("min_services", 3)
        # { src_ip -> deque[(ts_monotonic, service)] }
        self._ps_hits: dict = defaultdict(deque)

        # ── Credential stuffing ──────────────────────────────────────
        self._cs_window: int = cfg.get("alerts", {}).get(
            "credential_stuffing", {}).get("window_seconds", 60)
        self._cs_min:    int = cfg.get("alerts", {}).get(
            "credential_stuffing", {}).get("min_users", 5)
        # { (service, src_ip, password) -> deque[(ts_monotonic, username)] }
        self._cs_attempts: dict = defaultdict(deque)

        # ── Decoy file — cooldown para no repetir alerta por misma IP+file ──
        # { (src_ip, file) -> last_alert_ts_monotonic }
        self._decoy_cooldown: dict = {}
        self._decoy_cooldown_secs: int = 300  # 5 minutos

    # ─── API pública ─────────────────────────────────────────────────────────

    def record(self, service: str, src_ip: str, username: str,
               password: str = "") -> None:
        """
        Registra un intento de login fallido.
        Dispara brute_force y/o credential_stuffing si se superan umbrales.
        Mantiene compatibilidad con la firma original de BruteForceDetector.
        """
        if src_ip in self.whitelist:
            return
        self._check_brute_force(service, src_ip, username)
        if password:
            self._check_credential_stuffing(service, src_ip, username, password)

    def record_connection(self, service: str, src_ip: str) -> None:
        """
        Registra una nueva conexión (para detección de port scan).
        Llamar desde cada servicio en connection_made/on_connect.
        """
        if src_ip in self.whitelist:
            return
        self._check_port_scan(service, src_ip)

    def record_file_access(self, service: str, src_ip: str,
                           filename: str, direction: str = "download") -> None:
        """
        Registra un acceso a fichero. Si coincide con DECOY_FILES,
        emite alerta inmediata de alta prioridad.
        """
        if src_ip in self.whitelist:
            return
        # Normalizar nombre: comparar solo el basename y el path completo
        basename = filename.split("/")[-1].split("\\")[-1]
        match = (filename in DECOY_FILES or
                 basename in DECOY_FILES or
                 any(filename.endswith(d) for d in DECOY_FILES))
        if match:
            self._alert_decoy_file(service, src_ip, filename, direction)

    def record_http_path(self, service: str, src_ip: str, path: str,
                         method: str = "GET") -> None:
        """
        Registra acceso a ruta HTTP. Alerta si es una ruta señuelo sensible.
        """
        if src_ip in self.whitelist:
            return
        if path in DECOY_HTTP_PATHS:
            self._alert_decoy_file(service, src_ip, path, f"http_{method.lower()}")

    # ─── Detectores internos ─────────────────────────────────────────────────

    def _check_brute_force(self, service: str, src_ip: str,
                           username: str) -> None:
        key = (service, src_ip)
        now = time.monotonic()
        q: Deque = self._bf_attempts[key]

        q.append((now, username))

        while q and (now - q[0][0]) > self._bf_window:
            q.popleft()

        count = len(q)
        if count >= self._bf_threshold:
            usernames = list({u for _, u in q})
            get_logger().error(
                "brute_force",
                extra={
                    **self._base_extra,
                    "service":        service,
                    "action":         "brute_force",
                    "src_ip":         src_ip,
                    "attempt_count":  count,
                    "usernames":      usernames,
                    "window_seconds": self._bf_window,
                },
            )
            q.clear()

    def _check_port_scan(self, service: str, src_ip: str) -> None:
        """
        Detecta si una IP está conectando a múltiples servicios distintos
        en una ventana corta — indicativo de port scan activo.
        """
        now = time.monotonic()
        q: Deque = self._ps_hits[src_ip]

        q.append((now, service))

        # Limpiar fuera de ventana
        while q and (now - q[0][0]) > self._ps_window:
            q.popleft()

        services_seen = {s for _, s in q}
        if len(services_seen) >= self._ps_min:
            get_logger().error(
                "port_scan",
                extra={
                    **self._base_extra,
                    "service":         "multi",
                    "action":          "port_scan",
                    "src_ip":          src_ip,
                    "services_scanned": sorted(services_seen),
                    "hit_count":       len(q),
                    "window_seconds":  self._ps_window,
                },
            )
            # Vaciar para no repetir alerta en cada conexión siguiente
            q.clear()

    def _check_credential_stuffing(self, service: str, src_ip: str,
                                   username: str, password: str) -> None:
        """
        Detecta la misma contraseña probada contra múltiples usuarios distintos
        — patrón típico de credential stuffing con lista de creds filtradas.
        """
        # Clave por contraseña (independiente del usuario)
        key = (service, src_ip, password)
        now = time.monotonic()
        q: Deque = self._cs_attempts[key]

        q.append((now, username))

        while q and (now - q[0][0]) > self._cs_window:
            q.popleft()

        users_seen = {u for _, u in q}
        if len(users_seen) >= self._cs_min:
            get_logger().error(
                "credential_stuffing",
                extra={
                    **self._base_extra,
                    "service":        service,
                    "action":         "credential_stuffing",
                    "src_ip":         src_ip,
                    "password":       password,
                    "users_tried":    sorted(users_seen),
                    "attempt_count":  len(q),
                    "window_seconds": self._cs_window,
                },
            )
            q.clear()

    def _alert_decoy_file(self, service: str, src_ip: str,
                          filename: str, direction: str) -> None:
        """
        Emite alerta inmediata cuando se accede a un fichero señuelo.
        Tiene cooldown de 5 minutos por (ip, fichero) para no spamear.
        """
        key = (src_ip, filename)
        now = time.monotonic()
        last = self._decoy_cooldown.get(key, 0)

        if now - last < self._decoy_cooldown_secs:
            return  # Dentro del cooldown — no repetir

        self._decoy_cooldown[key] = now

        get_logger().error(
            "decoy_file_access",
            extra={
                **self._base_extra,
                "service":   service,
                "action":    "decoy_file_access",
                "src_ip":    src_ip,
                "file":      filename,
                "direction": direction,
                "priority":  "HIGH",
            },
        )


# ─── Alias de compatibilidad ──────────────────────────────────────────────────
# main.py instancia BruteForceDetector — mantenemos el nombre para no
# tener que tocar main.py. ThreatDetector es un superset.

BruteForceDetector = ThreatDetector
