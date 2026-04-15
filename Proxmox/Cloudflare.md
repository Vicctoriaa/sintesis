☁️ Cloudflare Tunnel con cloudflared (Guía completa)

Guía paso a paso para instalar y configurar un túnel de Cloudflare en un LXC con Debian/Ubuntu.

☁️ 1. Instalar Cloudflared en el LXC
🔧 En Debian/Ubuntu:
sudo apt update
sudo apt install -y curl gnupg lsb-release
📦 Añadir repositorio de Cloudflare:
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg

echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
⚙️ Instalar paquete:
sudo apt update
sudo apt install cloudflared
🔐 2. Login en Cloudflare

Ejecuta:

cloudflared tunnel login
Pasos:
Se generará una URL
Ábrela en tu navegador
Inicia sesión
Selecciona tu dominio
🚇 3. Crear el túnel
cloudflared tunnel create mi-tunel

Esto generará:

🆔 Un Tunnel ID
📁 Un archivo de credenciales en:
/etc/cloudflared/<TUNNEL-ID>.json
⚙️ 4. Configurar el túnel
📄 Crear archivo de configuración:
sudo nano /etc/cloudflared/config.yml
🧩 Ejemplo de configuración:
tunnel: mi-tunel
credentials-file: /etc/cloudflared/TUNNEL_ID.json

ingress:
  - hostname: tu-dominio.com
    service: http://localhost:80

  - hostname: www.tu-dominio.com
    service: http://localhost:80

  - service: http_status:404

👉 Este túnel redirige el tráfico hacia Nginx en localhost:80.

🌐 5. Crear DNS en Cloudflare
cloudflared tunnel route dns mi-tunel tu-dominio.com
cloudflared tunnel route dns mi-tunel www.tu-dominio.com
🚀 6. Ejecutar el túnel
🧪 Prueba manual:
cloudflared tunnel run mi-tunel

Si todo está correcto, tu web ya estará accesible vía Cloudflare.

🔄 7. Ejecutarlo como servicio (IMPORTANTE)
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
