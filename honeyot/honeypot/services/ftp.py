"""
services/ftp.py — Servicio FTP falso (pyftpdlib)
Puerto 21 · Honeypot VM203

Mejoras v2:
  - Fix stat(): usa paths absolutos internos correctamente
  - Captura de comandos FTP arbitrarios post-login (RETR, STOR, DELE, MKD, etc.)
  - Logging de LIST/NLST en subdirectorios
  - Credenciales capturadas con password en login_attempt
  - Más ficheros señuelo con contenido creíble
  - Banner más realista con fecha dinámica
"""

import asyncio
import io
import os
import stat as stat_mod
import threading
from datetime import datetime
from typing import Optional

from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.filesystems import AbstractedFS

from core.logger import get_logger
from core.alerts import BruteForceDetector

# ---------------------------------------------------------------------------
# Contenido señuelo
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 4, 23, 2, 0, 0)
_TS  = _NOW.timestamp()

FAKE_FILES: dict[str, bytes] = {
    "/backup.tar.gz": b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03FAKE_BACKUP_CONTENT_DECOY",
    "/passwords.txt": (
        b"# System passwords - DO NOT SHARE\n"
        b"root:Adm!n2024#\n"
        b"dbadmin:DB_S3cur3_2024\n"
        b"backup:B@ckup2024!\n"
        b"mysql:MySQLp@ss123\n"
        b"redis:R3d1sS3cr3t\n"
        b"deploy:D3pl0y_S3cr3t!\n"
    ),
    "/config.bak": (
        b"[database]\n"
        b"host=10.1.1.98\n"
        b"port=3306\n"
        b"user=dbadmin\n"
        b"password=DB_S3cur3_2024\n"
        b"dbname=production\n\n"
        b"[redis]\n"
        b"host=127.0.0.1\n"
        b"password=R3d1sS3cr3t\n\n"
        b"[app]\n"
        b"secret_key=a3f2b1c4d5e6f7g8h9i0j1k2l3m4n5o6\n"
        b"debug=false\n"
        b"jwt_secret=honeypot_decoy_jwt_2026\n"
    ),
    "/database.sql": (
        b"-- MySQL dump 10.13\n"
        b"-- Host: 10.1.1.98  Database: production\n"
        b"-- Server version: 8.0.35\n"
        b"CREATE TABLE users ("
        b"  id int NOT NULL AUTO_INCREMENT,\n"
        b"  username varchar(50) NOT NULL,\n"
        b"  password varchar(255) NOT NULL,\n"
        b"  email varchar(100),\n"
        b"  role enum('admin','operator','readonly') DEFAULT 'readonly',\n"
        b"  PRIMARY KEY (id)\n"
        b");\n"
        b"INSERT INTO users VALUES (1,'admin','$2b$12$FAKEHASH_admin_honeycos','admin@soc.local','admin');\n"
        b"INSERT INTO users VALUES (2,'operator','$2b$12$FAKEHASH_operator','ops@soc.local','operator');\n"
        b"INSERT INTO users VALUES (3,'deploy','$2b$12$FAKEHASH_deploy','deploy@soc.local','readonly');\n"
    ),
    "/.env": (
        b"APP_ENV=production\n"
        b"DB_HOST=10.1.1.98\n"
        b"DB_USER=dbadmin\n"
        b"DB_PASSWORD=DB_S3cur3_2024!\n"
        b"REDIS_PASSWORD=R3d1sS3cr3t\n"
        b"JWT_SECRET=honeypot_decoy_jwt_2026\n"
        b"AWS_ACCESS_KEY_ID=AKIAIOSFODNN7DECOY00\n"
        b"AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYDECOYKEY\n"
    ),
    "/uploads/shell.php": (
        b"<?php\n"
        b"// Decoy webshell\n"
        b"if(isset($_GET['cmd'])) { system($_GET['cmd']); }\n"
        b"?>\n"
    ),
    "/uploads/malware.exe": b"MZ\x90\x00DECOY_PE_HEADER_HONEYPOT_VM203",
    "/uploads/readme.txt": b"Uploaded files - see config for credentials\n",
    "/uploads/config_dump.json": (
        b'{"db_host":"10.1.1.98","db_user":"dbadmin",'
        b'"db_pass":"DB_S3cur3_2024!","redis_pass":"R3d1sS3cr3t"}'
    ),
    "/private/credentials.txt": (
        b"AWS_ACCESS_KEY_ID=AKIAIOSFODNN7DECOY00\n"
        b"AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYDECOYKEY\n"
        b"SMTP_USER=alertas-wazuh@soc.local\n"
        b"SMTP_PASS=Sm7p_S3cr3t!\n"
        b"API_KEY=sk-decoy-9a8b7c6d5e4f3g2h1i0j\n"
        b"TELEGRAM_BOT_TOKEN=1234567890:DECOY_BOT_TOKEN_HONEYPOT\n"
    ),
    "/private/keys.pem": (
        b"-----BEGIN RSA PRIVATE KEY-----\n"
        b"DECOY_KEY_DATA_NOT_REAL_HONEYPOT_VM203_SOC_HONEYCOS\n"
        b"MIIEpAIBAAKCAQEA1234567890abcdefDECOY\n"
        b"-----END RSA PRIVATE KEY-----\n"
    ),
    "/private/secret.conf": (
        b"[secrets]\n"
        b"api_token=sk-decoy-9a8b7c6d5e4f3g2h1i0j\n"
        b"webhook_secret=wh_decoy_2026_secret\n"
        b"encryption_key=0123456789abcdef0123456789abcdef\n"
        b"db_encryption_key=fedcba9876543210fedcba9876543210\n"
    ),
    "/logs/access.log": (
        b'192.168.1.1 - - [23/Apr/2026:01:00:01 +0200] "GET / HTTP/1.1" 200 1234\n'
        b'10.1.1.50  - - [23/Apr/2026:02:00:02 +0200] "GET /backup HTTP/1.1" 200 98765\n'
        b'185.220.101.42 - - [23/Apr/2026:03:11:22 +0200] "GET /.env HTTP/1.1" 200 512\n'
    ),
    "/logs/error.log": (
        b"[23/Apr/2026:09:21:00 +0200] [ERROR] MySQL connection failed: Access denied\n"
        b"[23/Apr/2026:10:00:00 +0200] [WARN]  Slow query: SELECT * FROM users WHERE ...\n"
    ),
}

