# Sistema Honeypot

## 1. Visión general

El sistema honeypot SOC honeycos está compuesto por dos máquinas virtuales que trabajan en conjunto: VM203 actúa como honeypot expuesto, simulando servicios reales para atraer atacantes, y CT109 actúa como backend de análisis, almacenando y visualizando los eventos capturados en tiempo real.

```
┌───────────────────────────────────────────────────┐
│  VLAN50 — Honeypot (aislado)                      │
│                                                   │
│  VM203 · 10.1.1.130                               │
│  ├── honeypot.service (SSH/FTP/HTTP/HTTPS/RDP/SMB)|
│  ├── honeypot-agent.service                       │
│  │   └── agent.py → CT109:5000 (rule[15])         │
│  ├── honeypot-heartbeat.service                   │
│  │   └── heartbeat.py → CT109:5000/system         │
│  ├── node_exporter :9100                          │
│  └── wazuh-agent → VM202:1514                     │
└──────────────────────┬────────────────────────────┘
                       │ HTTP POST · rule[15] OpenWRT
                       │ VLAN50 → VLAN30:5000
┌──────────────────────▼────────────────────────────┐
│  VLAN30 — SOC                                     │
│                                                   │
│  CT109 · 10.1.1.69 · honeypot-dashboard           │
│  ├── dashboard-api.service (Flask :5000)          │
│  │   ├── /opt/dashboard-api/app.py                │
│  │   ├── events.db (SQLite, max 10.000)           │
│  │   ├── system_status (tabla SQLite)             │
│  │   └── GeoLite2-City.mmdb (geolocalización)     │
│  └── nginx :80                                    │
│      ├── / → /var/www/html/ (dashboard HTML)      │
│      └── /api/ → proxy Flask:5000                 │
└──────────────────────┬────────────────────────────┘
                       │ proxy_pass :8765 (CT105 Nginx)
┌──────────────────────▼────────────────────────────┐
│  Acceso externo — Basic Auth (admin)              │
│  http://192.168.3.200:8765                        │
│  Solo red 192.168.3.0/24 · autenticación requerida|
└───────────────────────────────────────────────────┘
```

### Flujo de datos

```
VM203 honeypot.log
    └── agent.py (tail -f)
         ├── deduplicación (ventana 1s)
         ├── throttling (max 5 eventos/10s por ip+accion)
         └── HTTP POST /events [X-Agent-Token: desde /etc/honeypot/agent.secret]
                 └── CT109 Flask API
                         ├── SQLite events.db (indices compuestos)
                         └── GeoLite2-City.mmdb (geolocalización)
                                 └── GET /stats · /events · /geo (cada 30s)
                                         └── Dashboard HTML (navegador)
                                                 └── http://192.168.3.200:8765

VM203 heartbeat.py (servicio independiente)
    └── Comprueba puertos con ss (sin conexión TCP)
    └── HTTP POST /system cada 30s [X-Agent-Token: desde /etc/honeypot/agent.secret]
            └── CT109 SQLite system_status (UPSERT — 1 sola fila)
                    └── GET /system (dashboard — cada 30s)
```

---

# PARTE I — Honeypot (VM203)

---

## 2. Información general

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

## 3. Estructura del proyecto

> El honeypot está desarrollado en Python y estructurado en módulos independientes por servicio. `main.py` actúa como punto de entrada que arranca todos los listeners en paralelo. El módulo `core/` contiene la lógica transversal de logging y detección, desacoplada de cada servicio individual.

