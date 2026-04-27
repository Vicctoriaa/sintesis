# Homepage Dashboard — CT107

> Dashboard de inicio autoalojado que centraliza el acceso a todos los servicios del SOC. Corre en Docker dentro de un LXC no privilegiado en la VLAN 30. El acceso externo se gestiona a través del proxy Nginx en CT105, que añade autenticación Basic Auth.

---

## Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 107 |
| Hostname | `homepage` |
| OS | Debian 12 Bookworm |
| Memoria | 512 MB |
| Swap | 512 MB |
| Disco | 4 GB |
| Cores | 1 |
| Privilegiado | No |
| Features | `nesting=1` (necesario para Docker) |
| onboot | 1 |
| Bridge | `vmbr1` — VLAN 30 SOC |
| IP | `10.1.1.68/27` |
| Gateway | `10.1.1.65` |

---

## Docker

### Instalación

```bash
apt update && apt install -y curl
curl -fsSL https://get.docker.com | sh
```

| Componente | Versión |
|-----------|---------|
| Docker Engine | 29.4.0 |
| API version | 1.54 |
| containerd | v2.2.2 |

### Docker Compose — `/opt/homepage/docker-compose.yml`

```yaml
services:
  homepage:
    image: ghcr.io/gethomepage/homepage:latest
    container_name: homepage
    ports:
      - "3001:3000"
    environment:
      HOMEPAGE_ALLOWED_HOSTS: "*"
    volumes:
      - /opt/homepage/config:/app/config
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped
```

> Puerto interno: `3001`. El socket Docker se monta en solo lectura para que Homepage consulte el estado de los contenedores en tiempo real. La autenticación se gestiona en Nginx CT105, no en Homepage.

### Comandos Docker

```bash
cd /opt/homepage

docker compose up -d       # Arrancar
docker compose down        # Parar
docker compose restart     # Reiniciar
docker logs homepage       # Ver logs
docker compose pull && docker compose up -d  # Actualizar imagen
```

---

## Configuración

Los ficheros de configuración están en `/opt/homepage/config/` y se recargan automáticamente al detectar cambios — no es necesario reiniciar el contenedor.

### `settings.yaml`

```yaml
title: SOC Dashboard
theme: dark
color: slate
headerStyle: clean
layout:
  Infraestructura:
    columns: 1
  SOC:
    columns: 3
  Servicios:
    columns: 1
```

### `services.yaml`

```yaml
- Infraestructura:
    - Proxmox:
        href: https://192.168.3.200:8006
        description: Hypervisor Proxmox VE
        icon: proxmox.png

- SOC:
    - Wazuh:
        href: https://192.168.3.200:443
        description: SIEM
        icon: wazuh.png
    - Grafana:
        href: http://192.168.3.200:3000
        description: Dashboards y métricas
        icon: grafana.png
    - Honeypot Dashboard:
        href: http://192.168.3.200:8765
        description: Dashboard honeypot
        icon: https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/cowrie.png

- Servicios:
    - SOAR:
        href: http://192.168.3.200:8080
        description: Plataforma SOAR
        icon: shield.png
    - Vaultwarden:
        href: http://192.168.3.200:8091
        description: Gestor de contraseñas
        icon: vaultwarden.png
```

> `bookmarks.yaml` y `widgets.yaml` pendientes de configurar.

---

## Autenticación

Homepage no tiene sistema de login propio. El acceso se protege mediante HTTP Basic Auth en Nginx CT105.

| Parámetro | Valor |
|-----------|-------|
| Fichero htpasswd | `/etc/nginx/.htpasswd` (en CT105) |
| Usuario | `admin` |
| Regenerar credencial | `htpasswd /etc/nginx/.htpasswd admin` |

---

## Acceso

| Desde | URL |
|-------|-----|
| Red local | `http://192.168.3.200:8888` |
| Interno VLAN | `http://10.1.1.35:8888` (via Nginx CT105) |

```
Cliente (192.168.3.x)
   ↓ http://192.168.3.200:8888
Proxmox PREROUTING (:8888 → 10.1.1.35:8888)
   ↓
CT105 Nginx :8888 — Basic Auth
   ↓ proxy_pass
CT107 Homepage (10.1.1.68:3001)
```

---

## Monitorización

| Servicio | Puerto | Estado |
|---------|--------|--------|
| node_exporter | `9100` | active |

Target en Prometheus CT101:
```yaml
- '10.1.1.68:9100'    # CT107 Homepage
```

---

## Comandos útiles

```bash
# Estado del contenedor
docker ps

# Logs en tiempo real
docker logs -f homepage

# Verificar que responde
curl -I http://localhost:3001

# Editar servicios (recarga automática)
nano /opt/homepage/config/services.yaml
```

---

## Resumen

```
CT107 Homepage (VLAN 30 · 10.1.1.68)
   └── Docker :3001 → Homepage dashboard
         └── Acceso via CT105 Nginx :8888 (Basic Auth)
```
