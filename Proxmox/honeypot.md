# Honeypot VM203 — Documentación

**SOC honeycos · Abril 2026 · v2**

---

## 1. Información general

> El honeypot corre como VM (no LXC) para mayor aislamiento y para poder simular un sistema operativo completo de forma más convincente. Está en la VLAN 50, completamente separada del resto de la infraestructura SOC, para que cualquier atacante que interactúe con ella no tenga acceso lateral a otros servicios.

| Campo | Valor |
|-------|-------|
| VMID | 203 |
| Hostname | honeypot |
| IP | 10.1.1.130/27 |
| Gateway | 10.1.1.129 |
| VLAN | 50 — Honeypot (aislado total) |
| OS | Debian 12 Bookworm |
| RAM | 1 GB |
| Disco | 16 GB (local-zfs, thin) |
| Bridge | vmbr1, tag=50 |

---

## 2. Arquitectura

> El honeypot está desarrollado en Python y estructurado en módulos independientes por servicio. `main.py` actúa como punto de entrada que arranca todos los listeners en paralelo. El módulo `core/` contiene la lógica transversal de logging y detección, desacoplada de cada servicio individual.

```
/opt/honeypot/
├── config.yaml          # Configuración central
├── main.py              # Entry point — arranca todos los servicios
├── agent.py             # Agente de envío de eventos al dashboard
├── services/
│   ├── __init__.py
│   ├── ssh.py           # SSH (paramiko) — puerto 22
│   ├── http.py          # HTTP (aiohttp) — puerto 80
│   ├── https.py         # HTTPS (aiohttp + SSL) — puerto 443
│   ├── ftp.py           # FTP (pyftpdlib) — puerto 21
│   ├── rdp.py           # RDP — puerto 3389
│   └── smb.py           # SMB (impacket) — puerto 445
├── core/
│   ├── __init__.py
│   ├── logger.py        # Logging JSON estructurado
│   └── alerts.py        # Detección de amenazas (ThreatDetector)
└── logs/ -> /var/log/honeypot/
```

---

## 3. Servicios simulados

> Cada servicio simula el comportamiento real del protocolo correspondiente para que los escaneos automatizados y los atacantes no lo detecten fácilmente como honeypot. El objetivo es que interactúen el máximo tiempo posible, generando eventos que el dashboard y Wazuh procesarán y correlacionarán.

| Servicio | Puerto | Librería | Capacidades |
|----------|--------|----------|-------------|
| SSH | 22 | paramiko | Shell interactiva completa, pipes, historial 120 cmds, captura credenciales y comandos |
| FTP | 21 | pyftpdlib | Filesystem virtual, captura logins, transferencias y comandos post-login |
| HTTP | 80 | aiohttp | ~60 rutas señuelo, headers realistas, panel admin con cookie falsa |
| HTTPS | 443 | aiohttp + ssl | Igual que HTTP con certificado autofirmado y SAN |
| RDP | 3389 | asyncio | Handshake en 3 fases, captura mstshash, clientName y NTLM |
| SMB | 445 | impacket | 6 shares falsos, ficheros señuelo creíbles, captura NTLM |

### SSH — Capacidades v2

> Se emula un servidor OpenSSH con banner real. La shell falsa soporta pipes, redirecciones y encadenamiento de comandos para maximizar el tiempo de interacción del atacante. Los delays artificiales por tipo de comando dificultan el fingerprinting automático.

- Banner: `SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6`
- Shell falsa con soporte de pipes (`|`), redirecciones (`>`, `>>`), encadenamiento (`&&`, `;`)
- Historial de 120 comandos realistas (backups, deploys, análisis de logs)
- Delays artificiales por tipo de comando (`apt` 1.5–3s, `find` 0.2–0.6s, etc.)
- Hostname consistente en todos los contextos: prompt, `/etc/hostname`, `/etc/hosts`, `auth.log`
- Comandos soportados: `ls`, `cat`, `ps`, `netstat`, `env`, `history`, `crontab`, `find`, `wget`, `curl`, `df`, `free`, `last`, `who`, `ufw`, `systemctl`, y más
- Captura `username` + `password` en cada `login_attempt`

### HTTP/HTTPS — Rutas simuladas v2

> Las rutas están diseñadas para atraer scanners automáticos y atacantes. Todos los eventos HTTP capturan User-Agent, Referer y X-Forwarded-For. Los headers de respuesta son realistas para no ser detectados como honeypot.