```
/opt/honeypot/
├── config.yaml          # Configuración central
├── main.py              # Entry point — arranca todos los servicios
├── agent.py             # Agente de envío de eventos al dashboard
├── heartbeat.py         # Heartbeat de estado del sistema (servicio independiente)
├── setup_secret.sh      # Script de instalación del token de API
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

## 4. Servicios simulados

> Cada servicio simula el comportamiento real del protocolo correspondiente para que los escaneos automatizados y los atacantes no lo detecten fácilmente como honeypot. El objetivo es que interactúen el máximo tiempo posible, generando eventos que el dashboard y Wazuh procesarán y correlacionarán.

| Servicio | Puerto | Librería | Capacidades |
|----------|--------|----------|-------------|
| SSH | 22 | paramiko | Shell interactiva completa, pipes, historial 120 cmds, captura credenciales y comandos, expansión de variables de entorno |
| FTP | 21 | pyftpdlib | Filesystem virtual, captura logins con password, transferencias, comandos post-login, alertas decoy_file_access |
| HTTP | 80 | aiohttp | ~60 rutas señuelo, headers realistas, panel admin con cookie falsa, captura credenciales completas, alertas decoy_file_access |
| HTTPS | 443 | aiohttp + ssl | Igual que HTTP con certificado autofirmado y SAN |
| RDP | 3389 | asyncio | Handshake en 3 fases, captura mstshash, clientName y NTLM |
| SMB | 445 | impacket | 6 shares falsos, ficheros señuelo creíbles, detección SMB1 y SMB2, extracción username NTLM real |

### SSH

> Se emula un servidor OpenSSH con banner real. La shell falsa soporta pipes, redirecciones y encadenamiento de comandos para maximizar el tiempo de interacción del atacante. Los delays artificiales por tipo de comando dificultan el fingerprinting automático.

- Banner: `SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6`
- Shell falsa con soporte de pipes (`|`), redirecciones (`>`, `>>`), encadenamiento (`&&`, `;`)
- Historial de 120 comandos realistas (backups, deploys, análisis de logs)
- Delays artificiales por tipo de comando (`apt` 1.5-3s, `find` 0.2-0.6s, etc.)
- Hostname consistente en todos los contextos: prompt, `/etc/hostname`, `/etc/hosts`, `auth.log`
- Comandos soportados: `ls`, `cat`, `ps`, `netstat`, `env`, `history`, `crontab`, `find`, `wget`, `curl`, `df`, `free`, `last`, `who`, `ufw`, `systemctl`, `echo`, `printenv`, `export`, y más
- Expansión de variables de entorno: `$VAR` y `${VAR}` — `echo $DB_PASSWORD` devuelve `Sup3rS3cr3t!`
- Variables de entorno simuladas: `DB_PASSWORD`, `DB_HOST`, `DB_USER`, `MYSQL_PWD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `JWT_SECRET`, `REDIS_PASSWORD`
- Captura `username` + `password` en cada `login_attempt`, ambos enviados al detector de credential stuffing

### HTTP/HTTPS

> Las rutas están diseñadas para atraer scanners automáticos y atacantes. Todos los eventos HTTP capturan User-Agent, Referer y X-Forwarded-For. Los headers de respuesta son realistas para no ser detectados como honeypot.

Headers de respuesta: `Server: Apache/2.4.57 (Ubuntu)`, `X-Powered-By: PHP/8.1.12`

Rutas principales: `/` (Apache default), `/admin` (panel con cookie falsa), `/login`, `/phpmyadmin`, `/wp-admin`, `/manager` (Tomcat 401), `/.env`, `/config.php`, `/.git/config`, `/actuator/env`, `/server-status`, `/xmlrpc.php`, y ~50 rutas adicionales de scanner logueadas como `WARNING scanner_probe`.

Todos los paneles de login (`/admin`, `/login`, `/phpmyadmin`, `/wp-admin`) capturan `username` y `password` del POST y los pasan al detector de credential stuffing. Los ficheros sensibles (`/.env`, `/config.php`, `/.git/config`, `/actuator/env`, `/backup.zip`) disparan alertas `decoy_file_access` inmediatas.

### FTP

> El sistema de ficheros virtual incluye 12 ficheros señuelo en 4 directorios. Los comandos post-login también se capturan y loggean.

