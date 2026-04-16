# Vaultwarden en LXC Proxmox con Nginx

## 1. Crear el contenedor LXC en Proxmox

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

### HTTP (puerto 8091)

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

```bash
ln -s /etc/nginx/sites-available/vaultwarden /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

---

## 7. Router

Abre el siguiente puerto hacia la IP del contenedor Nginx:

| Puerto externo | Destino |
|----------------|---------|
| `8443` | https://192.168.3.200 |
