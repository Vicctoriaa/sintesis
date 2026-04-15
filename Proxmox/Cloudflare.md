## 📌 Índice

- [1. Instalación de Cloudflared](#1--instalación-de-cloudflared)
- [2. Login en Cloudflare](#2--login-en-cloudflare)
- [3. Creación del túnel](#3--creación-del-túnel)
- [4. Configuración del túnel](#4--configuración-del-túnel)
- [5. Configuración DNS](#5--configuración-dns)
- [6. Ejecución del túnel](#6--ejecución-del-túnel)
- [7. Servicio automático](#7--servicio-automático)

---

# 1️⃣ Instalación de Cloudflared

### 🧱 Requisitos previos

```bash
sudo apt update
sudo apt install -y curl gnupg lsb-release
📦 Añadir repositorio oficial de Cloudflare
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg

echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
| sudo tee /etc/apt/sources.list.d/cloudflared.list
⚙️ Instalar cloudflared
sudo apt update
sudo apt install -y cloudflared
2️⃣ Login en Cloudflare

Ejecuta el siguiente comando:

cloudflared tunnel login
🌐 Proceso:
Se generará una URL de autenticación
Ábrela en el navegador
Inicia sesión en Cloudflare
Selecciona tu dominio
3️⃣ Creación del túnel
cloudflared tunnel create mi-tunel
📌 Resultado:
🆔 Se genera un Tunnel ID
📁 Archivo de credenciales:
/etc/cloudflared/<TUNNEL-ID>.json
4️⃣ Configuración del túnel
📄 Crear archivo de configuración
sudo nano /etc/cloudflared/config.yml
⚙️ Ejemplo de configuración
tunnel: mi-tunel
credentials-file: /etc/cloudflared/TUNNEL_ID.json

ingress:
  - hostname: tu-dominio.com
    service: http://localhost:80

  - hostname: www.tu-dominio.com
    service: http://localhost:80

  - service: http_status:404
🔁 Flujo

🌍 Cloudflare → ☁️ Tunnel → 🖥️ Nginx (localhost:80)

5️⃣ Configuración DNS en Cloudflare
cloudflared tunnel route dns mi-tunel tu-dominio.com
cloudflared tunnel route dns mi-tunel www.tu-dominio.com
6️⃣ Ejecución del túnel
🧪 Modo prueba
cloudflared tunnel run mi-tunel
✅ Resultado esperado
Tu web queda accesible desde Internet
Sin abrir puertos en el router
Sin exponer IP pública
7️⃣ Ejecutarlo como servicio (RECOMENDADO)
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
🔄 Gestión del servicio
# Estado
systemctl status cloudflared

# Reiniciar
systemctl restart cloudflared

# Logs
journalctl -u cloudflared -f
🚀 Resultado final

✔ Servidor local expuesto de forma segura
✔ Sin abrir puertos
✔ Protección de Cloudflare (DDoS + proxy)
✔ Dominio conectado al túnel

🧠 Nota técnica

Este método es ideal para:

🖥️ Servidores caseros (home lab)
🧪 Entornos de desarrollo
🌐 VPS sin IP pública fija
🔐 Exposición segura de servicios internos

---

Si quieres puedo llevarlo aún más lejos con:

- 🔥 portada tipo “GitHub repo profesional” con banner
- 🧭 diagrama visual del flujo Cloudflare → Tunnel → Nginx
- 🧩 versión en inglés tipo portfolio técnico
- 📦 badge de estado + versión + licencia estilo open source

Solo dime.