- `/` — `backup.tar.gz`, `passwords.txt`, `config.bak`, `database.sql`, `.env`
- `/uploads` — `shell.php`, `malware.exe`, `readme.txt`, `config_dump.json`
- `/private` — `credentials.txt`, `keys.pem`, `secret.conf`
- `/logs` — `access.log`, `error.log`

Comandos capturados post-login: `DELE`, `MKD`, `RMD`, `RNFR`, `SITE`

La descarga de cualquier fichero señuelo (p. ej. `passwords.txt`, `.env`, `keys.pem`) dispara una alerta `decoy_file_access` inmediata con cooldown de 5 minutos por IP+fichero. El password del intento de login se envía al detector de credential stuffing.

### SMB

> Se simulan 6 shares con ficheros señuelo de contenido creíble (sin strings "FAKE" visibles). Los ficheros contienen credenciales falsas, configuraciones de red, logs y documentos financieros.

| Share | Descripción | Ficheros señuelo |
|-------|-------------|-----------------|
| `ADMIN$` | Remote Admin | `system_info.txt`, `install_log.txt` |
| `C$` | Default share | `deployment_notes.txt`, `hosts.bak` |
| `Backups` | Company Backups | `credentials_backup.txt`, `backup.log`, `db_backup.sql.gz` |
| `Finance` | Finance Department | `Q1_2026_Summary.txt`, `salaries_2026.xlsx` |
| `IT$` | IT Department | `network_diagram.txt`, `admin_accounts.txt`, `vpn_config.ovpn` |
| `Logs` | System Logs | `auth.log`, `access.log` |

El servicio detecta tanto SMB1 (`\xffSMB`) como SMB2/3 (`\xfeSMB`) por el magic de cabecera. Para cada protocolo se procesan SESSION_SETUP (autenticación), TREE_CONNECT (acceso a share), WRITE (escritura) y CREATE (apertura de fichero en SMB2). El username NTLM se extrae del mensaje Authenticate (tipo 3) cuando está disponible. Todos los eventos incluyen el campo `protocol: "SMB1"` o `"SMB2"`.

### RDP

> El handshake RDP simula 3 fases del protocolo para parecer un servidor real. Los scanners que solo envían paquetes cortos son detectados y logueados como `scanner_probe`.

- Fase 1: X.224 CR → extrae `requestedProtocols`, cookie `mstshash` y `clientName`
- Fase 2: MCS Connect Initial → responde con MCS Connect Response con BER encoding válido
- Fase 3: Espera CredSSP/NTLM → extrae `ntlm_user` si el cliente usa NLA
- Detección de scanners: paquetes < 11 bytes → `scanner_probe`
- Timeout de 45s por conexión

---

## 5. Logging

### Ubicación

```
/var/log/honeypot/honeypot.log   # Eventos JSON de todos los servicios
/var/log/honeypot/agent.log      # Log del agente (envío a API)
```

### Formato JSON

| Campo | Descripción |
|-------|-------------|
| `timestamp` | ISO8601 UTC |
| `level` | INFO / WARNING / ERROR |
| `service` | ssh / ftp / http / https / rdp / smb / main |
| `action` | connection / login_attempt / command / request / file_access / brute_force / port_scan / credential_stuffing / decoy_file_access / scanner_probe / share_access / write_attempt / file_open |
| `src_ip` | IP de origen |
| `src_port` | Puerto de origen |
| `username` | Usuario intentado (si aplica) |
| `password` | Contraseña intentada (si aplica) |
| `protocol` | SMB1 / SMB2 (solo eventos SMB) |
| `share` | Share SMB accedido (si aplica) |
| `user_agent` | User-Agent HTTP (si aplica) |
| `path` | Ruta HTTP accedida (si aplica) |
| `command` | Comando SSH ejecutado (si aplica) |
| `file` | Fichero accedido (FTP/SMB/HTTP decoy) |
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

---

## 6. Detección de amenazas (`core/alerts.py`)