Headers de respuesta: `Server: Apache/2.4.57 (Ubuntu)`, `X-Powered-By: PHP/8.1.12`

Rutas principales:
- `/` — Apache2 Ubuntu Default Page
- `/admin` — Panel de administración (credenciales señuelo generan cookie de sesión falsa)
- `/login` — Página de login genérica
- `/phpmyadmin` — Login phpMyAdmin
- `/wp-admin` — Login WordPress
- `/manager` — Tomcat Manager (401 con WWW-Authenticate)
- `/.env` — Fichero de entorno con credenciales falsas
- `/config.php` — Configuración WordPress con credenciales falsas
- `/.git/config` — Configuración Git con repositorio remoto falso
- `/actuator/env` — Spring Boot Actuator con credenciales de BD falsas
- `/server-status` — Apache server-status realista
- `/xmlrpc.php` — WordPress XML-RPC
- ~50 rutas adicionales de scanner logueadas como `WARNING scanner_probe`

### FTP — Filesystem virtual v2

> El sistema de ficheros virtual incluye 12 ficheros señuelo en 4 directorios. Los comandos post-login (DELE, MKD, RMD, RNFR) también se capturan y loggean.

- `/` — `backup.tar.gz`, `passwords.txt`, `config.bak`, `database.sql`, `.env`
- `/uploads` — `shell.php`, `malware.exe`, `readme.txt`, `config_dump.json`
- `/private` — `credentials.txt`, `keys.pem`, `secret.conf`
- `/logs` — `access.log`, `error.log`

Comandos capturados post-login: `DELE`, `MKD`, `RMD`, `RNFR`, `SITE`

### SMB — Shares falsos v2

> Se simulan 6 shares con ficheros señuelo de contenido creíble (sin strings "FAKE" visibles). Los ficheros contienen credenciales falsas, configuraciones de red, logs de acceso y documentos financieros para maximizar el tiempo de interacción.

- `ADMIN$` — Remote Admin (`system_info.txt`, `install_log.txt`)
- `C$` — Default share (`deployment_notes.txt`, `hosts.bak`)
- `Backups` — Company Backups (`credentials_backup.txt`, `backup.log`, `db_backup.sql.gz`)
- `Finance` — Finance Department (`Q1_2026_Summary.txt`, `salaries_2026.xlsx`)
- `IT$` — IT Department (`network_diagram.txt`, `admin_accounts.txt`, `vpn_config.ovpn`)
- `Logs` — System Logs (`auth.log`, `access.log`)

### RDP — Handshake v2

> El handshake RDP simula 3 fases del protocolo para parecer un servidor real. Los scanners que solo envían paquetes cortos son detectados y logueados como `scanner_probe`.

- Fase 1: X.224 CR → extrae `requestedProtocols`, cookie `mstshash` y `clientName`
- Fase 2: MCS Connect Initial → responde con MCS Connect Response con BER encoding válido
- Fase 3: Espera CredSSP/NTLM → extrae `ntlm_user` si el cliente usa NLA
- Detección de scanners: paquetes < 11 bytes → `scanner_probe`
- Timeout de 45s por conexión para evitar conexiones zombie

---

## 4. Logging

### Ubicación

```
/var/log/honeypot/honeypot.log
/var/log/honeypot/agent.log
```

### Formato JSON

> El logging estructurado en JSON facilita el parsing por parte del agente y de Wazuh. Los campos varían según el servicio y la acción, pero todos incluyen los campos base.

| Campo | Descripción |
|-------|-------------|
| `timestamp` | ISO8601 UTC |
| `level` | INFO / WARNING / ERROR |
| `service` | ssh / ftp / http / https / rdp / smb / main |
| `action` | connection / login_attempt / command / request / file_access / brute_force / port_scan / credential_stuffing / decoy_file_access / scanner_probe |
| `src_ip` | IP de origen |
| `src_port` | Puerto de origen |
| `username` | Usuario intentado (si aplica) |
| `password` | Contraseña intentada (si aplica) |
| `user_agent` | User-Agent HTTP (si aplica) |
| `path` | Ruta HTTP accedida (si aplica) |
| `command` | Comando SSH ejecutado (si aplica) |
| `environment` | honeypot |
| `vlan` | 50 |
| `host` | honeypot-soc |

