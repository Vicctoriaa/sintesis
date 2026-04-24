# SOAR - WEB

## Índice

1. [Descripción general](#1-descripción-general)
2. [Infraestructura](#2-infraestructura)
3. [Dominio con IONOS](#3-dominio-con-ionos)
4. [Túnel Cloudflare](#4-túnel-cloudflare)
5. [Servidor web — Apache](#5-servidor-web--apache)
6. [Base de datos — MariaDB](#6-base-de-datos--mariadb)
7. [Estructura de archivos de la web](#7-estructura-de-archivos-de-la-web)
8. [Flujo del formulario de contacto](#8-flujo-del-formulario-de-contacto)
9. [PHPMailer y envío de correos](#9-phpmailer-y-envío-de-correos)
10. [Funcionalidades del frontend](#10-funcionalidades-del-frontend)
11. [Validaciones implementadas](#11-validaciones-implementadas)
12. [Posibles mejoras futuras](#12-posibles-mejoras-futuras)

---

## 1. Descripción general

**HoneyCos** es una web corporativa ficticia especializada en tecnología de *deception* (engaño) y honeypots avanzados para ciberseguridad. El proyecto cubre desde la infraestructura hasta el desarrollo web completo:

- Servidor virtualizado con **Proxmox** y contenedor LXC.
- Dominio real **honeycos.com** gestionado en **IONOS**.
- Exposición segura a Internet mediante un **túnel Cloudflare** (sin IP pública expuesta).
- Web en **HTML/CSS/JS + PHP** servida con **Apache**.
- Base de datos **MariaDB** para almacenar contactos y suscriptores.
- Sistema de verificación de identidad por email (código OTP de 6 dígitos).

---

## 2. Infraestructura

### Arquitectura general

El proyecto corre sobre **Proxmox VE** con dos contenedores LXC interconectados en la misma red interna:

```
Internet
    │  (HTTPS)
    ▼
[Cloudflare Tunnel]
    │
    ▼
Contenedor: nginx-proxy  (cloudflared + Nginx reverse proxy)
    │  http://10.1.1.37:8080
    ▼
Contenedor: soar-web     (Apache + PHP + MariaDB)
    └── /var/www/html/
```

- **`nginx-proxy`** — aloja el daemon `cloudflared` y Nginx como reverse proxy. Recibe el tráfico de Cloudflare y lo reenvía internamente a `soar-web`.
- **`soar-web`** — aloja Apache, PHP, MariaDB y todos los archivos del sitio.

Todos los comandos se ejecutaron directamente dentro de cada contenedor por SSH.

```bash
ssh root@<IP_nginx-proxy>
ssh root@<IP_soar-web>
```

#### Preparación inicial del sistema (en ambos contenedores)

```bash
apt update && apt upgrade -y
apt install -y curl wget nano git unzip
```

---

## 3. Dominio con IONOS

El dominio **honeycos.com** fue comprado en [IONOS](https://www.ionos.es). La gestión DNS se delegó a **Cloudflare** para poder usar el túnel.

### Pasos realizados en IONOS

1. Comprar el dominio `honeycos.com`.
2. Ir a **Dominios → DNS → Cambiar servidores de nombres**.
3. Sustituir los nameservers de IONOS por los asignados por Cloudflare al añadir el dominio:

```
olivia.ns.cloudflare.com
drew.ns.cloudflare.com
```

> ⚠️ La propagación DNS puede tardar entre 15 minutos y 48 horas.

### Verificar la propagación

```bash
dig NS honeycos.com +short

# Resultado esperado
olivia.ns.cloudflare.com.
drew.ns.cloudflare.com.
```

---

## 4. Túnel Cloudflare + Nginx reverse proxy

El túnel Cloudflare y el reverse proxy Nginx están configurados en el contenedor **`nginx-proxy`**. Este contenedor recibe el tráfico desde Cloudflare y lo reenvía internamente al contenedor `soar-web` en `10.1.1.37:8080`.

### 4.1 Instalar cloudflared en `nginx-proxy`

```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
  gpg --dearmor -o /usr/share/keyrings/cloudflare-main.gpg

echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
  https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
  | tee /etc/apt/sources.list.d/cloudflared.list

apt update && apt install -y cloudflared
```

### 4.2 Autenticar y crear el túnel

```bash
cloudflared tunnel login
# Abre una URL en el navegador → seleccionar honeycos.com

cloudflared tunnel create mi-tunel
# Genera el archivo de credenciales JSON automáticamente
```

### 4.3 Archivos de configuración del túnel

Los archivos se guardan en `/etc/cloudflared/`:

```
root@nginx-proxy:/etc/cloudflared/
├── config.yml       # Configuración del túnel
└── mi-tunel.json    # Credenciales del túnel (UUID + token)
```

Contenido de `config.yml`:

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

> El túnel apunta a `localhost:8080` donde Nginx escucha y hace el proxy interno hacia `soar-web`.

### 4.4 Enrutar el DNS del túnel

```bash
cloudflared tunnel route dns mi-tunel honeycos.com
cloudflared tunnel route dns mi-tunel www.honeycos.com
# Crea registros CNAME en Cloudflare apuntando al túnel automáticamente
```

### 4.5 Ejecutar cloudflared como servicio

```bash
cloudflared service install
systemctl enable cloudflared
systemctl start cloudflared
systemctl status cloudflared
```

### 4.6 Nginx — reverse proxy hacia soar-web

Nginx escucha en el puerto `8080` y redirige el tráfico al contenedor `soar-web` (`10.1.1.37:8080`).

```bash
apt install -y nginx
```

Archivo `/etc/nginx/sites-available/soar`:

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

Activar el sitio y recargar Nginx:

```bash
ln -s /etc/nginx/sites-available/soar /etc/nginx/sites-enabled/soar
nginx -t
systemctl reload nginx
```

---

## 5. Servidor web — Apache

### Instalar Apache y PHP

```bash
apt install -y apache2 php php-mysql php-mbstring libapache2-mod-php
```

### Habilitar módulos necesarios

```bash
a2enmod rewrite
systemctl restart apache2
```

### Directorio de la web

Los archivos de la web se alojan en:

```
/var/www/html/
```

### Permisos correctos

```bash
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html
```

### Verificar que Apache funciona

```bash
systemctl status apache2
curl http://localhost
```

---

## 6. Base de datos — MariaDB

### Instalar MariaDB

```bash
apt install -y mariadb-server
systemctl enable mariadb
systemctl start mariadb

# Securizar la instalación
mysql_secure_installation
```

### Crear la base de datos y el usuario

```sql
-- Acceder como root
mysql -u root -p

-- Crear la base de datos
CREATE DATABASE honeycos_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Crear el usuario con contraseña
CREATE USER 'user'@'127.0.0.1' IDENTIFIED BY 'password!';

-- Conceder permisos solo sobre la base de datos del proyecto
GRANT ALL PRIVILEGES ON honeycos_db.* TO 'user'@'127.0.0.1';
FLUSH PRIVILEGES;

EXIT;
```

### Crear las tablas necesarias

```sql
USE honeycos_db;

-- Tabla de contactos verificados (formulario principal)
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

-- Tabla temporal para verificaciones pendientes (OTP)
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

-- Tabla de suscriptores al newsletter
CREATE TABLE suscriptores (
    id      INT AUTO_INCREMENT PRIMARY KEY,
    correo  VARCHAR(150) NOT NULL UNIQUE,
    fecha   TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Verificar las tablas

```bash
mysql -u user -p honeycos_db -e "SHOW TABLES;"
```

---

## 7. Estructura de archivos de la web

```
/var/www/html/
│
├── index.html              # Página principal (hero, servicios, tecnología, formulario)
├── style.css               # Estilos globales con modo claro/oscuro
├── script.js               # Validaciones JS del formulario
│
├── contacto.php            # Recibe el formulario → genera OTP → envía email → redirige
├── verificar.php           # Página para introducir el código OTP
├── procesar_final.php      # Valida el OTP → inserta en contactos → muestra éxito
│
├── suscripcion.php         # Gestiona suscripción al newsletter
│
└── phpmailer/              # Librería PHPMailer (copiada manualmente o con Composer)
    ├── PHPMailer.php
    ├── SMTP.php
    └── Exception.php
```

### Instalar PHPMailer (opción con Composer)

```bash
apt install -y composer
cd /var/www/html
composer require phpmailer/phpmailer
```

### Instalar PHPMailer (opción manual)

```bash
cd /var/www/html
mkdir phpmailer
cd phpmailer
wget https://github.com/PHPMailer/PHPMailer/raw/master/src/PHPMailer.php
wget https://github.com/PHPMailer/PHPMailer/raw/master/src/SMTP.php
wget https://github.com/PHPMailer/PHPMailer/raw/master/src/Exception.php
```

---

## 8. Flujo del formulario de contacto

El proceso de contacto implementa verificación de identidad en dos pasos:

```
Usuario rellena el formulario (index.html)
        │
        ▼
[contacto.php]
  · Recoge los datos POST
  · Genera un código OTP de 6 dígitos aleatorio
  · Guarda datos + código en verificaciones_pendientes (expira en 15 min)
  · Envía el código al email del usuario via SMTP (IONOS)
  · Redirige a verificar.php?email=<correo>
        │
        ▼
[verificar.php]
  · Muestra un campo para introducir el código de 6 dígitos
        │
        ▼
[procesar_final.php]
  · Busca el registro en verificaciones_pendientes con correo + código + no expirado
  · Si es válido:
      → Inserta los datos en la tabla contactos
      → Borra el registro de verificaciones_pendientes
      → Muestra página de éxito con el nombre del usuario
  · Si no es válido o expirado:
      → Alerta de error y redirige al inicio
```

---

## 9. PHPMailer y envío de correos

### Configuración SMTP usada en `contacto.php`

El correo de verificación se envía desde una cuenta IONOS corporativa:

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

### Configuración SMTP alternativa en `suscripcion.php` (Gmail)

Para el newsletter se usa una cuenta Gmail con contraseña de aplicación:

```php
$mail->Host       = 'smtp.gmail.com';
$mail->SMTPAuth   = true;
$mail->Username   = 'telenecos9@gmail.com';
$mail->Password   = '<CONTRASEÑA_DE_APLICACION_GMAIL>';
$mail->SMTPSecure = 'tls';
$mail->Port       = 587;
```

> ℹ️ Para usar Gmail con PHP necesitas activar la **verificación en dos pasos** en tu cuenta Google y generar una **contraseña de aplicación** en `myaccount.google.com/apppasswords`.

### Probar el envío de correo desde CLI

```bash
# Comprobar que el puerto SMTP está accesible
telnet smtp.ionos.es 587

# O con curl
curl -v smtp://smtp.ionos.es:587
```

---

## 10. Funcionalidades del frontend

### `index.html`

- **Navegación sticky** con scroll suave entre secciones.
- **Toggle modo oscuro/claro** persistido en `localStorage`.
- Secciones: *Hero*, *Estadísticas*, *Servicios*, *Tecnología* y *Contacto*.
- Animación de terminal en la sección de tecnología (línea de escaneo CSS).
- **Formulario de contacto** con validaciones en tiempo real.

### `style.css`

- Variables CSS para dos paletas de color (claro y oscuro).
- Diseño *responsive* con `grid` y `flexbox`.
- Breakpoints: `992px`, `768px` y `480px`.
- Transiciones suaves al cambiar de modo.

### `script.js`

- Gestión del toggle de modo oscuro.
- Formateo automático del teléfono según prefijo de país.
- Validación de CIF/NIF/EIN con límite dinámico de caracteres.
- Validación de email corporativo/institucional.
- El botón de envío permanece deshabilitado hasta que todos los campos son válidos.

---

## 11. Validaciones implementadas

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

---

## Créditos

**Proyecto Final de Curso** — HoneyCos Security Services © 2026  
Tecnologías utilizadas: Proxmox · LXC · Cloudflare Tunnel · Apache · PHP · MariaDB · PHPMailer · HTML5 · CSS3 · JavaScript
