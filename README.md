FASE 1: Planificación del Proyecto

Objetivo:
Planificar el proyecto definiendo un calendario detallado con los objetivos, resultados a alcanzar, y requisitos técnicos (hardware y software).

Esquema resumido:

Especificar objetivos y funcionalidades.

Especificar listado de tareas.

Asignar roles y responsabilidades del equipo.

Diseñar el diagrama de la red.

Seleccionar tecnologías a implementar.

Definir el hardware a utilizar.

Identificar los servicios a implementar.

Determinar los sistemas operativos a utilizar.

Establecer un diagrama de Gantt con objetivos y resultados.

Documentar en GitHub.

Funcionalidades
ID	Prioridad	Objetivo	Funcionalidad	Disparador	Fecha Entrega	Estado
ID0	Media	Registrar usuarios en la página	Crear sistema de registro y login que almacene información individual del usuario	Botón en la esquina superior → pantalla registro/login	20/02/2025	Pendiente

Leyenda:

ID: Número de tarea.

Prioridad: Baja, Media o Alta.

Objetivo: Qué se busca conseguir.

Funcionalidad: Qué hará la aplicación.

Disparador: Evento que activa la función.

Fecha: Entrega aproximada.

Estado: Activo, Pendiente o Cancelado.

Listado de Tareas (Metodología Kanban)

Usamos Trello para gestionar las tareas visualmente. Cada tarea es una tarjeta que se revisará durante la producción.

Ejemplo de planificación de tareas

Objetivo 1: Implementar un servidor web

1.1 [Maria] Instalación y configuración básica del servidor
CP1.2 – Sistema operativo instalado y configurado en red

1.2 [Enrique] Configuración de política de usuarios y privilegios
CP1.2 – Sistema operativo instalado y configurado en red

1.3 [Enrique] Instalación y configuración de servicios web: NGINX, MariaDB, PHP 8.2, PHPMYADMIN
CP3.1.1 – Servicios web funcionando correctamente

Objetivo 2: Programar la front-page

2.1 [Jan] Crear la estructura del index.html con CSS
CP2.1.6 – Código correcto, experiencia de usuario adecuada

2.2 [Maria] Crear header y footer comunes
CP2.1.6 – Código correcto, experiencia de usuario adecuada

2.3 [Enrique] Programar formulario de contacto de la frontpage
CP2.1.6 – Código correcto, experiencia de usuario adecuada

Arquitectura del Sistema
Componentes y Tecnologías
Componente	Tecnología / Framework	Versión	Puerto	Descripción de uso	Documentación
Hardware	PC / Servidor	-	-	Procesador, RAM, Disco, adaptadores de red	-
Sistema Operativo	Linux / Windows	Última	-	Soporte para servicios y backend	-
Interfaz de Usuario (Frontend)	HTML, CSS, JavaScript, React	Última	-	Construcción de la UI, interacción con el usuario	React Docs

Lógica de negocio (Backend)	PHP, Node.js, Python	Última	8080	Procesamiento de datos y reglas de negocio	-
Servidor web	NGINX / Apache	Última	80/443	Servir la web a los clientes	-
Base de datos	MySQL / PostgreSQL	8.x	3306	Almacenamiento de datos de la aplicación	MySQL Docs

Sistema gestor de base de datos	PHPMyAdmin / MySQL Workbench	Última	8080	Gestión visual de la base de datos	-
Servicios de APIs	REST / GraphQL	Última	3000	Comunicación entre frontend y backend	-
Diagrama de la Base de Datos

Se recomienda usar herramientas gráficas como draw.io, Lucidchart o Microsoft Visio para diseñar el diagrama entidad-relación (ER).
Considerar:

Qué datos necesita la aplicación.

Tipos de usuarios y datos a solicitar.

Tipos de datos y claves primarias.

Relaciones entre tablas.

Estructura Básica de la Red

Se debe diseñar un diagrama de red que incluya:

Servidores (web, base de datos, archivos).

Switches y routers (si aplica).

Segmentación de red por VLANs o subredes.

Conexión cliente-servidor.

Si quieres, puedo hacer una versión aún más visual y elegante, con tablas de colores, íconos de roles, y un mini-diagrama de red integrado, lista para entregar o presentar en PDF/Word.

¿Quieres que haga eso?

si

Perfecto 😎, vamos a hacer una versión mucho más visual, limpia y profesional, lista para entregar o exportar a PDF/Word. La organizaré con colores, íconos, tablas claras y mini-diagramas, manteniendo toda la información que me diste. Aquí te la dejo:

🌐 Proyecto: Arquitectura y Sistemas
🎯 Objetivos Generales

Definir, planificar y documentar la arquitectura y los sistemas de la aplicación, incluyendo hardware, software, roles, tareas y planificación temporal.

📅 FASE 1: Planificación del Proyecto

Objetivo:
Planificar el proyecto definiendo un calendario detallado con los objetivos, resultados a alcanzar, y requisitos técnicos (hardware y software).

Esquema resumido:

Especificar objetivos y funcionalidades.

Listado de tareas.

Asignar roles y responsabilidades del equipo.

Diagrama de la red.

Tecnologías a implementar.

Hardware a utilizar.

Servicios a implementar.

Sistemas operativos a utilizar.

Diagrama de Gantt con objetivos y resultados.

Documentación en GitHub.

🛠 Funcionalidades y Requisitos
ID	Prioridad	Objetivo	Funcionalidad	Disparador	Fecha Entrega	Estado
ID0	🔶 Media	Registrar usuarios en la página	Crear sistema de registro y login que almacene información individual del usuario	Botón superior → pantalla registro/login	20/02/2025	⏳ Pendiente

Leyenda:

🔴 Alta | 🔶 Media | 🟢 Baja

⏳ Pendiente | ✅ Activo | ❌ Cancelado

📋 Listado de Tareas (Kanban / Trello)
Objetivo 1: Implementar un servidor web
Tarea	Responsable	Resultado esperado
1.1 Instalación y configuración básica del servidor	Maria	CP1.2 – Sistema operativo instalado y configurado en red
1.2 Configuración de política de usuarios y privilegios	Enrique	CP1.2 – Sistema operativo instalado y configurado en red
1.3 Instalación y configuración de servicios web (NGINX, MariaDB, PHP8.2, PHPMYADMIN)	Enrique	CP3.1.1 – Servicios web funcionando correctamente
Objetivo 2: Programar la front-page
Tarea	Responsable	Resultado esperado
2.1 Crear estructura de index.html con CSS	Jan	CP2.1.6 – Código correcto y experiencia de usuario adecuada
2.2 Crear header y footer comunes	Maria	CP2.1.6 – Código correcto y experiencia de usuario adecuada
2.3 Programar formulario de contacto	Enrique	CP2.1.6 – Código correcto y experiencia de usuario adecuada
🏗 Arquitectura del Sistema
Componentes y Tecnologías
Componente	Tecnología / Framework	Versión	Puerto	Descripción	Documentación
💻 Hardware	PC / Servidor	-	-	Procesador, RAM, Disco, adaptadores de red	-
🖥 Sistema Operativo	Linux / Windows	Última	-	Soporte para servicios y backend	-
🎨 Frontend	HTML, CSS, JavaScript, React	Última	-	Interfaz de usuario	React

⚙ Backend	PHP, Node.js, Python	Última	8080	Lógica de negocio	-
🌐 Servidor Web	NGINX / Apache	Última	80/443	Servir la web	-
🗄 Base de Datos	MySQL / PostgreSQL	8.x	3306	Almacenamiento de datos	MySQL

🛠 Gestión BD	PHPMyAdmin / MySQL Workbench	Última	8080	Gestión visual de la base de datos	-
🔌 APIs	REST / GraphQL	Última	3000	Comunicación frontend-backend	-
🗃 Diagrama de Base de Datos (ER)

Recomendado usar draw.io, Lucidchart o Visio.
Debe incluir:

Tablas de usuarios, productos, pedidos, roles, etc.

Tipos de datos y claves primarias.

Relaciones entre tablas.

(Aquí puedes insertar un mini-diagrama visual con íconos para cada tabla si quieres que quede más atractivo.)

🌐 Estructura Básica de la Red

Diagrama sugerido:

[Clientes] ---Internet--- [Router] --- [Switch] --- [Servidor Web]
                                    |--- [Servidor BD]
                                    |--- [Servidor de Archivos]

Notas:

Segmentación de red por VLANs o subredes si aplica.

Conexión cliente-servidor asegurada.

Considerar firewalls y seguridad básica.

📊 Diagrama de Gantt (Resumen)
Objetivo	Inicio	Fin	Responsable	Estado
Servidor web	01/03/2025	10/03/2025	Maria / Enrique	⏳ Pendiente
Front-page	11/03/2025	20/03/2025	Jan / Maria / Enrique	⏳ Pendiente
Registro/Login	21/03/2025	25/03/2025	Enrique	⏳ Pendiente
