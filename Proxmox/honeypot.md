# Honeypot VM203 — Documentación

**SOC honeycos · Abril 2026**

---

## 1. Información general

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

```
/opt/honeypot/
├── config.yaml          # Configuración central
├── main.py              # Entry point — arranca todos los servicios
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
│   └── alerts.py        # Detección brute force
└── logs/ -> /var/log/honeypot/
```

---

## 3. Servicios simulados

| Servicio | Puerto | Librería | Capacidades |
|----------|--------|----------|-------------|
| SSH | 22 | paramiko | Shell interactiva falsa, captura credenciales, logging de comandos |
| FTP | 21 | pyftpdlib | Filesystem virtual, captura logins y transferencias |
| HTTP | 80 | aiohttp | Rutas realistas (admin, phpMyAdmin, WordPress, .env) |
| HTTPS | 443 | aiohttp + ssl | Igual que HTTP con certificado autofirmado |
| RDP | 3389 | asyncio | Captura cookies mstshash y NTLM negotiate |
| SMB | 445 | impacket | Shares falsos, captura autenticación NTLM |

### SSH — Rutas simuladas

- Banner: `SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6`
- Acepta credenciales falsas definidas en `config.yaml` y abre shell interactiva
- Shell responde a: `ls`, `pwd`, `whoami`, `id`, `uname`, `hostname`, `ifconfig`
- Todos los intentos fallidos se logean y se cuentan para detección de brute force

### HTTP/HTTPS — Rutas simuladas

- `/` — Apache2 Ubuntu Default Page
- `/admin` — Panel de administración con formulario
- `/login` — Página de login genérica
- `/phpmyadmin` — Login phpMyAdmin
- `/wp-admin` — Login WordPress
- `/manager` — Tomcat Manager (401)
- `/.env` — Fichero de entorno con credenciales falsas
- `/config.php` — Configuración WordPress con credenciales falsas

### FTP — Filesystem virtual

- `/` — `backup.tar.gz`, `passwords.txt`, `config.bak`, `database.sql`
- `/uploads` — `shell.php`, `malware.exe`, `readme.txt`
- `/private` — `credentials.txt`, `keys.pem`, `secret.conf`

### SMB — Shares falsos

- `ADMIN$` — Remote Admin
- `C$` — Default share
- `Backups` — Company Backups
- `Finance` — Finance Department

---

## 4. Logging

### Ubicación

```
/var/log/honeypot/honeypot.log
```

### Formato JSON

| Campo | Descripción |
|-------|-------------|
| `timestamp` | ISO8601 UTC |
| `level` | INFO / WARNING / ERROR |
| `service` | ssh / ftp / http / https / rdp / smb |
| `action` | connection / login_attempt / command / request / file_access / brute_force |
| `src_ip` | IP de origen |
| `src_port` | Puerto de origen |
| `environment` | honeypot |
| `vlan` | 50 |
| `host` | honeypot-soc |

### Ejemplo de evento

```json
{
  "message": "request",
  "service": "http",
  "action": "request",
  "src_ip": "1.2.3.4",
  "src_port": 54321,
  "method": "GET",
  "path": "/.env",
  "status": 200,
  "user_agent": "curl/7.88.1",
  "timestamp": "2026-04-10T14:33:48.475Z",
  "level": "INFO",
  "hostname": "honeypot",
  "environment": "honeypot",
  "vlan": "50",
  "host": "honeypot-soc"
}
```

### Rotación de logs

- Tamaño máximo: 10 MB por fichero
- Backups: 5 ficheros rotados

---

## 5. Detección de brute force

| Parámetro | Valor |
|-----------|-------|
| Umbral | 5 intentos |
| Ventana | 60 segundos |
| Whitelist | 192.168.3.200, 10.1.1.34, 127.0.0.1 |

---

## 6. Dependencias Python

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

## 7. Servicio systemd

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
StandardOutput=journal
StandardError=journal
SyslogIdentifier=honeypot

[Install]
WantedBy=multi-user.target
```

```bash
systemctl status honeypot
systemctl start honeypot
systemctl stop honeypot
systemctl restart honeypot
journalctl -u honeypot -f
```

---

## 8. SSH de gestión

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

## 9. Red y aislamiento

- VLAN50 tiene forwarding `REJECT` hacia todas las VLANs internas salvo excepciones
- Solo tiene salida a WAN para resolución DNS y actualizaciones
- Regla `rule[10]` — acceso SSH gestión desde honeycos (192.168.3.200:2222)
- Regla `rule[11]` — honeypot → Wazuh Manager (10.1.1.67:1514/1515)
- Regla `rule[12]` — Prometheus (CT101) → honeypot node_exporter (10.1.1.130:9100)

---

## 10. Wazuh Agent

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

| ID | Nivel | Descripcion | Grupo |
|----|-------|-------------|-------|
| 100500 | 3 | Evento generico honeypot | honeypot |
| 100501 | 5 | Conexion detectada | honeypot, connection |
| 100502 | 8 | Intento de login | honeypot, authentication_failed |
| 100503 | 10 | Comando SSH ejecutado | honeypot, ssh, command |
| 100504 | 5 | Request HTTP/HTTPS | honeypot, http |
| 100505 | 10 | Acceso a ruta sensible | honeypot, http, suspicious |
| 100506 | 8 | Acceso a fichero FTP/SMB | honeypot, file_access |
| 100507 | 14 | Brute force detectado | honeypot, brute_force — mail: True |
| 100508 | 12 | Evento critico (ERROR) | honeypot, high_severity |

---

## 11. node_exporter

| Campo | Valor |
|-------|-------|
| Version | 1.8.2 |
| Puerto | 9100 |
| Binario | /usr/local/bin/node_exporter |
| Servicio | node_exporter.service (enabled, running) |
| Usuario | node_exporter |
| Target Prometheus | 10.1.1.130:9100 — UP |

---

## 12. Dashboard Grafana

| Campo | Valor |
|-------|-------|
| Titulo | Honeypot VM203 |
| UID | 39dd04b1-3625-4526-b239-3bad5eb2c35a |
| URL | /d/39dd04b1-3625-4526-b239-3bad5eb2c35a/honeypot-vm203 |
| Datasource | prometheus (cfgen8anxk16oa) — http://10.1.1.66:9090 |
| Refresh | 30s |

Paneles incluidos: CPU Usage %, RAM Usage %, Disco usado %, Trafico de red, Conexiones TCP activas, Uptime, Load Average (1m).

---

## 13. DNS

| Registro | Tipo | Valor |
|----------|------|-------|
| honeypot.soc.local | A | 10.1.1.130 |
| 130.1.1.10.in-addr.arpa | PTR | honeypot.soc.local. |

---

## 14. Pendientes

| Tarea | Prioridad | Estado |
|-------|-----------|--------|
| Instalar Wazuh Agent y crear decoder personalizado | Alta | ✅ Completado 2026-04-13 |
| Instalar node_exporter y añadir target en Prometheus | Alta | ✅ Completado 2026-04-13 |
| Crear dashboard Grafana honeypot | Media | ✅ Completado 2026-04-13 |
| Añadir registro DNS honeypot.soc.local | Media | ✅ Completado 2026-04-13 |

*Honeypot completamente integrado en el SOC — 2026-04-13*
