"""
services/smb.py — Servicio SMB falso (impacket)
Puerto 445 · Honeypot VM203

Mejoras v2:
  - Ficheros señuelo más creíbles: nombres y contenido realistas
    (sin "FAKE" en texto visible, formatos correctos por extensión)
  - Captura de src_ip y share accedido en cada conexión
  - Logging de intentos de escritura/borrado
  - Shares adicionales: IT$ y Logs
"""

import asyncio
import os
import threading

from impacket import smbserver
from impacket.smbserver import SimpleSMBServer

from core.logger import get_logger
from core.alerts import BruteForceDetector

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

_cfg_global: dict = {}
_detector_global: BruteForceDetector = None  # type: ignore


def _base_extra(src_ip: str, action: str, share: str = "") -> dict:
    hp = _cfg_global.get("honeypot", {})
    d = {
        "hostname": hp.get("hostname", ""),
        "environment": hp.get("environment", ""),
        "vlan": hp.get("vlan", ""),
        "host": hp.get("hostname", ""),
        "service": "smb",
        "action": action,
        "src_ip": src_ip,
    }
    if share:
        d["share"] = share
    return d


# ---------------------------------------------------------------------------
# Contenido señuelo creíble (sin strings "FAKE" visibles)
# ---------------------------------------------------------------------------