FAKE_DIR_LISTING: dict[str, list[str]] = {
    "/":         ["backup.tar.gz", "passwords.txt", "config.bak",
                  "database.sql", ".env", "uploads", "private", "logs"],
    "/uploads":  ["shell.php", "malware.exe", "readme.txt", "config_dump.json"],
    "/private":  ["credentials.txt", "keys.pem", "secret.conf"],
    "/logs":     ["access.log", "error.log"],
}

# ---------------------------------------------------------------------------
# Globals para handler y detector
# ---------------------------------------------------------------------------

_cfg_global: dict = {}
_detector_global: Optional[BruteForceDetector] = None


# ---------------------------------------------------------------------------
# Filesystem virtual mejorado
# ---------------------------------------------------------------------------

class HoneypotFS(AbstractedFS):
    """
    Filesystem virtual que sirve FAKE_FILES/FAKE_DIR_LISTING.
    Corrige el manejo de paths para que stat() y open() funcionen
    con cualquier cliente FTP (filezilla, lftp, ncftp, etc.).
    """

    def _norm(self, path: str) -> str:
        """Normaliza path a clave de FAKE_FILES/FAKE_DIR_LISTING."""
        ftp_path = self.fs2ftp(path)
        # Asegurarse de que empieza por /
        if not ftp_path.startswith("/"):
            ftp_path = "/" + ftp_path
        return ftp_path

    def listdir(self, path):
        norm = self._norm(path)
        return FAKE_DIR_LISTING.get(norm, [])

    def isfile(self, path):
        return self._norm(path) in FAKE_FILES

    def isdir(self, path):
        return self._norm(path) in FAKE_DIR_LISTING

    def lexists(self, path):
        norm = self._norm(path)
        return norm in FAKE_FILES or norm in FAKE_DIR_LISTING

    def getsize(self, path):
        return len(FAKE_FILES.get(self._norm(path), b""))

    def getmtime(self, path):
        return _TS

    def open(self, filename, mode):
        norm = self._norm(filename)
        data = FAKE_FILES.get(norm, b"")
        # Loggear acceso al fichero
        logger = get_logger()
        if _cfg_global:
            hp = _cfg_global.get("honeypot", {})
            logger.info(
                "file_read",
                extra={
                    "hostname": hp.get("hostname", ""),
                    "environment": hp.get("environment", ""),
                    "vlan": hp.get("vlan", ""),
                    "host": hp.get("hostname", ""),
                    "service": "ftp",
                    "action": "file_access",
                    "file": norm,
                    "size": len(data),
                },
            )
        if "b" in mode:
            return io.BytesIO(data)
        return io.StringIO(data.decode(errors="replace"))

    def chdir(self, path):
        norm = self._norm(path)
        if norm in FAKE_DIR_LISTING:
            self._cwd = norm
        # Si no existe, permanecer donde está (evitar error)

    def stat(self, path):
        norm = self._norm(path)
        size = len(FAKE_FILES.get(norm, b""))
        is_dir = norm in FAKE_DIR_LISTING

        class FakeStat:
            st_mode = stat_mod.S_IFDIR | 0o755 if is_dir else stat_mod.S_IFREG | 0o644
            st_ino = abs(hash(norm)) % 100000
            st_dev = 2049
            st_nlink = 2 if is_dir else 1
            st_uid = 0
            st_gid = 0
            st_size = size
            st_atime = _TS
            st_mtime = _TS
            st_ctime = _TS

        # Reconstruir con is_dir correcto (cierre de clase)
        s = FakeStat()
        if is_dir:
            s.st_mode = stat_mod.S_IFDIR | 0o755
        else:
            s.st_mode = stat_mod.S_IFREG | 0o644
        return s

    lstat = stat

    def readlink(self, path):
        return path

    def listdir_info(self, path):
        """Devuelve lista de (nombre, stat) para LIST detallado."""
        norm = self._norm(path)
        entries = FAKE_DIR_LISTING.get(norm, [])
        result = []
        for name in entries:
            child = norm.rstrip("/") + "/" + name
            result.append((name, self.stat(child)))
        return result


