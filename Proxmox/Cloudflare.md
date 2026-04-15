☁️ 1. Instalar Cloudflared en el LXC
En Debian/Ubuntu:
sudo apt update
sudo apt install -y curl gnupg lsb-release
Añadir repo de Cloudflare:
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
Instalar:
sudo apt update
sudo apt install cloudflared

🔐 2. Login en Cloudflare

Ejecuta:

cloudflared tunnel login
Te dará una URL
Ábrela en tu navegador
Selecciona tu dominio

🚇 3. Crear el túnel
cloudflared tunnel create mi-tunel

Esto genera:

Un Tunnel ID

Un archivo credencial en:

/etc/cloudflared/<TUNNEL-ID>.json
⚙️ 4. Configurar el túnel

Crea el archivo:

sudo nano /etc/cloudflared/config.yml

Ejemplo:

tunnel: mi-tunel
credentials-file: /etc/cloudflared/TUNNEL_ID.json

ingress:
  - hostname: tu-dominio.com
    service: http://localhost:80

  - hostname: www.tu-dominio.com
    service: http://localhost:80

  - service: http_status:404

👉 Aquí es donde conectas con Nginx, que normalmente escucha en localhost:80.

🌐 5. Crear DNS en Cloudflare automáticamente
cloudflared tunnel route dns mi-tunel tu-dominio.com
cloudflared tunnel route dns mi-tunel www.tu-dominio.com

🚀 6. Ejecutar el túnel
Prueba manual:

cloudflared tunnel run mi-tunel

Si todo funciona, tu web ya debería salir por Cloudflare.

🔄 7. Ejecutarlo como servicio (IMPORTANTE)
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
