#!/usr/bin/env python3
"""
main.py — Entry point del honeypot
SOC honeycos · VM203 · 10.1.1.130 · VLAN 50

Arranca todos los servicios simulados:
  - SSH  (22)   paramiko
  - FTP  (21)   pyftpdlib
  - HTTP (80)   aiohttp
  - HTTPS(443)  aiohttp + ssl
  - RDP  (3389) asyncio
  - SMB  (445)  impacket

Uso:
  python3 main.py
  systemctl start honeypot
"""

import asyncio
import os
import signal
import sys

import yaml

from core.logger import setup_logger, get_logger
from core.alerts import BruteForceDetector

from services.ssh   import start_ssh
from services.ftp   import start_ftp
from services.http  import start_http, start_https
from services.rdp   import start_rdp
from services.smb   import start_smb

# ---------------------------------------------------------------------------
# Carga de configuración
# ---------------------------------------------------------------------------

CONFIG_PATH = os.environ.get("HONEYPOT_CONFIG", "/opt/honeypot/config.yaml")


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        # Intentar en el mismo directorio del script
        local = os.path.join(os.path.dirname(__file__), "config.yaml")
        if os.path.exists(local):
            cfg_path = local
        else:
            print(f"[ERROR] No se encontró config.yaml en {CONFIG_PATH}", file=sys.stderr)
            sys.exit(1)
    else:
        cfg_path = CONFIG_PATH

    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    cfg = load_config()

    # Logging
    logger = setup_logger(cfg)
    logger.info(
        "honeypot_starting",
        extra={
            "hostname": cfg["honeypot"]["hostname"],
            "environment": cfg["honeypot"]["environment"],
            "vlan": cfg["honeypot"]["vlan"],
            "host": cfg["honeypot"]["hostname"],
            "service": "main",
            "action": "connection",
            "ip": cfg["honeypot"]["ip"],
        },
    )

    detector = BruteForceDetector(cfg)

    # Crear directorio SSL
    os.makedirs("/opt/honeypot/ssl", exist_ok=True)

    tasks = []

    if cfg["services"]["ssh"]["enabled"]:
        tasks.append(asyncio.create_task(start_ssh(cfg, detector), name="ssh"))

    if cfg["services"]["ftp"]["enabled"]:
        tasks.append(asyncio.create_task(start_ftp(cfg, detector), name="ftp"))

    if cfg["services"]["http"]["enabled"]:
        tasks.append(asyncio.create_task(start_http(cfg, detector), name="http"))

    if cfg["services"]["https"]["enabled"]:
        tasks.append(asyncio.create_task(start_https(cfg, detector), name="https"))

    if cfg["services"]["rdp"]["enabled"]:
        tasks.append(asyncio.create_task(start_rdp(cfg, detector), name="rdp"))

    if cfg["services"]["smb"]["enabled"]:
        tasks.append(asyncio.create_task(start_smb(cfg, detector), name="smb"))

    logger.info(
        "honeypot_started",
        extra={
            "hostname": cfg["honeypot"]["hostname"],
            "environment": cfg["honeypot"]["environment"],
            "vlan": cfg["honeypot"]["vlan"],
            "host": cfg["honeypot"]["hostname"],
            "service": "main",
            "action": "connection",
            "services_active": [t.get_name() for t in tasks],
        },
    )

    # Manejo de señales para shutdown limpio
    loop = asyncio.get_event_loop()

    def _shutdown(sig):
        logger.info(
            "honeypot_stopping",
            extra={
                "hostname": cfg["honeypot"]["hostname"],
                "environment": cfg["honeypot"]["environment"],
                "vlan": cfg["honeypot"]["vlan"],
                "host": cfg["honeypot"]["hostname"],
                "service": "main",
                "action": "connection",
                "signal": sig.name,
            },
        )
        for t in tasks:
            t.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as exc:
        logger.error("honeypot_error", extra={"error": str(exc)})


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
