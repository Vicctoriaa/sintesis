# 🌐 Proyecto: Arquitectura y Sistemas

## 🎯 OBJETIVOS – FASE 1
**Planificación del proyecto:**  
Definir un calendario detallado con los objetivos, resultados a alcanzar y requisitos técnicos tanto de hardware como de software.

> **Nota:** Para llevar a cabo esta actividad es recomendable seguir el esquema de Gestión de Proyectos.

### ✅ Resumen de objetivos
1. Especificar objetivos y funcionalidades  
2. Especificar listado de tareas  
3. Asignar roles y responsabilidades del equipo  
4. Diseñar el diagrama de la red  
5. Determinar las tecnologías a implementar  
6. Definir el hardware a utilizar  
7. Identificar los servicios a implementar  
8. Establecer los sistemas operativos a utilizar  
9. Crear un diagrama de Gantt con los objetivos y resultados  
10. Documentar todo en GitHub

---

## 🛠 FUNCIONALIDADES

Completa la matriz de requisitos y funcionalidades asignando prioridad y fecha aproximada de entrega.

| ID   | Prioridad | Objetivo                       | Funcionalidad                                                                 | Disparador                                        | Fecha Entrega | Estado    |
|------|-----------|--------------------------------|-------------------------------------------------------------------------------|--------------------------------------------------|---------------|-----------|
| ID0  | Media     | Registrar usuarios en la página | Sistema de registro y login que guarde información individual del usuario      | Botón en la esquina superior → pantalla registro/login | 20/02/2025    | Pendiente |

**Leyenda:**  
- **ID:** número asignado de tarea  
- **Prioridad:** Baja, Media o Alta  
- **Funcionalidad:** La acción que realizará la aplicación para cumplir el requisito  
- **Disparador:** Evento que activa la funcionalidad  
- **Fecha:** aproximada de entrega  
- **Estado:** Activo, Pendiente o Cancelado

---

## 📋 LISTADO DE TAREAS

**Kanban:** metodología de gestión visual de proyectos que limita el trabajo en curso y mejora la productividad.  
Usaremos **Trello** para gestionar todas las tareas.

### Procedimiento
1. Revisar funcionalidades del proyecto  
2. Dividir el trabajo en tareas concretas  
3. Asignar un integrante a cada tarea  
4. Crear tarjetas en Trello para seguimiento

### Ejemplo de tareas

#### Objetivo 1: Implementar un servidor web
| Tarea | Responsable | Resultado esperado |
|-------|------------|-----------------|
| 1.1 Instalación y configuración básica del servidor | Maria | CP1.2 – Sistema operativo instalado y configurado en red |
| 1.2 Configuración de política de usuarios y privilegios | Enrique | CP1.2 – Sistema operativo instalado y configurado en red |
| 1.3 Instalación y configuración de servicios web (NGINX, MariaDB, PHP8.2, PHPMYADMIN) | Enrique | CP3.1.1 – Servicios web funcionando correctamente |

#### Objetivo 2: Programar la front-page
| Tarea | Responsable | Resultado esperado |
|-------|------------|-----------------|
| 2.1 Crear estructura del `index.html` con CSS | Jan | CP2.1.6 – Código correcto y experiencia de usuario adecuada |
| 2.2 Crear header y footer comunes | Maria | CP2.1.6 – Código correcto y experiencia de usuario adecuada |
| 2.3 Programar formulario de contacto | Enrique | CP2.1.6 – Código correcto y experiencia de usuario adecuada |

---

## 🏗 ARQUITECTURA DEL SISTEMA

**Fundamento:** identificar componentes clave o módulos de la aplicación. Cada componente realiza funciones específicas y se integra con otros para cumplir todos los requisitos.

> La arquitectura será cliente-servidor. Se debe especificar software, versión, puerto y uso de cada tecnología.

| Componente de sistema       | Tecnología / Framework | Versión | Puerto | Descripción de uso | Documentación |
|-----------------------------|----------------------|---------|--------|------------------|---------------|
| Hardware                    | Modelo, procesador, RAM, disco, adaptadores de red | - | - | Infraestructura física | - |
| Sistema operativo           | ¿Libre o propietario? | - | - | Sistema base para servidores | - |
| Interfaz de usuario (Frontend) | HTML, CSS, JavaScript, frameworks como React, Angular o Vue.js | - | - | Interacción con el usuario | - |
| Lógica de negocio (Backend) | PHP, Python, Java, Node.js, frameworks como Django, Flask, Spring, Express | - | - | Procesamiento de datos | - |
| Servidor web                | Apache, Nginx, Microsoft IIS | - | 80/443 | Servir la aplicación web | - |
| Base de datos               | MySQL, PostgreSQL, MongoDB, Firebase, SQLite | - | 3306 | Almacenamiento de datos | - |
| Sistema gestor de base de datos | MySQLWorkbench, PHPMyAdmin, Access, Oracle SQL, MongoDB Atlas | - | - | Gestión visual de la DB | - |
| Servicios de APIs           | REST, GraphQL, SOAP | - | - | Comunicación entre sistemas | - |

---

## 🗃 DIAGRAMA DE LA BASE DE DATOS

**Recomendaciones para el ERD:**
- Determinar los datos necesarios para la aplicación  
- Identificar tipos de usuarios y datos a solicitar  
- Definir tipo de dato de cada campo  
- Establecer claves primarias y relaciones entre tablas  

> Herramientas recomendadas: **draw.io**, **Lucidchart**, **Microsoft Visio**