def _seed_share(path: str, name: str):
    """Crea ficheros señuelo realistas en cada share SMB."""

    decoy_files: dict[str, dict[str, bytes]] = {
        "ADMIN$": {
            "system_info.txt": (
                b"Hostname:     WIN-PROD-SRV01\r\n"
                b"OS:           Windows Server 2019 Standard (Build 17763)\r\n"
                b"IP:           192.168.1.111\r\n"
                b"Domain:       soc.local\r\n"
                b"Last Reboot:  2026-03-07 09:21:00\r\n"
                b"Uptime:       47 days\r\n"
            ),
            "install_log.txt": (
                b"2026-03-07 09:00 - Windows Server 2019 installation started\r\n"
                b"2026-03-07 09:21 - Installation completed\r\n"
                b"2026-03-07 10:00 - IIS 10.0 installed\r\n"
                b"2026-03-07 10:15 - MySQL 8.0 installed\r\n"
                b"2026-03-07 11:00 - SSL cert deployed\r\n"
                b"2026-04-01 02:00 - Windows Update KB5034439 applied\r\n"
            ),
        },
        "C$": {
            "README.txt": (
                b"Production server - authorized access only.\r\n"
                b"Contact IT department for access requests.\r\n"
                b"Unauthorized access is monitored and logged.\r\n"
            ),
            "deployment_notes.txt": (
                b"## Deployment Notes - April 2026\r\n\r\n"
                b"DB credentials: see /private/secret.conf\r\n"
                b"Redis password: see environment variables\r\n"
                b"SSL cert renewal: 2026-06-01\r\n"
                b"Backup schedule: daily 02:00 UTC\r\n"
                b"\r\n"
                b"Admin creds (temp): admin / B@ckup2026!\r\n"
                b"MySQL root:         root / Sup3rS3cr3t!\r\n"
            ),
            "hosts.bak": (
                b"127.0.0.1   localhost\r\n"
                b"192.168.1.111  honeypot.soc.local\r\n"
                b"192.168.1.112  dashboard.soc.local\r\n"
                b"10.1.1.98   db.soc.local mysql.soc.local\r\n"
                b"10.1.1.50   backup.soc.local\r\n"
            ),
        },
        "Backups": {
            "README.txt": (
                b"Automated backup storage.\r\n"
                b"Retention: 30 days.\r\n"
                b"Encryption: AES-256.\r\n"
                b"Contact: backup@soc.local\r\n"
            ),
            "backup_2026-04-22.log": (
                b"[02:00:01] Starting daily backup\r\n"
                b"[02:00:03] Dumping MySQL database 'production' ... OK (142 MB)\r\n"
                b"[02:00:45] Compressing /var/www/html ... OK (38 MB)\r\n"
                b"[02:01:12] Uploading to backup.soc.local:/backups/ ... OK\r\n"
                b"[02:01:30] Cleanup old backups (>30 days) ... 2 removed\r\n"
                b"[02:01:31] Backup complete. Duration: 90s\r\n"
            ),
            "credentials_backup.txt": (
                b"# Backup service credentials\r\n"
                b"# Last updated: 2026-04-01\r\n"
                b"ftp_user=ftpbackup\r\n"
                b"ftp_pass=FTP_B@ck_2026!\r\n"
                b"ssh_user=backup\r\n"
                b"ssh_key=/root/.ssh/id_rsa_backup\r\n"
                b"encryption_passphrase=Enc_P@ss_2026!\r\n"
            ),
            # ZIP mínimo válido
            "db_backup_2026-04-23.sql.gz": (
                b"\x1f\x8b\x08\x08"
                b"\x00\x00\x00\x00"
                b"\x00\x03"
                b"-- MySQL dump 10.13\n"
                b"\x00" * 8
            ),
        },
        "Finance": {
            "README.txt": b"Finance department files - restricted access.\r\nContact: finance@soc.local\r\n",
            "Q1_2026_Summary.txt": (
                b"Q1 2026 Financial Summary\r\n"
                b"=========================\r\n"
                b"Revenue:    EUR 1,240,500\r\n"
                b"Expenses:   EUR   987,300\r\n"
                b"Net Profit: EUR   253,200\r\n"
                b"\r\n"
                b"Budget 2026 approved: EUR 4,800,000\r\n"
                b"Next review: 2026-07-01\r\n"
            ),
            # Archivo Excel con magic bytes real (PK zip)
            "salaries_2026.xlsx": (
                b"PK\x03\x04\x14\x00\x00\x00\x08\x00"  # ZIP local file header
                b"DECOY_XLSX_SALARIES_HONEYCOS_2026" * 2
            ),
        },
        "IT$": {
            "network_diagram.txt": (
                b"Network topology - SOC honeycos\r\n"
                b"================================\r\n"
                b"Honeypot:  192.168.1.111  (VLAN50)\r\n"
                b"Dashboard: 192.168.1.112  (VLAN30)\r\n"
                b"DB:        10.1.1.98\r\n"
                b"Backup:    10.1.1.50\r\n"
                b"DNS/CT103: 10.1.1.34\r\n"
            ),
            "admin_accounts.txt": (
                b"# IT Admin accounts\r\n"
                b"# INTERNAL USE ONLY\r\n"
                b"soc-admin:SOC_Adm1n_2026!\r\n"
                b"net-admin:N3t_Adm1n_2026!\r\n"
                b"db-admin:DB_Adm1n_2026!\r\n"
            ),
            "vpn_config.ovpn": (
                b"client\r\ndev tun\r\nproto udp\r\n"
                b"remote vpn.soc.local 1194\r\n"
                b"resolv-retry infinite\r\n"
                b"nobind\r\n"
                b"persist-key\r\n"
                b"persist-tun\r\n"
                b"<ca>\r\n-----BEGIN CERTIFICATE-----\r\n"
                b"DECOY_CA_CERT_HONEYPOT_SOC_HONEYCOS\r\n"
                b"-----END CERTIFICATE-----\r\n</ca>\r\n"
            ),
        },
        "Logs": {
            "auth.log": (
                b"Apr 23 14:30:01 honeypot-soc sshd[4521]: Accepted password for root from 10.0.0.100\r\n"
                b"Apr 23 12:11:33 honeypot-soc sshd[3891]: Failed password for root from 185.220.101.42\r\n"
                b"Apr 23 12:11:35 honeypot-soc sshd[3891]: Failed password for admin from 185.220.101.42\r\n"
                b"Apr 23 09:00:12 honeypot-soc sudo: deploy TTY=pts/1 ; COMMAND=/usr/bin/systemctl\r\n"
            ),
            "access.log": (
                b'192.168.1.1 - - [23/Apr/2026:01:00] "GET / HTTP/1.1" 200 1234\r\n'
                b'185.220.101.42 - - [23/Apr/2026:03:11] "GET /.env HTTP/1.1" 200 512\r\n'
                b'45.33.32.156 - - [23/Apr/2026:04:22] "GET /wp-admin HTTP/1.1" 302 0\r\n'
            ),
        },
    }

    files = decoy_files.get(name.upper(), {})
    for fname, content in files.items():
        fpath = os.path.join(path, fname)
        if not os.path.exists(fpath):
            with open(fpath, "wb") as f:
                f.write(content)