### Ejemplo de evento

```json
{
  "timestamp": "2026-04-23T20:27:17.913Z",
  "level": "WARNING",
  "service": "ssh",
  "action": "login_attempt",
  "src_ip": "185.220.101.42",
  "src_port": 54321,
  "username": "root",
  "password": "toor",
  "result": "failed",
  "hostname": "honeypot-soc",
  "environment": "honeypot",
  "vlan": "50",
  "host": "honeypot-soc",
  "message": "login_attempt"
}
```

### Rotación de logs

- Tamaño máximo: 10 MB por fichero
- Backups: 5 ficheros rotados

---

## 5. Detección de amenazas (`core/alerts.py`)

> El módulo `ThreatDetector` (alias `BruteForceDetector` para compatibilidad con `main.py`) implementa 4 detectores en memoria. Todos emiten eventos de nivel ERROR con `action` específico que el agente reenvía al dashboard y Wazuh procesa con sus reglas.

| Detector | Acción emitida | Condición |
|----------|---------------|-----------|
| Brute force | `brute_force` | ≥5 intentos fallidos de login por IP en 60s |
| Port scan | `port_scan` | Misma IP toca ≥3 servicios distintos en 30s |
| Credential stuffing | `credential_stuffing` | Misma contraseña contra ≥5 usuarios distintos en 60s |
| Decoy file access | `decoy_file_access` | Acceso a fichero señuelo de alta prioridad (passwords.txt, .env, keys.pem, etc.) |

Los umbrales son configurables en `config.yaml`:

```yaml
alerts:
  brute_force:
    threshold: 5
    window_seconds: 60
    whitelist:
      - "192.168.3.200"   # honeycos
      - "10.1.1.34"       # CT103 playbooks-dns
      - "127.0.0.1"
  port_scan:
    min_services: 3
    window_seconds: 30
  credential_stuffing:
    min_users: 5
    window_seconds: 60
```

---

## 6. Agente (`agent.py`)

> El agente lee el log del honeypot en tiempo real e incluye dos mecanismos de protección ante scans masivos: deduplicación y throttling. El health check periódico permite monitorizar la actividad real del agente.

| Campo | Valor |
|-------|-------|
| Ruta | `/opt/honeypot/agent.py` |
| Servicio | `honeypot-agent.service` |
| Cola local | 500 eventos en memoria si la API no responde |
| Retry | 5 intentos con backoff exponencial |
| Token | `X-Agent-Token: honeypot-soc-2026` |
| Log propio | `/var/log/honeypot/agent.log` |

### Deduplicación

Descarta eventos idénticos en menos de 1 segundo. Clave: `(service, src_ip, action, username, path, command)`. Evita duplicados de clientes SSH que reenvían el mismo intento.

### Throttling

Máximo 5 eventos de la misma `(service, src_ip, action)` en 10 segundos. Las acciones de alta prioridad nunca se throttlean: `brute_force`, `command`, `port_scan`, `credential_stuffing`, `decoy_file_access`.

### Health check

Cada 5 minutos loguea en `agent.log`:

```
Health check — cola: 0 | procesados: 12 (2.4/min) | throttleados: 3 | deduplicados: 1
```

---

## 7. Dependencias Python

| Librería | Versión | Uso |
|----------|---------|-----|
| paramiko | 4.0.0 | Servicio SSH |
| pyftpdlib | 2.2.0 | Servicio FTP |
| impacket | 0.13.0 | Servicio SMB |
| aiohttp | 3.13.5 | Servicios HTTP/HTTPS |
| python-json-logger | 4.1.0 | Logging JSON |
| cryptography | 46.0.7 | Certificado SSL |
| pyyaml | 6.0.3 | Config YAML |

> **Nota impacket:** La versión instalada tiene un bug con Python 3.11+ donde `pktFlags` llega como `bytes`. Se aplicó un parche directo en `/usr/local/lib/python3.11/dist-packages/impacket/smbserver.py`, función `queryFsInformation` (línea ~321), añadiendo normalización de tipo antes de la operación `&`. Si se actualiza impacket habrá que verificar si el bug está corregido o reaplicar el parche.

---

## 8. Servicio systemd

