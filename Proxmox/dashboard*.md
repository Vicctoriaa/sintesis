# Dashboard Honeypot — Arquitectura de recolección de datos

## 1. Contexto

El honeypot (VM203 · 10.1.1.130 · VLAN50) genera eventos JSON estructurados en `/var/log/honeypot/honeypot.log`. Un agente Python en VM203 lee esos eventos en tiempo real, aplica deduplicación y throttling, y los envía a una API Flask en CT109 (VLAN30), que los almacena en SQLite y los sirve al dashboard HTML.

---

## 2. Arquitectura implementada — Opción B (agente Python + HTTP POST)

```
┌─────────────────────────────────────────────────┐
│  VLAN50 — Honeypot (aislado)                    │
│                                                  │
│  VM203 · 10.1.1.130                             │
│  ├── honeypot.service (SSH/FTP/HTTP/HTTPS/RDP/SMB)
│  ├── node_exporter :9100                        │
│  ├── wazuh-agent → VM202:1514                   │
│  └── honeypot-agent.service                     │
│      └── agent.py → CT109:5000 (rule[15])       │
└──────────────────────┬──────────────────────────┘
                       │ HTTP POST · rule[15] OpenWRT
                       │ VLAN50 → VLAN30:5000
┌──────────────────────▼──────────────────────────┐
│  VLAN30 — SOC                                    │
│                                                  │
│  CT109 · 10.1.1.69 · honeypot-dashboard         │
│  ├── dashboard-api.service (Flask :5000)         │
│  │   ├── /opt/dashboard-api/app.py              │
│  │   ├── events.db (SQLite, máx 10.000)         │
│  │   └── GeoLite2-City.mmdb (geolocalización)   │
│  └── nginx :80                                  │
│      ├── / → /var/www/html/ (dashboard HTML)    │
│      └── /api/ → proxy Flask:5000              │
└──────────────────────┬──────────────────────────┘
                       │ proxy_pass :8765 (CT105 Nginx)
┌──────────────────────▼──────────────────────────┐
│  Acceso externo — Basic Auth (admin)             │
│  http://192.168.3.200:8765                      │
│  Solo red 192.168.3.0/24 · autenticación requerida
└──────────────────────────────────────────────────┘
```

---

## 3. Componentes desplegados

### VM203 — Agente (`/opt/honeypot/agent.py`)

| Campo | Valor |
|-------|-------|
| Ruta | `/opt/honeypot/agent.py` |
| Servicio | `honeypot-agent.service` (enabled, running) |
| Función | `tail -f` del log · dedup · throttle · HTTP POST a CT109:5000 |
| Deduplicación | Descarta eventos idénticos en ventana de 1s |
| Throttling | Máx 5 eventos/10s por (service, src_ip, action) |
| Cola local | 500 eventos en memoria si la API no responde |
| Retry | 5 intentos con backoff exponencial |
| Token | `X-Agent-Token: honeypot-soc-2026` |
| Log propio | `/var/log/honeypot/agent.log` |
| Health check | Cada 5 min — loguea eventos procesados, throttleados y deduplicados |

### CT109 — API Flask (`/opt/dashboard-api/app.py`)

| Campo | Valor |
|-------|-------|
| VMID | 109 |
| Hostname | honeypot-dashboard |
| IP | 10.1.1.69/27 |
| VLAN | 30 — SOC |
| OS | Debian 12 |
| RAM | 1 GB |
| Disco | 16 GB |
| Servicio | `dashboard-api.service` (enabled, running) |
| Puerto Flask | 5000 (solo interno) |
| BD | `/opt/dashboard-api/events.db` (SQLite, máx 10.000 eventos) |
| GeoLite2 | `/opt/dashboard-api/GeoLite2-City.mmdb` (MaxMind, gratuito) |

#### Endpoints API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/events` | Recibe evento del agente (requiere X-Agent-Token) |
| GET | `/events` | Lista eventos con filtros (limit, service, action, level, src_ip, since) |
| GET | `/stats` | Estadísticas agregadas (ventana configurable, default 24h) |
| GET | `/geo` | Top IPs geolocalizadas con país, ciudad, coords y flag |
| GET | `/export` | Exporta eventos a CSV o JSON descargable |
| GET | `/db/stats` | Estado de la base de datos: tamaño, uso, distribución |
| GET | `/health` | Health check |

#### Parámetros de `/events` y `/export`

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `limit` | int | Máximo de eventos (default 100, max 1000; export max 50.000) |
| `service` | str | Filtrar por servicio (ssh, http, https, ftp, smb, rdp) |
| `action` | str | Filtrar por acción |
| `level` | str | Filtrar por nivel (INFO, WARNING, ERROR) |
| `src_ip` | str | Filtrar por IP origen |
| `since` | str | ISO8601 sin offset — solo eventos posteriores |
| `format` | str | Solo `/export`: `csv` (default) o `json` |
| `hours` | int | Solo `/export`: ventana en horas (0 = todo) |

#### Base de datos SQLite

La BD tiene índices compuestos para optimizar las queries más frecuentes:

```sql
-- Índices creados en init_db() y manualmente si la BD ya existía:
CREATE INDEX idx_received          ON events(received_at);
CREATE INDEX idx_received_service  ON events(received_at, service);
CREATE INDEX idx_received_action   ON events(received_at, action);
CREATE INDEX idx_received_ip       ON events(received_at, src_ip);
CREATE INDEX idx_level             ON events(level);
CREATE INDEX idx_src_ip            ON events(src_ip);
```

La limpieza de eventos antiguos (máx 10.000) se ejecuta cada 100 inserts en lugar de en cada INSERT, reduciendo la carga durante scans masivos.