> El módulo `ThreatDetector` (alias `BruteForceDetector` para compatibilidad con `main.py`) implementa 4 detectores en memoria. Todos emiten eventos de nivel ERROR con `action` específico que el agente reenvía al dashboard y Wazuh procesa con sus reglas.

| Detector | Acción emitida | Condición | Servicios activos |
|----------|---------------|-----------|-------------------|
| Brute force | `brute_force` | ≥5 intentos fallidos de login por IP en 60s | SSH, FTP, HTTP, HTTPS, RDP, SMB |
| Port scan | `port_scan` | Misma IP toca ≥3 servicios distintos en 30s | Todos |
| Credential stuffing | `credential_stuffing` | Misma contraseña contra ≥5 usuarios distintos en 60s | SSH, FTP, HTTP, HTTPS, SMB |
| Decoy file access | `decoy_file_access` | Acceso a fichero señuelo de alta prioridad | FTP, SMB, HTTP, HTTPS |

> **Nota:** El detector de credential stuffing requiere que el servicio pase la contraseña al método `record()`. SSH, FTP y HTTP/HTTPS lo hacen desde v4. SMB no transmite contraseñas en claro en el handshake NTLM — en su lugar se pasa el username extraído del token NTLM.

Umbrales configurables en `config.yaml`:

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

## 7.1. Agente (`agent.py`)

> El agente lee el log del honeypot en tiempo real e incluye dos mecanismos de protección ante scans masivos: deduplicación y throttling. El health check periódico permite monitorizar la actividad real del agente por servicio.

| Campo | Valor |
|-------|-------|
| Ruta | `/opt/honeypot/agent.py` |
| Servicio | `honeypot-agent.service` |
| Cola local | 500 eventos en memoria si la API no responde |
| Retry | 5 intentos con backoff exponencial |
| Token | Cargado desde `/etc/honeypot/agent.secret` o `$HONEYPOT_API_TOKEN` |
| HTTP | `urllib` stdlib — sin dependencias externas |
| Log propio | `/var/log/honeypot/agent.log` |
| Health check | Cada 5 min — loguea métricas globales y desglose por servicio |

**Deduplicación** — descarta eventos idénticos en menos de 1 segundo. Clave: `(service, src_ip, action, username, path, command)`.

**Throttling** — máximo 5 eventos de la misma `(service, src_ip, action)` en 10 segundos. Las claves inactivas se purgan periódicamente para evitar memory leak. Nunca se throttlean: `brute_force`, `command`, `port_scan`, `credential_stuffing`, `decoy_file_access`.

**Health check** — cada 5 minutos loguea dos líneas en `agent.log`:

### Seguridad del token

El token nunca está escrito en el código fuente. Se carga en este orden de preferencia:

1. Variable de entorno `HONEYPOT_API_TOKEN`
2. Fichero `/etc/honeypot/agent.secret` (primera línea)

---

## 7.2. Heartbeat (`heartbeat.py`)

> Servicio independiente que comprueba el estado real de los puertos del honeypot y lo envía al dashboard cada 30 segundos. Corre como servicio systemd separado de `honeypot-agent` para que siga informando incluso si el honeypot cae.

| Campo | Valor |
|-------|-------|
| Ruta | `/opt/honeypot/heartbeat.py` |
| Servicio | `honeypot-heartbeat.service` |
| Endpoint destino | `POST http://10.1.1.69:5000/system` |
| Intervalo | 30 segundos |
| Token | Cargado desde `/etc/honeypot/agent.secret` o `$HONEYPOT_API_TOKEN` |
| HTTP | `urllib` stdlib — sin dependencias externas |

**Comprobación de puertos** — usa `ss -tlnp` (sin conexión TCP) para detectar si cada servicio está escuchando. Esto evita que el honeypot registre conexiones falsas de `127.0.0.1` en su log.

**Payload enviado:**

