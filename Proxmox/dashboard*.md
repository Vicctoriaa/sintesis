# Dashboard Honeypot — Arquitectura de recolección de datos

**SOC honeycos**

---

## 1. Contexto

El honeypot (VM203 · 10.1.1.130 · VLAN50) genera eventos JSON estructurados en `/var/log/honeypot/honeypot.log`. Un agente Python en VM203 lee esos eventos en tiempo real y los envía a una API Flask en CT109 (VLAN30), que los almacena en SQLite y los sirve al dashboard HTML.

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
│  │   └── /opt/dashboard-api/app.py              │
│  │       └── events.db (SQLite)                 │
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
| Función | `tail -f` del log · parse JSON · HTTP POST a CT109:5000 |
| Cola local | 500 eventos en memoria si la API no responde |
| Retry | 5 intentos con backoff exponencial |
| Token | `X-Agent-Token: honeypot-soc-2026` |
| Log propio | `/var/log/honeypot/agent.log` |

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

#### Endpoints API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/events` | Recibe evento del agente (requiere X-Agent-Token) |
| GET | `/events` | Lista eventos con filtros (limit, service, action, level, src_ip, since) |
| GET | `/stats` | Estadísticas agregadas (ventana configurable, default 24h) |
| GET | `/health` | Health check |

### CT109 — Dashboard HTML (`/var/www/html/`)

| Fichero | Descripción |
|---------|-------------|
| `index.html` | Estructura HTML — 5 pestañas (Resumen, Eventos, IPs, Servicios, Logs) |
| `assets/css/dashboard.css` | Estilos completos |
| `assets/js/charts.js` | Gráfico de tráfico 24h + donut servicios (Canvas) |
| `assets/js/views.js` | Lógica de pestañas, tabla eventos, logs, IPs, servicios |
| `assets/js/api.js` | Integración API Flask — refresh cada 30s, polling logs cada 3s |

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
            └── HTTP POST /events (cada evento nuevo)
                    └── CT109 Flask API
                            └── SQLite events.db
                                    └── GET /stats · GET /events (cada 30s)
                                            └── Dashboard HTML (navegador)
                                                    └── http://192.168.3.200:8765
```

**Latencia extremo a extremo:** ~1-3 segundos entre evento en el honeypot y aparición en el dashboard.

---

## 6. Acceso

| URL | Descripción |
|-----|-------------|
| `http://192.168.3.200:8765` | Dashboard (Basic Auth — usuario: admin) |
| `http://10.1.1.69/api/health` | Health check API (red interna) |
| `http://10.1.1.69/api/stats` | Estadísticas (red interna) |
| `http://10.1.1.69/api/events` | Eventos (red interna) |

---

## 7. Dashboard — Pestañas

| Pestaña | Contenido | Fuente |
|---------|-----------|--------|
| Resumen | Métricas 24h, feed actividad, gráfico tráfico, top IPs, credenciales, servicios, rutas HTTP | API `/stats` + `/events` |
| Eventos | Tabla interactiva con filtros (servicio, severidad, búsqueda), paginación, detalle expandible | API `/events?limit=200` |
| IPs | Stats IPs únicas/países/brute force, tabla top IPs, barras por país, mapa D3 | API `/stats` (top_ips) |
| Servicios | Cards por servicio (hits), timeline 12h, acciones, credenciales SSH, rutas HTTP, estado técnico | API `/stats` + `/events` |
| Logs | Visor terminal en vivo (polling 3s), filtros nivel/servicio/búsqueda, distribución por nivel y servicio | API `/events` (incremental) |

---

## 8. Pendientes CT109

| Tarea | Prioridad |
|-------|-----------|
| node_exporter (puerto 9100) | Media |
| Wazuh Agent | Media |
| DNS honeypot-dashboard.soc.local | Media |
| Añadir target en Prometheus CT101 | Media |


