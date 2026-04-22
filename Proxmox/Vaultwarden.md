# Vaultwarden en LXC Proxmox con Nginx

## 1. Crear el contenedor LXC en Proxmox

> Vaultwarden es una implementación alternativa del servidor de Bitwarden escrita en Rust, ligera y autoalojada. El primer paso es crear un contenedor LXC en Proxmox, que actuará como entorno aislado donde correrá Docker y, dentro de él, Vaultwarden. Se recomienda Debian 12 por su estabilidad y compatibilidad con Docker. El contenedor debe ser **privilegiado** para que Docker pueda funcionar correctamente dentro del LXC.

**Config recomendada:**
| Parámetro | Valor |
|-----------|-------|
| Template | Debian 12 (recomendado) |
| Privileged | IMPORTANTE |
| RAM | 512MB mínimo (mejor 1GB) |
| CPU | 1 core suficiente |
| Disco | 5–10GB |

---

## 2. Activar nesting (CLAVE)

> El **nesting** (anidamiento) permite que dentro del contenedor LXC se puedan ejecutar contenedores Docker. Sin esta opción activada, Docker no podrá arrancar dentro del LXC, ya que necesita acceso a ciertas funcionalidades del kernel que el nesting habilita. Este paso se realiza desde el **host Proxmox**, no desde dentro del contenedor.

En el host Proxmox:
```bash
pct set  -features nesting=1
```
Comprueba el config:
```bash
cat /etc/pve/lxc/.conf
```
Debe tener:
features: nesting=1

---

## 3. Instalar Docker dentro del LXC

> Una vez configurado el contenedor, entramos en él y procedemos a instalar Docker. Docker es el motor de contenedores que se usará para ejecutar Vaultwarden de forma aislada y reproducible. `docker-compose` permite definir y gestionar los servicios Docker mediante un archivo YAML. Habilitamos Docker como servicio del sistema para que arranque automáticamente al iniciar el contenedor.

Entra al contenedor:
```bash
pct enter <ID>
```
Instala Docker:
```bash
apt update && apt upgrade -y
apt install docker.io docker-compose -y
```
Arranca Docker:
```bash
systemctl enable docker
systemctl start docker
```

---

## 4. Crear Vaultwarden con docker-compose

> `docker-compose` nos permite definir la configuración completa de Vaultwarden en un único archivo. Aquí se especifica la imagen a usar, las variables de entorno (como el token de administración y si se permiten registros), los volúmenes donde se persistirán los datos y los puertos expuestos. El puerto `8090` del host mapeará al puerto `80` del contenedor Docker donde escucha Vaultwarden.

Crea carpeta:
```bash
mkdir /opt/vaultwarden && cd /opt/vaultwarden
```
Crea `docker-compose.yml`:
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
> **Nota:** Cambia `ADMIN_TOKEN` por un token seguro generado por ti antes de desplegar en producción.

---

## 5. Configuración Nginx (proxy inverso)

> Nginx actúa como **proxy inverso**: recibe las peticiones del cliente y las reenvía internamente hacia Vaultwarden. Esto permite exponer Vaultwarden bajo puertos estándar, añadir SSL/TLS y gestionar cabeceras HTTP necesarias para su correcto funcionamiento. Las cabeceras `Upgrade` y `Connection` son imprescindibles para que los **WebSockets** funcionen, ya que Vaultwarden los usa para sincronización en tiempo real.

### HTTP (puerto 8091)

> Esta configuración sirve Vaultwarden sin cifrado, útil para pruebas en red local. Redirige el tráfico del puerto `8091` de Nginx hacia el puerto `8090` donde escucha Vaultwarden.

```nginx
server {
    listen 8091;
    server_name _;
    location / {
        proxy_pass http://10.1.1.80:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # MUY IMPORTANTE (Vaultwarden)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### HTTPS / SSL (puerto 8443)

> Esta configuración añade cifrado TLS al tráfico. Los clientes se conectan por el puerto `8443` usando HTTPS, y Nginx descifra la conexión antes de reenviar el tráfico internamente a Vaultwarden por HTTP. Se necesitan un certificado (`vaultwarden.crt`) y su clave privada (`vaultwarden.key`), que pueden ser autofirmados para uso en red local.

```nginx
server {
    listen 8443 ssl;
    server_name _;
    ssl_certificate /etc/nginx/certs/vaultwarden.crt;
    ssl_certificate_key /etc/nginx/certs/vaultwarden.key;
    location / {
        proxy_pass http://10.1.1.80:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 6. Activar configuración

> Una vez creado el archivo de configuración de Nginx, hay que habilitarlo creando un enlace simbólico desde `sites-available` a `sites-enabled`. Después se verifica que la sintaxis del archivo sea correcta con `nginx -t` y se recarga Nginx para aplicar los cambios sin interrumpir el servicio.

```bash
ln -s /etc/nginx/sites-available/vaultwarden /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

---

## 7. Router

> El último paso es abrir el puerto correspondiente en el router doméstico o de red para que Vaultwarden sea accesible desde fuera de la red local. Se hace una regla de **port forwarding** que redirija el tráfico del puerto externo `8443` hacia la IP interna del servidor donde corre Nginx.

Abre el siguiente puerto hacia la IP del contenedor Nginx:
| Puerto externo | Destino |
|----------------|---------|
| `8443` | https://192.168.3.200 |