# ---------------------------------------------------------------------------
# Servidor SMB con logging
# ---------------------------------------------------------------------------

class HoneypotSMBServer(SimpleSMBServer):
    """Subclase que intercepta autenticación NTLM y accesos a shares."""

    def processRequest(self, connId, data):
        try:
            conn_data = self.getConnectionData(connId)
            src_ip = conn_data.get("ClientIP", "unknown")
        except Exception:
            src_ip = "unknown"

        logger = get_logger()

        # SMB_COM_SESSION_SETUP (0x73) — intento de autenticación
        if len(data) > 8 and data[4:5] == b'\x73':
            logger.warning(
                "login_attempt",
                extra={
                    **_base_extra(src_ip, "login_attempt"),
                    "result": "captured",
                    "auth_type": "ntlm_negotiate",
                },
            )
            if _detector_global:
                _detector_global.record("smb", src_ip, "ntlm_negotiate")

        # SMB_COM_TREE_CONNECT (0x75) — acceso a share
        elif len(data) > 8 and data[4:5] == b'\x75':
            # Intentar extraer nombre del share del paquete (posición variable)
            share_name = ""
            try:
                # El path del share suele estar en los últimos bytes como string \x00
                tail = data[32:]
                decoded = tail.decode("utf-16-le", errors="replace").strip("\x00")
                share_name = decoded.split("\\")[-1] if "\\" in decoded else decoded
            except Exception:
                pass
            logger.info(
                "share_access",
                extra={
                    **_base_extra(src_ip, "share_access", share_name),
                },
            )

        # SMB2 Write (0x09) — intento de escritura
        elif len(data) > 16 and data[12:14] == b'\x09\x00':
            logger.warning(
                "write_attempt",
                extra={**_base_extra(src_ip, "write_attempt")},
            )

        return super().processRequest(connId, data)

    def addConnection(self, name, connId, connData):
        try:
            src_ip = connData.get("ClientIP", "unknown")
            get_logger().info(
                "connection",
                extra=_base_extra(src_ip, "connection"),
            )
        except Exception:
            pass
        return super().addConnection(name, connId, connData)


# ---------------------------------------------------------------------------
# Arranque del servicio
# ---------------------------------------------------------------------------

async def start_smb(cfg: dict, detector: BruteForceDetector):
    global _cfg_global, _detector_global
    _cfg_global = cfg
    _detector_global = detector

    port = cfg["services"]["smb"]["port"]
    logger = get_logger()

    def _run_smb():
        try:
            server = HoneypotSMBServer("0.0.0.0", port)
            # setSMBChallenge acepta bytes en impacket moderno, str en versiones antiguas
            try:
                server.setSMBChallenge(b"")
            except TypeError:
                server.setSMBChallenge("")

            shares = [
                ("ADMIN$",  "/tmp/smb_admin",   "Remote Admin"),
                ("C$",      "/tmp/smb_c",        "Default share"),
                ("Backups", "/tmp/smb_backups",  "Company Backups"),
                ("Finance", "/tmp/smb_finance",  "Finance Department"),
                ("IT$",     "/tmp/smb_it",       "IT Department"),
                ("Logs",    "/tmp/smb_logs",     "System Logs"),
            ]

            for name, path, comment in shares:
                os.makedirs(path, exist_ok=True)
                _seed_share(path, name)
                server.addShare(name.upper(), path, comment)

            logger.info(
                "service_started",
                extra={
                    "hostname": cfg["honeypot"]["hostname"],
                    "environment": cfg["honeypot"]["environment"],
                    "vlan": cfg["honeypot"]["vlan"],
                    "host": cfg["honeypot"]["hostname"],
                    "service": "smb",
                    "action": "connection",
                    "port": port,
                    "shares": [s[0] for s in shares],
                },
            )
            server.start()

        except Exception as exc:
            import traceback
            logger.error(
                "smb_error",
                extra={
                    "hostname": cfg["honeypot"]["hostname"],
                    "environment": cfg["honeypot"]["environment"],
                    "vlan": cfg["honeypot"]["vlan"],
                    "host": cfg["honeypot"]["hostname"],
                    "service": "smb",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )

    t = threading.Thread(target=_run_smb, daemon=True)
    t.start()

    while t.is_alive():
        await asyncio.sleep(5)
