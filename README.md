# 🌐 Proyecto: Arquitectura y Sistemas

## 🎯 Objetivos Generales
Definir, planificar y documentar la arquitectura y los sistemas de la aplicación, incluyendo hardware, software, roles, tareas y planificación temporal.

---

## 📅 FASE 1: Planificación del Proyecto

**Objetivo:**  
Planificar el proyecto definiendo un calendario detallado con los objetivos, resultados a alcanzar, y requisitos técnicos (hardware y software).

**Esquema resumido:**
1. Especificar objetivos y funcionalidades  
2. Listado de tareas  
3. Asignar roles y responsabilidades del equipo  
4. Diagrama de la red  
5. Tecnologías a implementar  
6. Hardware a utilizar  
7. Servicios a implementar  
8. Sistemas operativos a utilizar  
9. Diagrama de Gantt con objetivos y resultados  
10. Documentación en GitHub

---

## 🛠 Funcionalidades y Requisitos

| ID   | Prioridad | Objetivo                       | Funcionalidad                                                                 | Disparador                                        | Fecha Entrega | Estado    |
|------|-----------|--------------------------------|-------------------------------------------------------------------------------|--------------------------------------------------|---------------|-----------|
| ID0  | Media     | Registrar usuarios en la página | Crear sistema de registro y login que almacene información individual del usuario | Botón superior → pantalla registro/login         | 20/02/2025    | Pendiente |

**Leyenda:**  
- Prioridad: Baja / Media / Alta  
- Estado: Activo / Pendiente / Cancelado  

---

## 📋 Listado de Tareas (Kanban / Trello)

### Objetivo 1: Implementar un servidor web
| Tarea | Responsable | Resultado esperado |
|-------|------------|-----------------|
| 1.1 Instalación y configuración básica del servidor | Maria | Sistema operativo instalado y configurado en red |
| 1.2 Configuración de política de usuarios y privilegios | Enrique | Sistema operativo instalado y configurado en red |
| 1.3 Instalación y configuración de servicios web (NGINX, MariaDB, PHP8.2, PHPMYADMIN) | Enrique | Servicios web funcionando correctamente |

### Objetivo 2: Programar la front-page
| Tarea | Responsable | Resultado esperado |
|-------|------------|-----------------|
| 2.1 Crear estructura de `index.html` con CSS | Jan | Código correcto y experiencia de usuario adecuada |
| 2.2 Crear header y footer comunes | Maria | Código correcto y experiencia de usuario adecuada |
| 2.3 Programar formulario de contacto | Enrique | Código correcto y experiencia de usuario adecuada |

---

## 🏗 Arquitectura del Sistema

### Componentes y Tecnologías
| Componente                  | Tecnología / Framework | Versión | Puerto | Descripción | Documentación |
|-----------------------------|----------------------|---------|--------|------------|---------------|
| 💻 Hardware | PC / Servidor | - | - | Procesador, RAM, Disco, adaptadores de red | - |
| 🖥 Sistema Operativo | Linux / Windows | Última | - | Soporte para servicios y backend | - |
| 🎨 Frontend | HTML, CSS, JavaScript, React | Última | - | Interfaz de usuario | [React](https://reactjs.org/) |
| ⚙ Backend | PHP, Node.js, Python | Última | 8080 | Lógica de negocio | - |
| 🌐 Servidor Web | NGINX / Apache | Última | 80/443 | Servir la web | - |
| 🗄 Base de Datos | MySQL / PostgreSQL | 8.x | 3306 | Almacenamiento de datos | [MySQL](https://dev.mysql.com/doc/) |
| 🛠 Gestión BD | PHPMyAdmin / MySQL Workbench | Última | 8080 | Gestión visual de la base de datos | - |
| 🔌 APIs | REST / GraphQL | Última | 3000 | Comunicación frontend-backend | - |

---

## 🗃 Diagrama de Base de Datos (ER)
> Recomendado usar herramientas como **draw.io**, **Lucidchart** o **Visio**.  

Considerar:
- Tablas: usuarios, productos, pedidos, roles, etc.  
- Tipos de datos y claves primarias  
- Relaciones entre tablas

---

## 🌐 Estructura Básica de la Red

```text
[Clientes] ---Internet--- [Router] --- [Switch] --- [Servidor Web]
                                    |--- [Servidor BD]
                                    |--- [Servidor de Archivos]