Los timestamps se almacenan sin offset UTC (`2026-04-23T20:17:46.539850`) para que las comparaciones string de SQLite funcionen correctamente.

#### Geolocalización (GeoLite2)

La API usa `geoip2` + `GeoLite2-City.mmdb` para geolocalizar las IPs atacantes. Es opcional — si el fichero no existe el endpoint `/geo` responde igualmente con coordenadas `0,0` y país "Desconocido".

```bash
# Instalación
pip install geoip2 --break-system-packages
# Descargar GeoLite2-City.mmdb de https://www.maxmind.com/en/geolite2/signup
cp GeoLite2-City.mmdb /opt/dashboard-api/GeoLite2-City.mmdb
systemctl restart dashboard-api
```

Las IPs privadas (`10.x.x.x`, `192.168.x.x`) no se geolocalización — comportamiento esperado.

### CT109 — Dashboard HTML (`/var/www/html/`)

| Fichero | Descripción |
|---------|-------------|
| `index.html` | Estructura HTML — 5 pestañas (Resumen, Eventos, IPs, Servicios, Logs) |
| `assets/css/dashboard.css` | Estilos completos |
| `assets/js/charts.js` | Reloj con timezone real, gráfico tráfico 24h, donut servicios HTTP/HTTPS separados |
| `assets/js/views.js` | Lógica de pestañas, mapa D3 con geolocalización, tablas, logs, servicios |
| `assets/js/api.js` | Integración API Flask — refresh cada 30s, polling logs cada 3s, exportación |

---

## 4. Reglas de red

### OpenWRT (VM201)

| Rule | Nombre | Descripción |
|------|--------|-------------|
| rule[15] | honeypot-to-dashboard-api | VLAN50 → VLAN30 · 10.1.1.69:5000 · TCP |

### honeycos — iptables

| Regla | Descripción |
|-------|-------------|
| PREROUTING DNAT | `tcp dpt:8765 → 10.1.1.35:8765` |
| FORWARD ACCEPT | `tcp dpt:8765 → 10.1.1.35` |
| POSTROUTING MASQUERADE | `10.1.1.0/24 → 0.0.0.0/0` |

### CT105 — Nginx proxy

```nginx
server {
    listen 8765;
    auth_basic "SOC honeycos — Dashboard Honeypot";
    auth_basic_user_file /etc/nginx/.htpasswd-dashboard;
    location / {
        proxy_pass http://10.1.1.69:80;
    }
}
```

---

## 5. Flujo de datos

```
VM203 honeypot.log
    └── agent.py (tail -f)
         ├── deduplicación (ventana 1s)
         ├── throttling (max 5 eventos/10s por ip+acción)
         └── HTTP POST /events [X-Agent-Token: honeypot-soc-2026]
                 └── CT109 Flask API
                         ├── SQLite events.db (índices compuestos)
                         └── GeoLite2-City.mmdb (geolocalización)
                                 └── GET /stats · /events · /geo (cada 30s)
                                         └── Dashboard HTML (navegador)
                                                 └── http://192.168.3.200:8765
```

**Latencia extremo a extremo:** ~1-3 segundos entre evento en el honeypot y aparición en el dashboard.

---

## 6. Acceso

| URL | Descripción |
|-----|-------------|
| `http://192.168.3.200:8765` | Dashboard (Basic Auth — usuario: admin) |
| `http://10.1.1.69/api/health` | Health check API |
| `http://10.1.1.69/api/stats` | Estadísticas |
| `http://10.1.1.69/api/events` | Eventos |
| `http://10.1.1.69/api/geo` | IPs geolocalizadas |
| `http://10.1.1.69/api/export?format=csv` | Exportar eventos CSV |
| `http://10.1.1.69/api/db/stats` | Estado de la base de datos |

---

## 7. Dashboard — Pestañas

| Pestaña | Contenido | Fuente |
|---------|-----------|--------|
| Resumen | Métricas 24h, feed actividad, gráfico tráfico, top IPs, credenciales multi-servicio, donut HTTP/HTTPS separados, rutas HTTP | API `/stats` + `/events` |
| Eventos | Tabla interactiva con filtros (servicio, severidad, búsqueda libre), paginación, detalle expandible, botones exportar CSV/JSON | API `/events?limit=200` |
| IPs | Stats IPs únicas/países/críticas/brute force, tabla top IPs con banderas reales (flagcdn.com), barras por país, mapa D3 con marcadores geolocalizados y animación de pulso | API `/geo` |
| Servicios | Cards por servicio (hits reales), timeline 12h con datos reales, acciones detectadas, credenciales multi-servicio (SSH+HTTP+FTP), rutas HTTP más accedidas, estado técnico | API `/stats` + `/events` |
| Logs | Terminal en vivo con polling incremental cada 3s, filtros nivel/servicio/búsqueda, distribución por nivel y servicio, botones exportar CSV/JSON | API `/events` (incremental) |

### Exportación de eventos

Disponible desde las pestañas Logs y Eventos mediante botones `⬇ CSV` y `⬇ JSON`, o directamente:

```bash
# CSV de las últimas 24h
curl "http://10.1.1.69/api/export?format=csv&hours=24" -o eventos.csv

# JSON de eventos SSH de los últimos 7 días
curl "http://10.1.1.69/api/export?format=json&hours=168&service=ssh" -o ssh.json
```

---

## 8. Pendientes CT109

| Tarea | Prioridad |
|-------|-----------|
| node_exporter (puerto 9100) | Media |
| Wazuh Agent | Media |
| DNS honeypot-dashboard.soc.local | Media |
| Añadir target en Prometheus CT101 | Media |
