# ☁️ Cloudflare Tunnel con `cloudflared`

> 🔐 Conecta tu servidor local (LXC / VPS / Debian / Ubuntu) a Internet de forma segura sin abrir puertos, usando Cloudflare Tunnel.

---

## 📌 Índice

1. [Instalación de Cloudflared](#1️⃣-instalación-de-cloudflared)
2. [Login en Cloudflare](#2️⃣-login-en-cloudflare)
3. [Creación del túnel](#3️⃣-creación-del-túnel)
4. [Configuración del túnel](#4️⃣-configuración-del-túnel)
5. [Configuración DNS](#5️⃣-configuración-dns-en-cloudflare)
6. [Ejecución del túnel](#6️⃣-ejecución-del-túnel)
7. [Servicio automático](#7️⃣-ejecutarlo-como-servicio-recomendado)

---

## 1️⃣ Instalación de Cloudflared

### 🧱 Requisitos previos

```bash
sudo apt update
sudo apt install -y curl gnupg lsb-release
```

### 📦 Añadir repositorio oficial de Cloudflare

```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg

echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
| sudo tee /etc/apt/sources.list.d/cloudflared.list
```

### ⚙️ Instalar cloudflared

```bash
sudo apt update
sudo apt install -y cloudflared
```

---

## 2️⃣ Login en Cloudflare

```bash
cloudflared tunnel login
```

### 🌐 Proceso

| Paso | Descripción |
|------|-------------|
| 1 | Se genera una URL de autenticación |
| 2 | Ábrela en el navegador |
| 3 | Inicia sesión en Cloudflare |
| 4 | Selecciona tu dominio |

---

## 3️⃣ Creación del túnel

```bash
cloudflared tunnel create mi-tunel
```

### 📌 Resultado

- 🆔 Se genera un **Tunnel ID**
- 📁 Archivo de credenciales en: `/etc/cloudflared/<TUNNEL-ID>.json`

---

## 4️⃣ Configuración del túnel

### 📄 Crear archivo de configuración

```bash
sudo nano /etc/cloudflared/config.yml
```

### ⚙️ Ejemplo de configuración

```yaml
tunnel: mi-tunel
credentials-file: /etc/cloudflared/TUNNEL_ID.json

ingress:
  - hostname: tu-dominio.com
    service: http://localhost:80

  - hostname: www.tu-dominio.com
    service: http://localhost:80

  - service: http_status:404
```

### 🔁 Flujo

```
🌍 Cloudflare → ☁️ Tunnel → 🖥️ Nginx (localhost:80)
```

---

## 5️⃣ Configuración DNS en Cloudflare

```bash
cloudflared tunnel route dns mi-tunel tu-dominio.com
cloudflared tunnel route dns mi-tunel www.tu-dominio.com
```

---

## 6️⃣ Ejecución del túnel

### 🧪 Modo prueba

```bash
cloudflared tunnel run mi-tunel
```

### ✅ Resultado esperado

- Tu web queda accesible desde Internet
- Sin abrir puertos en el router
- Sin exponer IP pública

---

## 7️⃣ Ejecutarlo como servicio (RECOMENDADO)

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### 🔄 Gestión del servicio

```bash
# Estado
systemctl status cloudflared

# Reiniciar
systemctl restart cloudflared

# Logs
journalctl -u cloudflared -f
```

---

> 💡 **Tip:** Puedes usar `cloudflared tunnel list` para ver todos tus túneles activos y `cloudflared tunnel delete mi-tunel` para eliminar uno.