```ini
[Unit]
Description=Honeypot SOC honeycos
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/honeypot
ExecStart=/usr/bin/python3 /opt/honeypot/main.py
Restart=on-failure
RestartSec=5
TimeoutStopSec=10
KillMode=mixed
StandardOutput=journal
StandardError=journal
SyslogIdentifier=honeypot

[Install]
WantedBy=multi-user.target
```

> `KillMode=mixed` asegura que los hilos de FTP y SMB (que son bloqueantes) terminen correctamente al hacer `systemctl stop`, evitando que systemd tenga que usar SIGKILL tras el timeout.

```bash
systemctl status honeypot
systemctl start honeypot
systemctl stop honeypot
systemctl restart honeypot
journalctl -u honeypot -f
journalctl -u honeypot-agent -f
```

---

## 9. SSH de gestión

| Parámetro | Valor |
|-----------|-------|
| Puerto | 2222 |
| PermitRootLogin | prohibit-password |
| PasswordAuthentication | no |
| MaxAuthTries | 3 |

```bash
ssh -p 2222 root@10.1.1.130
```

---

## 10. Red y aislamiento

- VLAN50 tiene forwarding `REJECT` hacia todas las VLANs internas salvo excepciones
- Solo tiene salida a WAN para resolución DNS y actualizaciones
- Regla `rule[10]` — acceso SSH gestión desde honeycos (192.168.3.200:2222)
- Regla `rule[11]` — honeypot → Wazuh Manager (10.1.1.67:1514/1515)
- Regla `rule[12]` — Prometheus (CT101) → honeypot node_exporter (10.1.1.130:9100)
- Regla `rule[15]` — honeypot-agent → dashboard API (CT109:5000)

---

## 11. Wazuh Agent

| Campo | Valor |
|-------|-------|
| ID agente | 007 |
| Nombre | honeypot |
| Version | 4.14.4 |
| Estado | active |
| Manager | 10.1.1.67 |
| Log monitorizado | /var/log/honeypot/honeypot.log (formato JSON) |

### Reglas personalizadas (VM202)

Fichero: `/var/ossec/etc/rules/honeypot_rules.xml`

| ID | Nivel | Descripción | Grupo |
|----|-------|-------------|-------|
| 100500 | 3 | Evento genérico honeypot | honeypot |
| 100501 | 5 | Conexión detectada | honeypot, connection |
| 100502 | 8 | Intento de login | honeypot, authentication_failed |
| 100503 | 10 | Comando SSH ejecutado | honeypot, ssh, command |
| 100504 | 5 | Request HTTP/HTTPS | honeypot, http |
| 100505 | 10 | Acceso a ruta sensible / fichero señuelo | honeypot, http, suspicious |
| 100506 | 8 | Acceso a fichero FTP/SMB | honeypot, file_access |
| 100507 | 14 | Brute force detectado | honeypot, brute_force — mail: True |
| 100508 | 12 | Evento crítico (ERROR) | honeypot, high_severity |
| 100509 | 12 | Port scan detectado | honeypot, port_scan |
| 100510 | 12 | Credential stuffing detectado | honeypot, credential_stuffing |
| 100511 | 14 | Acceso a fichero señuelo crítico | honeypot, decoy_file_access — mail: True |

---

## 12. node_exporter

| Campo | Valor |
|-------|-------|
| Version | 1.8.2 |
| Puerto | 9100 |
| Binario | /usr/local/bin/node_exporter |
| Servicio | node_exporter.service (enabled, running) |
| Usuario | node_exporter |
| Target Prometheus | 10.1.1.130:9100 — UP |

---

## 13. Dashboard Grafana

| Campo | Valor |
|-------|-------|
| Título | Honeypot VM203 |
| UID | 39dd04b1-3625-4526-b239-3bad5eb2c35a |
| URL | /d/39dd04b1-3625-4526-b239-3bad5eb2c35a/honeypot-vm203 |
| Datasource | prometheus (cfgen8anxk16oa) — http://10.1.1.66:9090 |
| Refresh | 30s |

Paneles incluidos: CPU Usage %, RAM Usage %, Disco usado %, Tráfico de red, Conexiones TCP activas, Uptime, Load Average (1m).

---

## 14. DNS

| Registro | Tipo | Valor |
|----------|------|-------|
| honeypot.soc.local | A | 10.1.1.130 |
| 130.1.1.10.in-addr.arpa | PTR | honeypot.soc.local. |
