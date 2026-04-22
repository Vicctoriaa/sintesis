# Honeypot VM203 — Documentación

**SOC honeycos · Abril 2026**

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

> Cada servicio simula el comportamiento real del protocolo correspondiente para que los escaneos automatizados y los atacantes no lo detecten fácilmente como honeypot. El objetivo es que interactúen el máximo tiempo posible, generando eventos que Wazuh procesará y correlacionará.

| Servicio | Puerto | Librería | Capacidades |
|----------|--------|----------|-------------|
| SSH | 22 | paramiko | Shell interactiva falsa, captura credenciales, logging de comandos |
| FTP | 21 | pyftpdlib | Filesystem virtual, captura logins y transferencias |
| HTTP | 80 | aiohttp | Rutas realistas (admin, phpMyAdmin, WordPress, .env) |
| HTTPS | 443 | aiohttp + ssl | Igual que HTTP con certificado autofirmado |
| RDP | 3389 | asyncio | Captura cookies mstshash y NTLM negotiate |
| SMB | 445 | impacket | Shares falsos, captura autenticación NTLM |

### SSH — Rutas simuladas

> Se emula un servidor OpenSSH con banner real para pasar desapercibido ante herramientas de fingerprinting. Las credenciales aceptadas están definidas en `config.yaml` y dan acceso a una shell falsa que responde a comandos básicos, maximizando el tiempo de interacción del atacante y la cantidad de datos recopilados.

- Banner: `SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.6`
- Acepta credenciales falsas definidas en `config.yaml` y abre shell interactiva
- Shell responde a: `ls`, `pwd`, `whoami`, `id`, `uname`, `hostname`, `ifconfig`
- Todos los intentos fallidos se logean y se cuentan para detección de brute force

### HTTP/HTTPS — Rutas simuladas

> Las rutas están diseñadas para atraer scanners automáticos (como Nuclei o Nikto) y atacantes que buscan paneles de administración expuestos. Cada acceso genera un evento que revela las herramientas y técnicas del atacante.

- `/` — Apache2 Ubuntu Default Page
- `/admin` — Panel de administración con formulario
- `/login` — Página de login genérica
- `/phpmyadmin` — Login phpMyAdmin
- `/wp-admin` — Login WordPress
- `/manager` — Tomcat Manager (401)
- `/.env` — Fichero de entorno con credenciales falsas
- `/config.php` — Configuración WordPress con credenciales falsas

### FTP — Filesystem virtual

> El sistema de ficheros virtual simula un servidor con datos sensibles para atraer intentos de descarga. Los nombres de ficheros están elegidos deliberadamente para parecer valiosos y provocar interacción prolongada.

- `/` — `backup.tar.gz`, `passwords.txt`, `config.bak`, `database.sql`
- `/uploads` — `shell.php`, `malware.exe`, `readme.txt`
- `/private` — `credentials.txt`, `keys.pem`, `secret.conf`

### SMB — Shares falsos

> Se simulan los shares más habituales en entornos Windows corporativos. Los intentos de autenticación NTLM son especialmente valiosos para detectar herramientas de movimiento lateral como Responder o CrackMapExec.

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

> El logging estructurado en JSON facilita el parsing por parte del agente Wazuh y permite crear reglas y decoders precisos basados en campos específicos como `action`, `service` o `src_ip`, sin necesidad de expresiones regulares complejas.

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

> La rotación evita que el disco se llene en caso de actividad intensa. Con 5 ficheros de 10 MB se conservan hasta 50 MB de historial reciente sin intervención manual.

- Tamaño máximo: 10 MB por fichero
- Backups: 5 ficheros rotados

---

## 5. Detección de brute force

> El módulo `alerts.py` mantiene un contador por IP y servicio en memoria. Si una misma IP supera 5 intentos en 60 segundos se genera un evento de nivel 14 en Wazuh (el más alto de las reglas honeypot), que dispara una alerta por correo. Las IPs de gestión están en whitelist para evitar falsos positivos durante pruebas o administración.

