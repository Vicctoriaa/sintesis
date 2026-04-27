# Nginx Reverse Proxy — CT105

> Punto de entrada único para todos los servicios web del laboratorio. Centraliza el acceso, añade autenticación y simplifica las reglas de firewall. Todo el tráfico externo pasa por este contenedor antes de llegar a su destino.

---

## Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 105 |
| Hostname | `nginx-proxy` |
| OS | Debian 12 |
| Memoria | 256 MB |
| Disco | 4 GB |
| Cores | 1 |
| Privilegiado | No |
| Bridge | `vmbr1` — VLAN 20 Servicios |
| IP | `10.1.1.35/27` |
| Gateway | `10.1.1.33` |

---

## Servicios proxificados

| Servicio | Destino interno | Puerto externo | Auth |
|----------|----------------|----------------|------|
| Grafana | `10.1.1.66:3000` | `:3000` | No |
| SOAR | `10.1.1.37:8080` | `:8080` | No |
| Vaultwarden | `10.1.1.80:8090` | `:8091` | No |
| Vaultwarden SSL | `10.1.1.80:8090` | `:8443` | No (cert autofirmado) |
| Homepage | `10.1.1.68:3001` | `:8888` | Basic Auth |
| Honeypot Dashboard | `10.1.1.69:80` | `:8765` | Basic Auth |
| Web | — | `:80` | — (503 reservado) |
| Wazuh | `10.1.1.67:443` | `:443` | Propio (acceso directo, sin Nginx) |

---

## Virtual hosts

### Grafana — `:3000`

```nginx
server {
    listen 3000;
    server_name _;

    location / {
        proxy_pass http://10.1.1.66:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSockets — necesario para Grafana Live
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### SOAR — `:8080`

```nginx
server {
    listen 8080;
    server_name _;

    location / {
        proxy_pass http://10.1.1.37:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Vaultwarden — `:8091`

> El WebSocket es obligatorio para que Vaultwarden sincronice el estado en tiempo real. El puerto interno de Docker es `8090`; el externo es `8091` para evitar conflicto con SOAR.

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

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Vaultwarden SSL — `:8443`

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

### Homepage — `:8888` (Basic Auth)

```nginx
server {
    listen 8888;
    server_name _;

    auth_basic "SOC Dashboard";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://10.1.1.68:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Honeypot Dashboard — `:8765` (Basic Auth)

```nginx
server {
    listen 8765;
    server_name _;

    auth_basic "SOC honeycos — Dashboard Honeypot";
    auth_basic_user_file /etc/nginx/.htpasswd-dashboard;

    location / {
        proxy_pass http://10.1.1.69:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Web — `:80` (reservado)

```nginx
server {
    listen 80 default_server;
    server_name _;

    location / {
        return 503 "Próximamente";
    }
}
```

---

## Flujo de acceso

```
Cliente (192.168.3.x)
   ↓ :3000   → Proxmox NAT → CT105 Nginx → CT101 Grafana       (10.1.1.66:3000)
   ↓ :8080   → Proxmox NAT → CT105 Nginx → CT104 SOAR          (10.1.1.37:8080)
   ↓ :8091   → Proxmox NAT → CT105 Nginx → CT102 Vaultwarden   (10.1.1.80:8090)
   ↓ :8443   → Proxmox NAT → CT105 Nginx → CT102 Vaultwarden   (10.1.1.80:8090) SSL
   ↓ :8888   → Proxmox NAT → CT105 Nginx → CT107 Homepage      (10.1.1.68:3001) Basic Auth
   ↓ :8765   → Proxmox NAT → CT105 Nginx → CT109 Honeypot Dash (10.1.1.69:80)   Basic Auth
   ↓ :443    → Proxmox NAT → VM202 Wazuh (directo, sin Nginx)  (10.1.1.67:443)
```
