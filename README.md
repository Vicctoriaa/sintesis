OBJETIVOS
Arquitectura y sistemas
1.        Especificar objetivos y las funcionalidades. [1p]
2.        Especificar listado de tareas. [1p]
3.        Asignar roles y responsabilidades del equipo. [1p]
4.        El diagrama de la red. [1p]
5.        Las tecnologías a implementar. [1p]
6.        El hardware que se va a utilizar. [1p]
7.        Los servicios a implementar. [1p]
8.        Los sistemas operativos a utilizar. [1p]
9.        Establecer un diagrama de Gantt con los objetivos y resultados a alcanzar. [1p]

Objetivos – FASE 1
 
Planificación del proyecto. Definir un calendario detallado con los objetivos, resultados a alcanzar, requisitos técnicos tanto hardware como de software.
 
Nota: Para llevar a cabo esta actividad es recomendable seguir el esquema de Gestión de Proyectos.
 
A modo de resumen:
1.       Especificar objetivos y las funcionalidades.
2.       Especificar listado de tareas.
3.       Asignar roles y responsabilidades del equipo.
4.       El diagrama de la red.
5.       Las tecnologías a implementar.
6.       El hardware que se va a utilizar.
7.       Los servicios a implementar.
8.       Los sistemas operativos .a utilizar.
9.       Establecer un diagrama de Gantt con los objetivos y resultados a alcanzar.
10.   Documentar en GitHub.
 
Funcionalidades
 
Siguiendo la plantilla que tienes a continuación, completa la matriz de requisitos y funcionalidades asignando una prioridad a cada función y una fecha aproximada de entrega. Se todo lo concreto posible.
ID
Prioridad
Objetivo
Funcionalidad
Disparador
Fecha Entrega
Estado
ID0
Media
Registrar usuarios en la página
Deberá crearse un sistema de registro de usuarios y posterior login que guarde información individual del usuario
Un botón en la esquina superior te llevará a la pantalla de registro/login
20/02/2025
Pendiente


 
Donde:
·         ID: número asignado de tarea
·         Prioridad: Prioridad que se le da a la tarea, puede ser Baja, Media o Alta. Ver esquema de Gestión de Proyecto.
·         Requisito: Narrativa de cliente que describe en que consiste el requerimiento de proyecto.
·         Funcionalidad: La funcionalidad de la app que va a cumplir con el objetivo de requisito previamente descrito.
·         Disparador: evento u objeto (gráfico o no) que va a hacer que se realice la función descrita.
·         Fecha: aproximada de entrega
·         Estado: Activo, pendiente o cancelado.
 
Listado de tareas
 
Kanban cuyo significado es letrero o tarjeta en japonés, es una metodología de gestión de proyectos que se centra en la visualización del trabajo, la limitación del trabajo en curso y la mejora continua.
Es una metodología fácil de entender y usar que usaremos para la gestión de tareas. Por eso, estamos utilizando Trello.
 
 
¿Qué tenemos que hacer?
Revisa las funcionalidades de tu proyecto, piensa en como dividir el trabajo de tu proyecto en distintos ítems o tareas fácilmente realizables.
A continuación, deberás plantear cada uno de los objetivos y tareas hasta cumplir este objetivo. Por cada tarea deberás asignar un integrante del proyecto que va a realizar esa tarea, más adelante asignaremos fechas concretas.
Utiliza el Trello para plantear cada uno de los objetivos y tareas. Recuerda que cada tarea se convertirá en una tarjeta de Trello que se irá revisando durante la fase de producción.
A continuación, tienes un ejemplo de cómo hacerlo:
Objetivo 1: Implementar un servidor web
1.1
[Maria] Instalación y configuración básica del servidor
CP1.2 – Se ha instalado y configurado un sistema operativo en red
1.2
[Enrique] Configurar la política de usuarios y privilegios
CP1.2 – Se ha instalado y configurado un sistema operativo en red
1.3
[Enrique] Instalación y configuración de los servicios web NGINX, MariaDB, PHP8.2, PHPMYADMIN.
CP3.1.1 – Se configura y se garantiza el funcionamiento de un servicio de servidor web

 
Objetivo 2: Programar la front-page
2.1
[Jan] Crear la estructura del index.html con CSS
CP2.1.6 – Los ficheros de lenguaje de marcas empleados tienen un código correcto y adecuado, transmiten al usuario la información correctamente y ofrecen una buena experiencia de usuario a nivel gráfico.
2.2
[Maria] Crear el header y el footer comunes de todas las páginas
CP2.1.6 – Los ficheros de lenguaje de marcas empleados tienen un código correcto y adecuado, transmiten al usuario la información correctamente y ofrecen una buena experiencia de usuario a nivel gráfico.
2.3
[Enrique] Programar el formulario de contacto de la frontpage
CP2.1.6 – Los ficheros de lenguaje de marcas empleados tienen un código correcto y adecuado, transmiten al usuario la información correctamente y ofrecen una buena experiencia de usuario a nivel gráfico.

 
Arquitectura del sistema
 
Uno de los fundamentos de arquitectura es la identificación de componentes: esto se refiere a determinar las piezas clave o módulos que compondrán una aplicación web. Cada componente realiza funciones específicas y se integra con otros para lograr el conjunto completo de características y servicios requeridos por la aplicación.
La arquitectura obligatoriamente será cliente-servidor, pero debes tener en cuenta los requerimientos técnicos para realizar el trabajo. Identifica el software, la versión a utilizar, el puerto de funcionamiento y el dominio si así lo requiera y explica brevemente para que se va a utilizar esa tecnología.
Componente de sistema
Tecnología o framework
 (elige de la lista o añade el que vayas a utilizar)
Versión
Puerto
Descripción de uso o requisitos
Enlace a documentación o información adicional
Hardware
Modelo, procesador, RAM, espacio en disco, adaptadores de red
 
no
 
 
Sistema operativo
¿Qué SO? ¿libre o propietario?
 
no
 
 
Interfaz de usuario (Frontend)
HTML, CSS, JavaScript, bibliotecas y frameworks como React, Angular o Vue.js.
 
 
 
 
Lógica de negocio (Backend)
Lenguajes de programación como PHP, Python, Java, Node.js, frameworks como Django, Flask, Spring (Java), Express (Node.js).
 
 
 
 
Servidor web
Apache, Nginx, Microsoft IIS.
 
 
 
 
Base de datos
MySQL, PostgreSQL, MongoDB, Firebase, SQLite.
 
 
 
 
Sistema gestor de base de datos
MySQLWorkbench, PHPMyAdmin, Access, Oracle SQL, MongoDB Atlas.
 
 
Servicios de APIs
REST, GraphQL, SOAP o APIs concretas
 
 
Diagrama de la base de datos
 
Si tu proyecto requiere de una DB tienes que plasmar el diagrama entidad-relación de la misma
 
Realiza el diagrama entidad-relación de la DB de tu aplicación web. Recuerda pensar en:
·         ¿Qué datos son necesarios para mi aplicación?
·         ¿Qué datos voy a pedir al usuario y que tipos de usuarios voy a tener?
·         ¿Qué tipo de dato necesitaré para cada información? (Aquí tienes la documentación oficial de MySQL)
·         ¿Qué clave primaria voy a implantar en cada tabla? ¿Cómo las relacionaré entre ellas?
 
Nota: Para el diagrama puedes usar cualquier herramienta gráfica como draw.io, Microsoft Visio o Lucidchart.

 
estructura básica de la red
 
Diseña el diagrama de la red de tu proyecto.
