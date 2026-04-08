# CT 107 — Homepage Dashboard

## Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 107 |
| Hostname | homepage |
| OS | Debian 12 (Bookworm) |
| Memoria | 512 MB |
| Swap | 512 MB |
| Disco | 4 GB (local-zfs) |
| Cores | 1 |
| Privilegiado | No |
| Features | nesting=1 (necesario para Docker) |
| onboot | 1 |

## Red

| Campo | Valor |
|-------|-------|
| Bridge | vmbr1 |
| VLAN | 30 — SOC |
| IP | 10.1.1.68/27 |
| Gateway | 10.1.1.65 |

---

## Creación del contenedor

```bash
pct create 107 local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst \
  --hostname homepage \
  --cores 1 \
  --memory 512 \
  --swap 512 \
  --rootfs local-zfs:4 \
  --net0 name=eth0,bridge=vmbr1,tag=30,ip=10.1.1.68/27,gw=10.1.1.65 \
  --unprivileged 1 \
  --features nesting=1 \
  --onboot 1 \
  --start 1
```

---

## Docker

### Instalación

```bash
apt update && apt install -y curl
curl -fsSL https://get.docker.com | sh
```

### Versión instalada

| Componente | Versión |
|-----------|---------|
| Docker Engine | 29.4.0 |
| API version | 1.54 |
| containerd | v2.2.2 |

---

## Homepage

### Docker Compose

**Fichero:** `/opt/homepage/docker-compose.yml`

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

> Puerto interno: **3001**. La autenticación se gestiona en Nginx CT105, no en Homepage.  
> `HOMEPAGE_ALLOWED_HOSTS: "*"` — Homepage no tiene autenticación nativa, el login se delega a Nginx Basic Auth.

### Comandos Docker

```bash
cd /opt/homepage

# Arrancar
docker compose up -d

# Parar
docker compose down

# Ver logs
docker logs homepage

# Reiniciar
docker compose restart

# Actualizar imagen
docker compose pull && docker compose up -d
```

---

## Configuración

Los ficheros de configuración están en `/opt/homepage/config/`.

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

### `bookmarks.yaml` y `widgets.yaml`

Pendientes de configurar.

---

## Autenticación

Homepage no tiene autenticación nativa. El login se gestiona mediante **HTTP Basic Auth en Nginx CT105**.

| Parámetro | Valor |
|-----------|-------|
| Fichero htpasswd | `/etc/nginx/.htpasswd` (en CT105) |
| Usuario | `admin` |
| Gestión | `htpasswd /etc/nginx/.htpasswd admin` |

---

## Acceso

| Desde | URL |
|-------|-----|
| Red local | `http://192.168.3.200:8888` |
| Interno VLAN | `http://10.1.1.35:8888` (via Nginx CT105) |

El flujo completo:
```
Cliente (192.168.3.x)
   ↓ http://192.168.3.200:8888
Proxmox PREROUTING (:8888 → 10.1.1.35:8888) + MASQUERADE
   ↓
CT105 Nginx :8888 — Basic Auth
   ↓ proxy_pass
CT107 Homepage (10.1.1.68:3001)
```

---

## Monitorización

| Servicio | Puerto | Estado |
|---------|--------|--------|
| node_exporter | 9100 | active |

Target añadido en Prometheus CT101:
```yaml
- '10.1.1.68:9100'    # CT107 Homepage
```

---

## Comandos útiles

```bash
# Ver estado del contenedor Docker
docker ps

# Ver logs en tiempo real
docker logs -f homepage

# Verificar que Homepage responde
curl -I http://localhost:3001

# Editar servicios
nano /opt/homepage/config/services.yaml

# Los cambios en config se aplican automáticamente sin reiniciar
```

---

## Resumen

```
CT 107 — Homepage (VLAN 30 · 10.1.1.68)
   └── Docker :3001 → Homepage dashboard
         └── Acceso via CT105 Nginx :8888 (Basic Auth)
```
