# Honeypot VM203 — Documentación

**SOC honeycos · Abril 2026**

---

## 1. Información general

| Campo | Valor |
|---|---|
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
|---|---|---|---|
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
- Los ficheros devuelven contenido falso con credenciales señuelo

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
Cada evento incluye los campos:

| Campo | Descripción |
|---|---|
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

Configurado en `config.yaml` sección `alerts`:

| Parámetro | Valor |
|---|---|
| Umbral | 5 intentos |
| Ventana | 60 segundos |
| Whitelist | 192.168.3.200, 10.1.1.34, 127.0.0.1 |

Cuando una IP supera el umbral en la ventana definida, se genera un evento de nivel `ERROR` con `action: brute_force` incluyendo el número de intentos y los usernames utilizados.

---

## 6. Dependencias Python

| Librería | Versión | Uso |
|---|---|---|
| paramiko | 4.0.0 | Servicio SSH |
| pyftpdlib | 2.2.0 | Servicio FTP |
| impacket | 0.13.0 | Servicio SMB |
| aiohttp | 3.13.5 | Servicios HTTP/HTTPS |
| python-json-logger | 4.1.0 | Logging JSON |
| cryptography | 46.0.7 | Certificado SSL |
| pyyaml | 6.0.3 | Config YAML |

---

## 7. Servicio systemd

```
/etc/systemd/system/honeypot.service
```

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

Comandos de gestión:

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
|---|---|
| Puerto | 2222 |
| PermitRootLogin | prohibit-password |
| PasswordAuthentication | no |
| MaxAuthTries | 3 |

Acceso desde honeycos:
```bash
ssh -p 2222 root@10.1.1.130
```

---

## 9. Red y aislamiento

- VLAN50 tiene forwarding `REJECT` hacia todas las VLANs internas (OpenWRT)
- Solo tiene salida a WAN (internet) para resolución DNS y actualizaciones
- Honeycos (192.168.3.200) tiene acceso al puerto 2222 via regla OpenWRT `rule[10]`
- El honeypot NO puede alcanzar: VLAN20 (Servicios), VLAN30 (SOC), VLAN40 (Producción)

---

## 10. Pendientes

| Tarea | Prioridad |
|---|---|
| Instalar Wazuh Agent y crear decoder personalizado | Alta |
| Instalar node_exporter y añadir target en Prometheus | Alta |
| Crear dashboard Grafana honeypot | Media |
| Añadir registro DNS honeypot.soc.local | Media |