```json
{
  "hostname": "honeypot",
  "ip": "10.1.1.130",
  "vlan": "50",
  "uptime": "3d 14h 22m",
  "services_up": 6,
  "services_total": 6,
  "services": {
    "ssh":   {"up": true, "port": 22,   "lib": "paramiko 4.0.0",  "banner": "..."},
    "http":  {"up": true, "port": 80,   "lib": "aiohttp 3.13.5",  "banner": "..."},
    "https": {"up": true, "port": 443,  "lib": "aiohttp + ssl",   "banner": "..."},
    "ftp":   {"up": true, "port": 21,   "lib": "pyftpdlib 2.2.0", "banner": "..."},
    "smb":   {"up": true, "port": 445,  "lib": "impacket 0.13.0", "banner": "..."},
    "rdp":   {"up": true, "port": 3389, "lib": "asyncio",         "banner": "..."}
  },
  "wazuh": {"active": true, "agent_id": "007"},
  "config": {
    "ssh_host_key":   "RSA 2048 (persistida)",
    "ftp_filesystem": "virtual · ficheros señuelo",
    "http_cert":      "autofirmado · válido 365d",
    "smb_shares":     "ADMIN$, C$, Backups, Finance, IT$, Logs",
    "rdp_ntlm":       "negotiate capturado",
    "whitelist_bf":   "192.168.3.200, 10.1.1.34"
  }
}
```

---

## 8. Dependencias Python

| Librería | Versión | Uso |
|----------|---------|-----|
| paramiko | 4.0.0 | Servicio SSH |
| pyftpdlib | 2.2.0 | Servicio FTP |
| impacket | 0.13.0 | Servicio SMB |
| aiohttp | 3.13.5 | Servicios HTTP/HTTPS |
| python-json-logger | 4.1.0 | Logging JSON |
| cryptography | 46.0.7 | Certificado SSL |
| pyyaml | 6.0.3 | Config YAML |

---

## 10. SSH de gestión

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

## 11. Red y aislamiento

> VLAN50 tiene forwarding `REJECT` hacia todas las VLANs internas salvo excepciones. Solo tiene salida a WAN para resolución DNS y actualizaciones.

| Regla | Descripción |
|-------|-------------|
| `rule[10]` | SSH gestión desde honeycos (192.168.3.200:2222) |
| `rule[11]` | honeypot → Wazuh Manager (10.1.1.67:1514/1515) |
| `rule[12]` | Prometheus → node_exporter (10.1.1.130:9100) |
| `rule[15]` | honeypot-agent + heartbeat → dashboard API (CT109:5000) |

---

## 12. Wazuh Agent

| Campo | Valor |
|-------|-------|
| ID agente | 007 |
| Nombre | honeypot |
| Version | 4.14.4 |
| Estado | active |
| Manager | 10.1.1.67 |
| Log monitorizado | /var/log/honeypot/honeypot.log (formato JSON) |

---

## 13. node_exporter y Grafana

| Campo | Valor |
|-------|-------|
| node_exporter version | 1.8.2 |
| Puerto | 9100 |
| Target Prometheus | 10.1.1.130:9100 — UP |

| Campo | Valor |
|-------|-------|
| Dashboard Grafana | Honeypot VM203 |
| UID | 39dd04b1-3625-4526-b239-3bad5eb2c35a |
| Datasource | prometheus — http://10.1.1.66:9090 |
| Refresh | 30s |

Paneles: CPU Usage %, RAM Usage %, Disco usado %, Tráfico de red, Conexiones TCP activas, Uptime, Load Average (1m).

---

# PARTE II — Dashboard (CT109)

---

## 14. Información general

| Campo | Valor |
|-------|-------|
| VMID | 109 |
| Hostname | honeypot-dashboard |
| IP | 10.1.1.69/27 |
| VLAN | 30 — SOC |
| OS | Debian 12 |
| RAM | 1 GB |
| Disco | 16 GB |

### Estructura de ficheros