| Parámetro | Valor |
|-----------|-------|
| Umbral | 5 intentos |
| Ventana | 60 segundos |
| Whitelist | 192.168.3.200, 10.1.1.34, 127.0.0.1 |

---

## 6. Dependencias Python

> Cada librería cubre un protocolo o función específica. `impacket` y `paramiko` son las más pesadas pero imprescindibles para emular SMB y SSH con fidelidad suficiente. `python-json-logger` estandariza el formato de salida para todos los servicios.

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

> Registrar el honeypot como servicio systemd garantiza que arranque automáticamente con el sistema y se reinicie solo si falla. `RestartSec=5` introduce una pequeña pausa entre reinicios para evitar bucles rápidos en caso de error persistente. Los logs van al journal del sistema, accesibles con `journalctl`.

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

> El honeypot expone el puerto 22 como servicio simulado para atacantes. Para la gestión legítima se usa el puerto 2222, con autenticación exclusivamente por clave pública, eliminando el riesgo de que las credenciales de gestión sean capturadas por el propio honeypot o por un atacante que esté monitorizando el tráfico.

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

> El aislamiento de red es crítico: si el honeypot fuera comprometido, el atacante no debe poder pivotar hacia el resto del SOC. Las únicas excepciones al bloqueo total son las estrictamente necesarias para la operación: gestión SSH, envío de eventos a Wazuh y scraping de métricas por Prometheus.

- VLAN50 tiene forwarding `REJECT` hacia todas las VLANs internas salvo excepciones
- Solo tiene salida a WAN para resolución DNS y actualizaciones
- Regla `rule[10]` — acceso SSH gestión desde honeycos (192.168.3.200:2222)
- Regla `rule[11]` — honeypot → Wazuh Manager (10.1.1.67:1514/1515)
- Regla `rule[12]` — Prometheus (CT101) → honeypot node_exporter (10.1.1.130:9100)

---

## 10. Wazuh Agent

> El agente Wazuh monitoriza el fichero de log del honeypot en tiempo real y envía los eventos al Manager para su correlación con el resto de la infraestructura SOC. Las reglas personalizadas permiten asignar niveles de severidad diferenciados según el tipo de actividad detectada, desde una simple conexión hasta un brute force confirmado.

| Campo | Valor |
|-------|-------|
| ID agente | 007 |
| Nombre | honeypot |
| Version | 4.14.4 |
| Estado | active |
| Manager | 10.1.1.67 |
| Log monitorizado | /var/log/honeypot/honeypot.log (formato JSON) |

### Reglas personalizadas (VM202)

> Los niveles de severidad siguen la escala de Wazuh (0–15). El nivel 14 del brute force es el más alto asignado y es el único que tiene `mail: True`, lo que significa que genera una alerta inmediata por correo. El resto alimenta el dashboard y los dashboards de Grafana sin notificación activa.

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

> `node_exporter` expone métricas del sistema operativo de la VM (CPU, RAM, disco, red) para que Prometheus las recoja y Grafana las visualice. Corre con un usuario sin privilegios dedicado siguiendo el principio de mínimo privilegio.

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

> El dashboard permite supervisar la salud del sistema y detectar anomalías de rendimiento relacionadas con la actividad del honeypot, como picos de CPU o saturación de red durante un escaneo masivo o un ataque intenso.

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

> Los registros DNS permiten referenciar el honeypot por nombre en lugar de por IP dentro de la red interna, facilitando la gestión y la lectura de logs cuando aparece el hostname en lugar de la dirección numérica.

| Registro | Tipo | Valor |
|----------|------|-------|
| honeypot.soc.local | A | 10.1.1.130 |
| 130.1.1.10.in-addr.arpa | PTR | honeypot.soc.local. |

---

*Honeypot completamente integrado en el SOC — 2026-04-13*
