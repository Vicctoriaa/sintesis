
# SOAR Web — CT104

> Web corporativa ficticia de HoneyCos, especializada en tecnología de *deception* y honeypots. Sirve como superficie de exposición pública del proyecto y como demostración de integración completa: infraestructura virtualizada, dominio real, túnel Cloudflare, servidor web PHP y base de datos con verificación de identidad por email.

---

## Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 104 |
| Hostname | `soar-web` |
| OS | Debian 12 |
| Memoria | 256 MB |
| Disco | 20 GB |
| Cores | 1 |
| Bridge | `vmbr1` — VLAN 20 Servicios |
| IP | `10.1.1.37/27` |
| Gateway | `10.1.1.33` |

---

## Arquitectura

```
Internet (HTTPS)
    ↓
Cloudflare Tunnel
    ↓
CT105 nginx-proxy (cloudflared + Nginx :8080)
    ↓ http://10.1.1.37:8080
CT104 soar-web (Apache + PHP + MariaDB)
    └── /var/www/html/
```

- **CT105 nginx-proxy** — aloja el daemon `cloudflared` y Nginx como reverse proxy. Recibe el tráfico de Cloudflare y lo reenvía internamente a `soar-web`.
- **CT104 soar-web** — aloja Apache, PHP, MariaDB y todos los archivos del sitio.

---

## Dominio — honeycos.com (IONOS)

El dominio `honeycos.com` está registrado en IONOS con la gestión DNS delegada a Cloudflare.

### Configuración en IONOS

1. Comprar el dominio `honeycos.com`.
2. Ir a **Dominios → DNS → Cambiar servidores de nombres**.
3. Sustituir los nameservers de IONOS por los de Cloudflare:

```
olivia.ns.cloudflare.com
drew.ns.cloudflare.com
```

> La propagación DNS puede tardar entre 15 minutos y 48 horas.

### Verificar propagación

```bash
dig NS honeycos.com +short
# Resultado esperado:
# olivia.ns.cloudflare.com.
# drew.ns.cloudflare.com.
```

---

## Túnel Cloudflare + Nginx reverse proxy

Configurados en CT105 (`nginx-proxy`). El túnel recibe el tráfico de Cloudflare y Nginx lo reenvía a `soar-web` en `10.1.1.37:8080`.

### Instalar cloudflared en CT105

```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
  gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg

echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
  https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
  | tee /etc/apt/sources.list.d/cloudflared.list

apt update && apt install -y cloudflared
```

### Crear el túnel

```bash
cloudflared tunnel login
# Abre URL en el navegador → seleccionar honeycos.com

cloudflared tunnel create mi-tunel
# Genera el archivo de credenciales JSON automáticamente
```

### Archivos de configuración — `/etc/cloudflared/`

```
/etc/cloudflared/
├── config.yml        # Configuración del túnel
└── mi-tunel.json     # Credenciales (UUID + token)
```

**`config.yml`:**

```yaml
tunnel: <UUID-DEL-TUNEL>
credentials-file: /etc/cloudflared/mi-tunel.json

ingress:
  - hostname: honeycos.com
    service: http://localhost:8080
  - hostname: www.honeycos.com
    service: http://localhost:8080
  - service: http_status:404
```

### Enrutar DNS del túnel

```bash
cloudflared tunnel route dns mi-tunel honeycos.com
cloudflared tunnel route dns mi-tunel www.honeycos.com
# Crea registros CNAME en Cloudflare apuntando al túnel automáticamente
```

### Ejecutar cloudflared como servicio

```bash
cloudflared service install
systemctl enable cloudflared
systemctl start cloudflared
```

### Nginx — `/etc/nginx/sites-available/soar`

```nginx
server {
    listen 8080;
    server_name honeycos.com www.honeycos.com;

    location / {
        proxy_pass         http://10.1.1.37:8080;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/soar /etc/nginx/sites-enabled/soar
nginx -t && systemctl reload nginx
```

---

## Servidor web — Apache

```bash
apt install -y apache2 php php-mysql php-mbstring libapache2-mod-php
a2enmod rewrite
systemctl restart apache2
```

```bash
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html
```

---

## Base de datos — MariaDB

```bash
apt install -y mariadb-server
systemctl enable mariadb && systemctl start mariadb
mysql_secure_installation
```

### Crear base de datos y usuario

```sql
CREATE DATABASE honeycos_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'user'@'127.0.0.1' IDENTIFIED BY 'password!';
GRANT ALL PRIVILEGES ON honeycos_db.* TO 'user'@'127.0.0.1';
FLUSH PRIVILEGES;
```

### Tablas

```sql
USE honeycos_db;

-- Contactos verificados
CREATE TABLE contactos (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(100)  NOT NULL,
    empresa     VARCHAR(100)  NOT NULL,
    correo      VARCHAR(150)  NOT NULL,
    telefono    VARCHAR(30)   NOT NULL,
    servicio    VARCHAR(50)   NOT NULL,
    mensaje     TEXT          NOT NULL,
    ip_origen   VARCHAR(45)   NOT NULL,
    fecha       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Verificaciones pendientes (OTP)
CREATE TABLE verificaciones_pendientes (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    nombre      VARCHAR(100)  NOT NULL,
    empresa     VARCHAR(100)  NOT NULL,
    correo      VARCHAR(150)  NOT NULL,
    telefono    VARCHAR(30)   NOT NULL,
    servicio    VARCHAR(50)   NOT NULL,
    mensaje     TEXT          NOT NULL,
    codigo      CHAR(6)       NOT NULL,
    ip_origen   VARCHAR(45)   NOT NULL,
    expira      DATETIME      NOT NULL,
    creado      TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Suscriptores newsletter
CREATE TABLE suscriptores (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    correo  VARCHAR(150) NOT NULL UNIQUE,
    fecha   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## Estructura de archivos

```
/var/www/html/
│
├── index.html              # Página principal (hero, servicios, tecnología, formulario)
├── style.css               # Estilos globales con modo claro/oscuro
├── script.js               # Validaciones JS del formulario
│
├── contacto.php            # Recibe formulario → genera OTP → envía email → redirige
├── verificar.php           # Página para introducir el código OTP
├── procesar_final.php      # Valida OTP → inserta en contactos → muestra éxito
│
├── suscripcion.php         # Gestiona suscripción al newsletter
│
└── phpmailer/
    ├── PHPMailer.php
    ├── SMTP.php
    └── Exception.php
