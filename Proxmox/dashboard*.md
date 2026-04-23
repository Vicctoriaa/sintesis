# Dashboard Honeypot — Arquitectura de recolección de datos


## Contexto

El honeypot (VM203 · 10.1.1.130 · VLAN50) genera eventos JSON estructurados en `/var/log/honeypot/honeypot.log`. El objetivo es que un nodo central pueda leer esos eventos en (casi) tiempo real y alimentar el dashboard sin que el honeypot tenga que exponer ningún puerto adicional ni cambiar su configuración de red.

---

## Restricciones de red

| Origen | Destino | Estado |
|--------|---------|--------|
| VLAN50 (honeypot) → VLANs internas | REJECT (OpenWRT) |
| VLAN20/30 → VLAN50 | OK (reglas específicas) |
| CT101 (Prometheus) → VM203:9100 | OK (rule[12]) |
| VM202 (Wazuh) → VM203:1514/1515 | OK (rule[11]) |

**Consecuencia importante:** el honeypot no puede iniciar conexiones hacia la red interna, pero la red interna sí puede conectarse al honeypot. Esto condiciona la arquitectura — el agente no puede hacer push hacia el servidor central directamente, salvo que se abra una regla nueva en OpenWRT.

---

## Arquitectura


### Agente Python con HTTP POST

```
VM203 (honeypot)                    CT104 / CT nuevo (VLAN20/30)
─────────────────                   ────────────────────────────
agente.py                           servidor API (Flask/FastAPI)
  │                                   │
  │  tail -f honeypot.log             │  POST /events  ──► base de datos
  │  detecta líneas nuevas            │                    (SQLite/JSON)
  └──── HTTP POST ──────────────────► │
        cada evento nuevo             │  GET /events   ◄── dashboard
                                      │  GET /stats        fetch() 30s
```

**Cómo funciona:**
Un script Python ligero en VM203 hace `tail -f` del log y por cada línea nueva envía un HTTP POST al servidor central. El servidor acumula los eventos y los sirve como API JSON al dashboard.

**Requiere:** una regla nueva en OpenWRT que permita `VLAN50 → servidor_central:puerto_api`.

**Ventajas:**
- Latencia muy baja (~1-2 segundos entre evento y dashboard)
- El agente es ligero (~50 líneas de Python)
- El servidor puede filtrar, agregar y servir estadísticas
- Arquitectura escalable — se pueden añadir más fuentes fácilmente

**Desventajas:**
- Requiere abrir una regla en OpenWRT
- Si el servidor cae, los eventos se pierden (mitigable con cola local)
- Más componentes que gestionar

**Componentes:**
```
VM203
└── /opt/honeypot/agent.py          # Lee log, hace POST

CT109 (VLAN20/30)
├── /opt/dashboard-api/             # Servidor Flask/FastAPI
│   ├── app.py                      # API REST
│   ├── db.py                       # SQLite o JSON en disco
│   └── requirements.txt
└── /var/www/dashboard/             # Ficheros HTML/CSS/JS del dashboard
    └── honeypot-dashboard.html
```

**Regla OpenWRT a añadir:**
```
# VM203 (VLAN50) → servidor API (VLAN20) puerto 5000
uci add firewall rule
uci set firewall.@rule[-1].src='vlan50'
uci set firewall.@rule[-1].dest='vlan20'
uci set firewall.@rule[-1].dest_ip='10.1.1.37'   # CT104
uci set firewall.@rule[-1].dest_port='5000'
uci set firewall.@rule[-1].proto='tcp'
uci set firewall.@rule[-1].target='ACCEPT'
uci commit firewall && /etc/init.d/firewall restart
```

---

## Plan de implementación

### Fase 1 — Servidor API (CT104 o CT nuevo)

1. Instalar dependencias: `pip install flask`
2. Crear `app.py` con endpoints:
   - `POST /events` — recibe eventos del agente
   - `GET /events` — devuelve últimos N eventos (con filtros)
   - `GET /stats` — devuelve estadísticas agregadas
3. Configurar como servicio systemd
4. Configurar Nginx como proxy inverso (ya existe CT105)

### Fase 2 — Agente en VM203

1. Crear `/opt/honeypot/agent.py`:
   - `tail -f` del log con `follow=True`
   - Parse de cada línea JSON
   - HTTP POST al servidor API con retry en caso de fallo
   - Cola local en memoria para eventos pendientes
2. Configurar como servicio systemd
3. Añadir regla OpenWRT

### Fase 3 — Dashboard

1. Modificar el `honeypot-dashboard.html` existente
2. Reemplazar los datos estáticos por `fetch()` al endpoint de la API
3. Añadir auto-refresh cada 30 segundos
4. Desplegar en CT104 o CT105 (Nginx ya configurado)

---

## Esquema de red final

```
                    ┌─────────────────────────────────────────┐
                    │  VLAN50 — Honeypot (aislado)            │
                    │                                          │
                    │  VM203 · 10.1.1.130                     │
                    │  ├── honeypot.service (6 servicios)      │
                    │  ├── node_exporter :9100                 │
                    │  ├── wazuh-agent → VM202:1514            │
                    │  └── agent.py → CT104:5000 (nueva regla)│
                    └────────────────┬────────────────────────┘
                                     │ HTTP POST (nueva regla OpenWRT)
                    ┌────────────────▼────────────────────────┐
                    │  VLAN20 — Servicios                      │
                    │                                          │
                    │  CT104 · 10.1.1.37                      │
                    │  ├── dashboard-api.service (Flask :5000) │
                    │  └── nginx :8765 → dashboard HTML        │
                    └────────────────┬────────────────────────┘
                                     │ proxy_pass (CT105 Nginx)
                    ┌────────────────▼────────────────────────┐
                    │  Acceso externo                          │
                    │  http://192.168.3.200:8765/dashboard    │
                    └─────────────────────────────────────────┘
```
