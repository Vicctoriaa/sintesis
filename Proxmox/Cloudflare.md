# Cloudflare Tunnel con `cloudflared`
> Conecta tu servidor local (LXC / VPS / Debian / Ubuntu) a Internet de forma segura sin abrir puertos, usando Cloudflare Tunnel.

Cloudflare Tunnel crea una conexión saliente cifrada entre tu servidor y la red de Cloudflare, eliminando la necesidad de exponer puertos o tu IP pública. El tráfico entra por Cloudflare y llega a tu servicio local a través del agente `cloudflared`.

---

## Índice
1. [Instalación de Cloudflared](#1️⃣-instalación-de-cloudflared)
2. [Login en Cloudflare](#2️⃣-login-en-cloudflare)
3. [Creación del túnel](#3️⃣-creación-del-túnel)
4. [Configuración del túnel](#4️⃣-configuración-del-túnel)
5. [Configuración DNS](#5️⃣-configuración-dns-en-cloudflare)
6. [Ejecución del túnel](#6️⃣-ejecución-del-túnel)
7. [Servicio automático](#7️⃣-ejecutarlo-como-servicio-recomendado)

---

## 1️. Instalación de Cloudflared

`cloudflared` es el agente que se ejecuta en tu servidor y mantiene la conexión con Cloudflare. Se instala desde el repositorio oficial para garantizar que siempre recibas actualizaciones de seguridad.

### Requisitos previos

Herramientas necesarias para añadir repositorios externos de forma segura: `curl` descarga la clave GPG y `lsb-release` detecta la versión del sistema operativo.

```bash
sudo apt update
sudo apt install -y curl gnupg lsb-release
```

### Añadir repositorio oficial de Cloudflare

Añade la clave GPG de Cloudflare para verificar la autenticidad de los paquetes, y registra el repositorio oficial en APT. El uso de `lsb_release -cs` asegura que se usa el repositorio correcto para tu versión de Debian/Ubuntu.

```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
| sudo tee /etc/apt/sources.list.d/cloudflared.list
```

### Instalar cloudflared

Una vez registrado el repositorio, se instala el agente `cloudflared` como cualquier otro paquete del sistema.

```bash
sudo apt update
sudo apt install -y cloudflared
```

---

## 2️. Login en Cloudflare

Autentica tu servidor con tu cuenta de Cloudflare. Este paso vincula el agente local con tu cuenta y dominio, generando un certificado de autorización que se almacena en el sistema.

```bash
cloudflared tunnel login
```

### Proceso

| Paso | Descripción |
|------|-------------|
| 1 | Se genera una URL de autenticación |
| 2 | Ábrela en el navegador |
| 3 | Inicia sesión en Cloudflare |
| 4 | Selecciona tu dominio |

---

## 3️. Creación del túnel

Crea un túnel con nombre personalizado. Cloudflare genera un identificador único (Tunnel ID) y un archivo de credenciales que el agente usará para autenticarse en cada conexión.

```bash
cloudflared tunnel create mi-tunel
```

### Resultado

- Se genera un **Tunnel ID**
- Archivo de credenciales en: `/etc/cloudflared/<TUNNEL-ID>.json`

---

## 4️. Configuración del túnel

El archivo `config.yml` define el comportamiento del túnel: qué credenciales usar, qué dominios escuchar y a qué servicio local redirigir cada petición. La regla final `http_status:404` actúa como catch-all para peticiones no definidas.

### Crear archivo de configuración

```bash
sudo nano /etc/cloudflared/config.yml
```

### Ejemplo de configuración

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

### Flujo

```
🌍 Cloudflare → ☁️ Tunnel → 🖥️ Nginx (localhost:80)
```

---

## 5️. Configuración DNS en Cloudflare

Crea automáticamente registros CNAME en tu zona DNS de Cloudflare apuntando al túnel. Esto evita tener que hacerlo manualmente desde el panel web y garantiza que el dominio resuelva correctamente a través del túnel.

```bash
cloudflared tunnel route dns mi-tunel tu-dominio.com
cloudflared tunnel route dns mi-tunel www.tu-dominio.com
```

---

## 6️. Ejecución del túnel

### Modo prueba

Lanza el túnel en primer plano para verificar que la configuración es correcta antes de dejarlo como servicio permanente. Útil para depurar errores de ingress o credenciales.

```bash
cloudflared tunnel run mi-tunel
```

### Resultado esperado

- Tu web queda accesible desde Internet
- Sin abrir puertos en el router
- Sin exponer IP pública

---

## 7️. Ejecutarlo como servicio (RECOMENDADO)

Registra `cloudflared` como servicio de systemd para que arranque automáticamente con el sistema y se reinicie ante fallos. Es el modo de uso recomendado en producción.

```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

### Gestión del servicio

Comandos habituales para operar el servicio una vez instalado.

```bash
# Estado
systemctl status cloudflared
# Reiniciar
systemctl restart cloudflared
# Logs
journalctl -u cloudflared -f
```

---

> **Tip:** Puedes usar `cloudflared tunnel list` para ver todos tus túneles activos y `cloudflared tunnel delete mi-tunel` para eliminar uno.
