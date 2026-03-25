# 🗄️ Configuración de MariaDB y Conexión con PHP

> Guía completa para instalar MariaDB, crear la base de datos del formulario de contacto y conectarla desde PHP.

---

## 📋 Tabla de Contenidos

1. [Instalación de MariaDB](#1-instalación-de-mariadb)
2. [Conectarse a MariaDB](#2-conectarse-a-mariadb)
3. [Crear la Base de Datos](#3-crear-la-base-de-datos)
4. [Crear la Tabla de Contactos](#4-crear-la-tabla-de-contactos)
5. [Crear Usuario y Permisos](#5-crear-usuario-y-permisos)
6. [Conexión desde PHP](#6-conexión-desde-php)

---

## 1. Instalación de MariaDB

Actualiza el sistema e instala MariaDB server y cliente:

```bash
# Actualizar repositorios y paquetes
apt update && apt upgrade -y

# Instalar MariaDB server y cliente
apt install mariadb-server mariadb-client -y

# Iniciar y habilitar el servicio de MariaDB
systemctl start mariadb
systemctl enable mariadb

# Ejecutar configuración segura de MariaDB
mysql_secure_installation
```

> **💡 Tip:** Durante `mysql_secure_installation` se recomienda responder `Y` a todas las opciones para una configuración segura.

---

## 2. Conectarse a MariaDB

Abre la terminal y conéctate como usuario root:

```bash
mysql -u root -p
```

---

## 3. Crear la Base de Datos

```sql
-- Crear base de datos con soporte UTF-8 completo
CREATE DATABASE honeycos_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

-- Seleccionar la base de datos
USE honeycos_db;
```

---

## 4. Crear la Tabla de Contactos

```sql
CREATE TABLE contactos (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    nombre           VARCHAR(100) NOT NULL,
    empresa          VARCHAR(100) NOT NULL,
    email            VARCHAR(150) NOT NULL,
    telefono         VARCHAR(20),
    servicio_interes VARCHAR(100) NOT NULL,
    mensaje          TEXT         NOT NULL,
    gdpr_aceptado    TINYINT(1)   NOT NULL DEFAULT 0,
    fecha            TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
```

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | INT | Clave primaria autoincremental |
| `nombre` | VARCHAR(100) | Nombre del contacto |
| `empresa` | VARCHAR(100) | Empresa del contacto |
| `email` | VARCHAR(150) | Correo electrónico |
| `telefono` | VARCHAR(20) | Teléfono (opcional) |
| `servicio_interes` | VARCHAR(100) | Servicio de interés seleccionado |
| `mensaje` | TEXT | Cuerpo del mensaje |
| `gdpr_aceptado` | TINYINT(1) | Aceptación RGPD (0 = No, 1 = Sí) |
| `fecha` | TIMESTAMP | Fecha de envío (automática) |

---

## 5. Crear Usuario y Permisos

```sql
-- Crear usuario para la aplicación web
CREATE USER 'webuser'@'localhost' IDENTIFIED BY 'StrongPass123!';

-- Conceder permisos sobre la base de datos
GRANT ALL PRIVILEGES ON honeycos_db.* TO 'webuser'@'localhost';

-- Aplicar cambios
FLUSH PRIVILEGES;
```

> **⚠️ Seguridad:** Cambia `StrongPass123!` por una contraseña robusta y única en producción.

---

## 6. Conexión desde PHP

Script PHP para recibir los datos del formulario de contacto e insertarlos en la base de datos de forma segura mediante **prepared statements**:

```php
<?php

// ── Datos de conexión ─────────────────────────────────────────────────────────
$host = 'localhost';
$db   = 'honeycos_db';
$user = 'webuser';
$pass = 'StrongPass123!';

// ── Crear conexión ────────────────────────────────────────────────────────────
$conn = new mysqli($host, $user, $pass, $db);

// Verificar conexión
if ($conn->connect_error) {
    die("Conexión fallida: " . $conn->connect_error);
}

// ── Recibir datos del formulario ──────────────────────────────────────────────
$nombre   = $_POST['c-name']    ?? '';
$empresa  = $_POST['c-company'] ?? '';
$email    = $_POST['c-email']   ?? '';
$telefono = $_POST['c-phone']   ?? '';
$servicio = $_POST['c-service'] ?? '';
$mensaje  = $_POST['c-msg']     ?? '';
$gdpr     = isset($_POST['c-gdpr']) ? 1 : 0;

// ── Insertar con prepared statement (previene SQL injection) ──────────────────
$stmt = $conn->prepare("
    INSERT INTO contactos
        (nombre, empresa, email, telefono, servicio_interes, mensaje, gdpr_aceptado)
    VALUES
        (?, ?, ?, ?, ?, ?, ?)
");

$stmt->bind_param("ssssssi", $nombre, $empresa, $email, $telefono, $servicio, $mensaje, $gdpr);

// ── Respuesta JSON ────────────────────────────────────────────────────────────
if ($stmt->execute()) {
    echo json_encode(['status' => 'success', 'message' => 'Mensaje recibido']);
} else {
    echo json_encode(['status' => 'error',   'message' => 'Error al enviar']);
}

$stmt->close();
$conn->close();
```

---

## ✅ Resumen del flujo

```
Formulario HTML  →  POST  →  script PHP
                               │
                               ├─ Valida conexión a MariaDB
                               ├─ Recoge campos del POST
                               ├─ Ejecuta prepared statement
                               └─ Devuelve JSON { status, message }
```

---

*Documentación generada para el proyecto **Honeycos**.*