```
/opt/dashboard-api/
├── app.py                  # API Flask v4
├── events.db               # SQLite (max 10.000 eventos + tabla system_status)
└── GeoLite2-City.mmdb      # Base de datos de geolocalización (MaxMind)

/etc/dashboard-api/
└── api.secret              # Token de API (600, root) — nunca en el código

/var/www/html/
├── index.html
└── assets/
    ├── css/dashboard.css   # Estilos — JetBrains Mono + Inter
    └── js/
        ├── charts.js       # Reloj, gráfico tráfico (labels dinamicas), donut servicios
        ├── views.js        # Logica de pestañas, mapa D3, tablas, logs, detalles tecnicos
        └── api.js          # Integración API — refresh 30s, polling logs 3s, /system
```

---

## 15. API Flask — Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/events` | Recibe evento del agente (requiere X-Agent-Token) |
| GET | `/events` | Lista eventos con filtros y paginación server-side |
| GET | `/stats` | Estadísticas agregadas (ventana configurable, default 24h) |
| GET | `/geo` | Top IPs geolocalizadas con país, ciudad, coords y flag |
| GET | `/export` | Exporta eventos a CSV o JSON descargable |
| GET | `/db/stats` | Estado de la BD: tamaño, uso, distribución |
| GET | `/health` | Health check |
| POST | `/system` | Recibe heartbeat de estado del honeypot (requiere X-Agent-Token) |
| GET | `/system` | Devuelve último estado del honeypot + antigüedad del heartbeat |

### Seguridad del token

El token nunca está escrito en el código fuente. Se carga en este orden de preferencia:

1. Variable de entorno `HONEYPOT_API_TOKEN`
2. Fichero `/etc/dashboard-api/api.secret` (primera línea)

```bash
# Instalación del token en CT109
mkdir -p /etc/dashboard-api
echo '<token>' > /etc/dashboard-api/api.secret
chmod 600 /etc/dashboard-api/api.secret
chown root:root /etc/dashboard-api/api.secret
systemctl restart dashboard-api
```

---

## 16. Base de datos SQLite


```sql
-- Tabla principal de eventos
CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    timestamp   TEXT, level TEXT, service TEXT,
    action TEXT, src_ip TEXT, src_port INTEGER,
    data TEXT NOT NULL
);

-- Indices compuestos para queries frecuentes
CREATE INDEX idx_received         ON events(received_at);
CREATE INDEX idx_received_service ON events(received_at, service);
CREATE INDEX idx_received_action  ON events(received_at, action);
CREATE INDEX idx_received_ip      ON events(received_at, src_ip);
CREATE INDEX idx_level            ON events(level);
CREATE INDEX idx_src_ip           ON events(src_ip);

-- Estado del sistema honeypot (una sola fila, UPSERT)
CREATE TABLE system_status (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    updated_at TEXT NOT NULL,
    data       TEXT NOT NULL
);
```

---

## 17. Geolocalización (GeoLite2)

La API usa `geoip2` + `GeoLite2-City.mmdb` para geolocalizar IPs atacantes. Las IPs privadas no se geolocalización.

```bash
pip install geoip2 --break-system-packages
# Descargar GeoLite2-City.mmdb desde https://www.maxmind.com/en/geolite2/signup
tar -xf GeoLite2-City_*.tar -C /tmp
cp /tmp/GeoLite2-City_*/GeoLite2-City.mmdb /opt/dashboard-api/
systemctl restart dashboard-api
```

---

## 18. Nginx y acceso externo

```nginx
# CT109 — /etc/nginx/sites-enabled/dashboard
server {
    listen 80;
    server_name 10.1.1.69;
    root /var/www/html;
    index index.html;
    location / { try_files $uri $uri/ =404; }
    location /api/ {
        proxy_pass http://127.0.0.1:5000/;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# CT105 — proxy externo con Basic Auth
server {
    listen 8765;
    auth_basic "SOC honeycos — Dashboard Honeypot";
    auth_basic_user_file /etc/nginx/.htpasswd-dashboard;
    location / { proxy_pass http://10.1.1.69:80; }
}
```
