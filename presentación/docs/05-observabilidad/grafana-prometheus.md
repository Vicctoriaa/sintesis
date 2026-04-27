# Grafana + Prometheus — CT101

> Stack de monitorización del laboratorio. Prometheus recolecta métricas de todos los contenedores y VMs mediante Node Exporter. Grafana proporciona la capa de visualización con dashboards preconfigurados. Todo corre en un único LXC en la VLAN 30 (SOC).

---

## Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 101 |
| Hostname | `Grafana-Prometheus` |
| OS | Debian 11 Bullseye |
| Memoria | 512 MB |
| Disco | 4 GB |
| Cores | 1 |
| Privilegiado | Sí |
| Features | `nesting=1`, `keyctl=1`, `lxc.apparmor.profile: unconfined` |
| Bridge | `vmbr1` — VLAN 30 SOC |
| IP | `10.1.1.66/27` |
| Gateway | `10.1.1.65` |

---

## Arquitectura

```
CT101 (VLAN 30 · 10.1.1.66)
   ├── Prometheus    :9090  (binario systemd)
   ├── Node Exporter :9100  (binario systemd)
   └── Grafana       :3000  (Docker)
         └── Datasource → Prometheus (http://10.1.1.66:9090)
```

---

## Prometheus

**Versión:** `2.45.0` — instalado como binario en `/opt/prometheus/`

### Servicio systemd — `/etc/systemd/system/prometheus.service`

```ini
[Unit]
Description=Prometheus
After=network.target

[Service]
Type=simple
ExecStart=/opt/prometheus/prometheus \
  --config.file=/opt/prometheus/prometheus.yml \
  --storage.tsdb.path=/opt/prometheus/data \
  --web.listen-address=0.0.0.0:9090 \
  --web.enable-lifecycle
Restart=always

[Install]
WantedBy=multi-user.target
```

> `--web.enable-lifecycle` permite recargar la configuración sin reiniciar: `POST http://localhost:9090/-/reload`

### Configuración — `/opt/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node_exporter'
    static_configs:
      - targets:
        - '10.1.1.66:9100'    # CT101 Grafana-Prometheus
        - '10.1.1.34:9100'    # CT103 DNS
        - '10.1.1.35:9100'    # CT105 Nginx
        - '10.1.1.36:9100'    # CT106 Suricata
        - '10.1.1.37:9100'    # CT104 SOAR
        - '10.1.1.98:9100'    # CT100 LDAP
        - '10.1.1.80:9100'    # CT102 Vaultwarden
        - '10.1.1.68:9100'    # CT107 Homepage
        - '10.1.1.67:9100'    # VM202 Wazuh
        - '10.1.1.130:9100'   # VM203 Honeypot
        - '10.1.1.69:9100'    # CT109 honeypot-dashboard

  - job_name: 'bind_exporter'
    static_configs:
      - targets:
        - '10.1.1.34:9119'    # CT103 Bind9

  - job_name: 'suricata_node'
    static_configs:
      - targets:
        - '10.1.1.36:9100'    # CT106 Suricata
```

### Targets activos

| Job | Target | CT/VM | Estado |
|-----|--------|-------|--------|
| prometheus | `localhost:9090` | CT101 | up |
| node_exporter | `10.1.1.66:9100` | CT101 Grafana-Prometheus | up |
| node_exporter | `10.1.1.34:9100` | CT103 DNS | up |
| node_exporter | `10.1.1.35:9100` | CT105 Nginx | up |
| node_exporter | `10.1.1.36:9100` | CT106 Suricata | up |
| node_exporter | `10.1.1.37:9100` | CT104 SOAR | up |
| node_exporter | `10.1.1.98:9100` | CT100 LDAP | up |
| node_exporter | `10.1.1.80:9100` | CT102 Vaultwarden | up |
| node_exporter | `10.1.1.68:9100` | CT107 Homepage | up |
| node_exporter | `10.1.1.67:9100` | VM202 Wazuh | up |
| node_exporter | `10.1.1.130:9100` | VM203 Honeypot | up |
| node_exporter | `10.1.1.69:9100` | CT109 honeypot-dashboard | up |
| bind_exporter | `10.1.1.34:9119` | CT103 Bind9 | up |
| suricata_exporter | `10.1.1.36:9917` | CT106 Suricata | up |

---

## Node Exporter

**Versión:** `v1.8.2` — instalado como binario en `/opt/node_exporter/`

### Servicio systemd — `/etc/systemd/system/node_exporter.service`

```ini
[Unit]
Description=Node Exporter
After=network.target

[Service]
Type=simple
ExecStart=/opt/node_exporter/node_exporter
Restart=always

[Install]
WantedBy=multi-user.target
```

> Node Exporter instalado en CT101, 103, 104, 105, 106, 107, 109, CT100, CT102, VM202 y VM203. Puerto: `9100`.

---

## Grafana

**Versión:** `12.4.1` — corriendo en Docker

### Docker Compose — `/root/grafana/docker-compose.yml`

```yaml
services:
  grafana:
    image: grafana/grafana-oss:12.4.1
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    volumes:
      - grafana-storage:/var/lib/grafana
      - ./provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=changeme
      - GF_USERS_ALLOW_SIGN_UP=false

volumes:
  grafana-storage:
```

### Dashboards importados

| Dashboard | UID | Descripción |
|-----------|-----|-------------|
| Node Exporter Full | `1860` | CPU, RAM, disco, red por host |
| Bind9 Exporter DNS | `bind9-exporter` | Queries DNS, NXDOMAIN, latencia |
| Suricata IDS — SOC honeycos | `suricata-soc-honeycos` | Alertas IDS, tráfico, flujos, memoria |
| Honeypot VM203 | `39dd04b1-3625-4526-b239-3bad5eb2c35a` | CPU/RAM/Disco/Red/TCP/Uptime honeypot |
