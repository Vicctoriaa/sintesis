# CT 107 — Homepage Dashboard

## Datos del contenedor

> Homepage es un dashboard de inicio autoalojado que centraliza el acceso a todos los servicios del SOC. Corre dentro de un contenedor LXC no privilegiado en Proxmox con Docker habilitado mediante `nesting=1`. Los recursos asignados son mínimos dado que el servicio es ligero.

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

> El contenedor está en la VLAN 30 del segmento SOC, junto al resto de servicios internos. No tiene IP pública directa; el acceso externo se gestiona a través del proxy Nginx en CT105.

| Campo | Valor |
|-------|-------|
| Bridge | vmbr1 |
| VLAN | 30 — SOC |
| IP | 10.1.1.68/27 |
| Gateway | 10.1.1.65 |

---

## Creación del contenedor

> Este comando crea y arranca el contenedor directamente con toda la configuración de red, recursos y opciones necesarias. El flag `--unprivileged 1` junto con `--features nesting=1` permite correr Docker dentro sin necesidad de privilegios completos.

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

> Se usa el script oficial de Docker para obtener la versión más reciente directamente desde los repositorios de Docker Inc., en lugar del paquete `docker.io` de Debian que suele estar desactualizado.

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

> El contenedor expone Homepage en el puerto `3001` del host (el `3000` interno es el puerto por defecto de la aplicación). Se monta el socket de Docker en modo solo lectura para que Homepage pueda consultar el estado de los contenedores en tiempo real. La autenticación no se configura aquí sino en Nginx.

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

> Todos los comandos se ejecutan desde `/opt/homepage` donde está el `docker-compose.yml`. Los cambios en los ficheros de configuración (`/opt/homepage/config/`) se aplican automáticamente sin necesidad de reiniciar el contenedor.

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

> Todos los ficheros de configuración de Homepage son YAML y se encuentran en `/opt/homepage/config/`. Homepage los monitoriza y recarga automáticamente al detectar cambios, por lo que no es necesario reiniciar el servicio tras editarlos.

Los ficheros de configuración están en `/opt/homepage/config/`.

### `settings.yaml`

> Define la apariencia global del dashboard: tema, colores y la distribución de las secciones en columnas. El layout controla cuántos servicios se muestran en fila por cada grupo.

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

> Define los servicios que aparecen en el dashboard, agrupados por categoría. Cada entrada incluye la URL de acceso, una descripción y un icono. Los iconos se resuelven automáticamente desde el repositorio de iconos de Homepage si coinciden con nombres conocidos.

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

> Homepage carece de sistema de login propio. Para proteger el acceso se delega la autenticación al proxy Nginx del CT105, que solicita usuario y contraseña mediante HTTP Basic Auth antes de reenviar la petición a Homepage. El fichero `htpasswd` almacena las credenciales en formato hash.

Homepage no tiene autenticación nativa. El login se gestiona mediante **HTTP Basic Auth en Nginx CT105**.

| Parámetro | Valor |
|-----------|-------|
| Fichero htpasswd | `/etc/nginx/.htpasswd` (en CT105) |
| Usuario | `admin` |
| Gestión | `htpasswd /etc/nginx/.htpasswd admin` |

---

## Acceso

> El tráfico pasa por dos saltos antes de llegar a Homepage: primero la regla de PREROUTING de Proxmox redirige el puerto hacia Nginx en CT105, y Nginx aplica la autenticación y hace el proxy_pass final a Homepage. El cliente nunca conecta directamente con CT107.

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

> El `node_exporter` expone métricas del sistema (CPU, memoria, disco, red) en el puerto `9100`. Prometheus en CT101 recoge estas métricas periódicamente y las almacena para su visualización en Grafana CT101.

| Servicio | Puerto | Estado |
|---------|--------|--------|
| node_exporter | 9100 | active |

Target añadido en Prometheus CT101:
```yaml
- '10.1.1.68:9100'    # CT107 Homepage
```

---

## Comandos útiles

> Comandos de uso frecuente para verificar el estado del servicio y editar la configuración en caliente. El `curl` local es útil para comprobar que Homepage responde antes de descartar problemas en Nginx o en el routing.

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