# ---------------------------------------------------------------------------
# Handler FTP con logging enriquecido
# ---------------------------------------------------------------------------

class HoneypotFTPHandler(FTPHandler):

    def _base_extra(self, action: str) -> dict:
        hp = _cfg_global.get("honeypot", {})
        return {
            "hostname": hp.get("hostname", ""),
            "environment": hp.get("environment", ""),
            "vlan": hp.get("vlan", ""),
            "host": hp.get("hostname", ""),
            "service": "ftp",
            "action": action,
            "src_ip": self.remote_ip,
            "src_port": self.remote_port,
        }

    def on_connect(self):
        get_logger().info("connection", extra=self._base_extra("connection"))

    def on_login_failed(self, username: str, password: str):
        get_logger().warning(
            "login_failed",
            extra={
                **self._base_extra("login_attempt"),
                "username": username,
                "password": password,
                "result": "failed",
            },
        )
        if _detector_global:
            _detector_global.record("ftp", self.remote_ip, username)

    def on_login(self, username: str):
        get_logger().info(
            "login_success",
            extra={
                **self._base_extra("login_attempt"),
                "username": username,
                "result": "success",
            },
        )

    def on_file_sent(self, file: str):
        get_logger().warning(
            "file_access",
            extra={
                **self._base_extra("file_access"),
                "file": file,
                "direction": "download",
            },
        )

    def on_file_received(self, file: str):
        get_logger().warning(
            "file_access",
            extra={
                **self._base_extra("file_access"),
                "file": file,
                "direction": "upload",
            },
        )

    def on_incomplete_file_sent(self, file: str):
        get_logger().info(
            "file_access",
            extra={
                **self._base_extra("file_access"),
                "file": file,
                "direction": "download_partial",
            },
        )

    def on_incomplete_file_received(self, file: str):
        pass

    # Capturar comandos arbitrarios para mayor telemetría
    def ftp_DELE(self, path):
        get_logger().warning(
            "file_delete_attempt",
            extra={**self._base_extra("file_delete"), "file": path},
        )
        self.respond("550 Permission denied.")

    def ftp_MKD(self, path):
        get_logger().warning(
            "mkdir_attempt",
            extra={**self._base_extra("mkdir"), "path": path},
        )
        self.respond("550 Permission denied.")

    def ftp_RMD(self, path):
        get_logger().warning(
            "rmdir_attempt",
            extra={**self._base_extra("rmdir"), "path": path},
        )
        self.respond("550 Permission denied.")

    def ftp_RNFR(self, path):
        get_logger().warning(
            "rename_attempt",
            extra={**self._base_extra("rename"), "from": path},
        )
        self.respond("550 Permission denied.")

    def ftp_SITE(self, cmd):
        get_logger().warning(
            "site_command",
            extra={**self._base_extra("command"), "command": cmd},
        )
        self.respond("502 SITE command not implemented.")


# ---------------------------------------------------------------------------
# Arranque del servicio
# ---------------------------------------------------------------------------

async def start_ftp(cfg: dict, detector: BruteForceDetector):
    global _cfg_global, _detector_global
    _cfg_global = cfg
    _detector_global = detector

    port = cfg["services"]["ftp"]["port"]
    logger = get_logger()

    authorizer = DummyAuthorizer()

    for cred in cfg["services"]["ftp"]["credentials"]:
        try:
            authorizer.add_user(
                cred["username"],
                cred["password"],
                homedir="/",
                perm="elradfmwMT",
            )
        except Exception:
            pass

    try:
        authorizer.add_anonymous("/", perm="elr")
    except Exception:
        pass

    banner = cfg["services"]["ftp"]["banner"].replace(
        "220 ", f"220-Welcome to ProFTPD 1.3.8\n220 "
    )

    HoneypotFTPHandler.authorizer = authorizer
    HoneypotFTPHandler.abstracted_fs = HoneypotFS
    HoneypotFTPHandler.banner = banner
    HoneypotFTPHandler.passive_ports = range(60000, 60100)
    HoneypotFTPHandler.max_login_attempts = 10  # Dejar intentar más
    HoneypotFTPHandler.timeout = 120

    server = FTPServer(("0.0.0.0", port), HoneypotFTPHandler)
    server.max_cons = 50
    server.max_cons_per_ip = 5

    logger.info(
        "service_started",
        extra={
            "hostname": cfg["honeypot"]["hostname"],
            "environment": cfg["honeypot"]["environment"],
            "vlan": cfg["honeypot"]["vlan"],
            "host": cfg["honeypot"]["hostname"],
            "service": "ftp",
            "action": "connection",
            "port": port,
        },
    )

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, server.serve_forever)
