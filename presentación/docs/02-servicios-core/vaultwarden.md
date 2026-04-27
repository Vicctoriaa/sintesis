# Vaultwarden — CT102

> Implementación alternativa del servidor Bitwarden escrita en Rust, ligera y autoalojada. Proporciona gestión centralizada de credenciales para el laboratorio SOC. Corre en Docker dentro de un LXC privilegiado, expuesto a través del proxy Nginx en CT105.

---

## Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 102 |
| Hostname | `Gestor-Vaultwarden` |
| OS | Debian 12 |
| Memoria | 256 MB |
| Disco | 10 GB |
| Cores | 1 |
| Privilegiado | Sí |
| Features | `nesting=1` |
| Bridge | `vmbr1` — VLAN 30 SOC |
| IP | `10.1.1.80/27` |
| Gateway | `10.1.1.65` |

> El contenedor debe ser **privilegiado** y tener `nesting=1` para que Docker funcione correctamente dentro del LXC.

---

## Preparación del contenedor

### Activar nesting en el host Proxmox

```bash
pct set 102 -features nesting=1

# Verificar
cat /etc/pve/lxc/102.conf | grep features
# features: nesting=1
```

### Instalar Docker

```bash
apt update && apt upgrade -y
apt install docker.io docker-compose -y
systemctl enable docker
systemctl start docker
```

---

## Docker Compose — `/opt/vaultwarden/docker-compose.yml`

```yaml
version: "3"
services:
  vaultwarden:
    image: vaultwarden/server:latest
    container_name: vaultwarden
    restart: always
    environment:
      - ADMIN_TOKEN=xxx
      - SIGNUPS_ALLOWED=false
      - DOMAIN=https://192.168.3.200:8443
    volumes:
      - ./data:/data
    ports:
      - "8090:80"
```

> Cambiar `ADMIN_TOKEN` por un token seguro antes de desplegar en producción.

```bash
mkdir /opt/vaultwarden && cd /opt/vaultwarden
# Crear docker-compose.yml con el contenido anterior
docker compose up -d
```

---

## Acceso

| URL | Descripción |
|-----|-------------|
| `http://192.168.3.200:8091` | Acceso HTTP (via Nginx CT105) |
| `https://192.168.3.200:8443` | Acceso HTTPS con TLS (via Nginx CT105) |
| `http://10.1.1.80:8090` | Acceso interno directo |

La configuración Nginx que expone Vaultwarden está documentada en [`nginx.md`](nginx.md).

---

## Monitorización

| Servicio | Puerto | Estado |
|---------|--------|--------|
| node_exporter | `9100` | active |

Target en Prometheus CT101:
```yaml
- '10.1.1.80:9100'    # CT102 Vaultwarden
```

---

## Comandos útiles

```bash
cd /opt/vaultwarden

# Estado
docker compose ps

# Logs
docker logs vaultwarden

# Reiniciar
docker compose restart

# Actualizar imagen
docker compose pull && docker compose up -d
```