```

### Instalar PHPMailer

```bash
# Con Composer
apt install -y composer
cd /var/www/html && composer require phpmailer/phpmailer

# O manual
mkdir /var/www/html/phpmailer && cd /var/www/html/phpmailer
wget https://github.com/PHPMailer/PHPMailer/raw/master/src/PHPMailer.php
wget https://github.com/PHPMailer/PHPMailer/raw/master/src/SMTP.php
wget https://github.com/PHPMailer/PHPMailer/raw/master/src/Exception.php
```

---

## Flujo del formulario de contacto

```
Usuario rellena el formulario (index.html)
        ↓
[contacto.php]
  · Recoge datos POST
  · Genera OTP de 6 dígitos
  · Guarda datos + código en verificaciones_pendientes (expira 15 min)
  · Envía código al email del usuario via SMTP (IONOS)
  · Redirige a verificar.php?email=<correo>
        ↓
[verificar.php]
  · Muestra campo para introducir el código de 6 dígitos
        ↓
[procesar_final.php]
  · Busca registro en verificaciones_pendientes con correo + código + no expirado
  · Si válido → inserta en contactos → borra verificación → muestra éxito
  · Si inválido/expirado → alerta de error → redirige al inicio
```

---

## PHPMailer — configuración SMTP

### Verificación OTP (`contacto.php`) — IONOS

```php
$mail->Host       = 'smtp.ionos.es';
$mail->SMTPAuth   = true;
$mail->Username   = 'contacto@honeycos.com';
$mail->Password   = '<CONTRASEÑA_SMTP>';
$mail->SMTPSecure = PHPMailer::ENCRYPTION_STARTTLS;
$mail->Port       = 587;
$mail->CharSet    = 'UTF-8';

$mail->setFrom('contacto@honeycos.com', 'HoneyCos Security');
$mail->addAddress($correo);
$mail->isHTML(true);
$mail->Subject = "[$codigo] Verificación HoneyCos";
$mail->Body    = "Hola $nombre, tu código es: <b>$codigo</b>";
```

### Newsletter (`suscripcion.php`) — Gmail

```php
$mail->Host       = 'smtp.gmail.com';
$mail->SMTPAuth   = true;
$mail->Username   = 'telenecos9@gmail.com';
$mail->Password   = '<CONTRASEÑA_DE_APLICACION_GMAIL>';
$mail->SMTPSecure = 'tls';
$mail->Port       = 587;
```

> Para Gmail es necesario activar la verificación en dos pasos y generar una contraseña de aplicación en `myaccount.google.com/apppasswords`.

---

## Frontend

### `index.html`

- Navegación sticky con scroll suave entre secciones.
- Toggle modo oscuro/claro persistido en `localStorage`.
- Secciones: Hero, Estadísticas, Servicios, Tecnología y Contacto.
- Animación de terminal en la sección de tecnología.
- Formulario de contacto con validaciones en tiempo real.

### `style.css`

- Variables CSS para dos paletas de color (claro y oscuro).
- Diseño responsive con `grid` y `flexbox`.
- Breakpoints: `992px`, `768px`, `480px`.

### `script.js`

- Toggle de modo oscuro.
- Formateo automático del teléfono según prefijo de país.
- Validación de CIF/NIF/EIN con límite dinámico de caracteres.
- Validación de email corporativo/institucional.
- Botón de envío deshabilitado hasta que todos los campos son válidos.

---

## Validaciones

### Teléfono — países soportados

| Prefijo | País | Dígitos (sin prefijo) |
|---------|------|-----------------------|
| +34 | España | 9 |
| +33 | Francia | 9 |
| +49 | Alemania | 11 |
| +39 | Italia | 11 |
| +44 | Reino Unido | 10 |
| +351 | Portugal | 9 |
| +1 | USA/Canadá | 10 |
| +52 | México | 10 |
| +54 | Argentina | 11 |

### Identificación fiscal — formatos aceptados

| País | Formato | Ejemplo |
|------|---------|---------|
| España | `[A-Z][0-9]{7}[0-9A-Z]` | `B12345678` |
| Francia / Portugal | 9 dígitos | `123456789` |
| Alemania | `DE` + 9 dígitos | `DE123456789` |
| Italia | 11 dígitos | `12345678901` |
| Reino Unido | `GB` + 9–12 dígitos | `GB123456789` |
| USA (EIN) | `XX-XXXXXXX` | `12-3456789` |
| México | 3–4 letras + 6 dígitos + 3 alfanum. | `ABC123456X01` |
| Argentina | `XX-XXXXXXXX-X` | `20-12345678-5` |

### Email — dominios aceptados

| Tipo | Valores |
|------|---------|
| Dominios gratuitos | `gmail.com`, `outlook.com`, `hotmail.com`, `proton.me`, `honeycos.com` |
| Extensiones institucionales | `.edu`, `.gov`, `.org`, `.gob.es` |
