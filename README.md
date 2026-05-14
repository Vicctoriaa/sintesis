# Memoria Final

**Autores:** Juan Victoria Víctor  
**Curso:** 2025–2026  
**Fecha:** Mayo 2026  

---

## Índice

1. [Resumen](#1-resumen)
2. [Introducción](#2-introducción)
3. [Objetivos](#3-objetivos)
4. [Marco teórico](#4-marco-teórico)
5. [Análisis de requisitos](#5-análisis-de-requisitos)
6. [Diseño de la arquitectura](#6-diseño-de-la-arquitectura)
7. [Implementación](#7-implementación)
   - 7.1 [Proxmox VE — Hipervisor](#71-proxmox-ve--hipervisor)
   - 7.2 [Segmentación de red con OpenWRT](#72-segmentación-de-red-con-openwrt)
   - 7.3 [DNS interno — Bind9](#73-dns-interno--bind9)
   - 7.4 [SIEM — Wazuh](#74-siem--wazuh)
   - 7.5 [IDS — Suricata](#75-ids--suricata)
   - 7.6 [Monitorización — Prometheus y Grafana](#76-monitorización--prometheus-y-grafana)
   - 7.7 [Automatización — Ansible y Playbooks](#77-automatización--ansible-y-playbooks)
   - 7.8 [Honeypot personalizado — HoneyCos](#78-honeypot-personalizado--honeycos)
   - 7.9 [Servicios de soporte](#79-servicios-de-soporte)
   - 7.10 [Hardening](#710-hardening)
   - 7.11 [Sistema de backups](#711-sistema-de-backups)
8. [Conclusiones](#8-conclusiones)
9. [Trabajo futuro](#9-trabajo-futuro)
10. [Anexos](#10-anexos)

---

## 1. Resumen

### Español

El presente proyecto de síntesis describe el diseño, implementación y validación de un entorno SOC (Security Operations Center) funcional construido íntegramente sobre infraestructura virtualizada con Proxmox VE. El laboratorio replica una arquitectura empresarial real segmentada mediante VLANs gestionadas por un firewall OpenWRT, e integra las principales herramientas de la cadena de detección y respuesta ante incidentes: un SIEM basado en Wazuh, un sistema de detección de intrusiones con Suricata, monitorización de infraestructura con Prometheus y Grafana, automatización de tareas de respuesta con Ansible, y un honeypot de producción desarrollado desde cero en Python.

El resultado es un entorno operativo capaz de centralizar logs y alertas, detectar amenazas en tiempo real, ejecutar respuestas automáticas ante incidentes y registrar actividad maliciosa sobre servicios señuelo.

---

## 2. Introducción

La ciberseguridad se ha convertido en una disciplina crítica para cualquier organización que opere con sistemas informáticos. El incremento sostenido de ataques dirigidos, ransomware, explotación de servicios expuestos y movimiento lateral dentro de redes corporativas pone de manifiesto la necesidad de contar no solo con medidas preventivas, sino con capacidad real de detección, análisis y respuesta ante incidentes.

Un SOC (Security Operations Center) es la estructura organizativa y técnica desde la que se centraliza esta capacidad defensiva. Agrupa herramientas de monitorización, correlación de eventos, detección de anomalías y respuesta coordinada, permitiendo a los equipos de seguridad tener visibilidad completa sobre el estado de la infraestructura y reaccionar de forma eficaz ante cualquier amenaza.

Sin embargo, el acceso a entornos SOC reales con fines formativos es limitado. La mayor parte de la industria opera sobre soluciones comerciales de coste elevado, y los laboratorios de práctica disponibles suelen ser entornos simplificados que no reflejan la complejidad de una infraestructura real.

Este proyecto surge con el objetivo de cerrar esa brecha: construir desde cero, sobre hardware convencional y herramientas de código abierto, un entorno SOC completamente funcional que reproduzca los componentes, la arquitectura y los flujos de trabajo de un despliegue empresarial real. El entorno no se limita a la instalación de herramientas; incluye el diseño de la red, la segmentación de tráfico por VLANs, la integración entre componentes, la automatización de respuestas y el desarrollo de un honeypot propio que actúa como cebo para atacantes reales.

---

## 3. Objetivos

### Objetivo general

Diseñar e implementar un entorno SOC funcional virtualizado, capaz de monitorizar, detectar y gestionar eventos de seguridad en una infraestructura segmentada, integrando herramientas de código abierto en un flujo de trabajo coherente y automatizado.

### Objetivos específicos

**Infraestructura y virtualización**
- Desplegar un hipervisor Proxmox VE como base del entorno, gestionando contenedores LXC y máquinas virtuales de forma eficiente.
- Implementar un sistema de almacenamiento ZFS en espejo para garantizar la integridad de los datos.
- Diseñar una arquitectura de red virtualizada con segmentación por VLANs representativa de un entorno empresarial real.

**Red y seguridad perimetral**
- Configurar OpenWRT como firewall y router inter-VLAN con políticas de acceso diferenciadas por zona de red.
- Aislar completamente la VLAN del honeypot del resto de la infraestructura para prevenir movimiento lateral.
- Implementar un servidor DNS interno Bind9 con resolución de nombres para todos los servicios del laboratorio.

**Detección y correlación**
- Desplegar Wazuh como SIEM centralizado, con agentes en todos los nodos del entorno.
- Desarrollar reglas de detección personalizadas para los eventos del honeypot y de Suricata.
- Integrar Suricata como motor IDS con análisis de tráfico en tiempo real.

**Monitorización**
- Implementar Prometheus para la recolección de métricas de todos los nodos del entorno.
- Configurar Grafana con dashboards que ofrezcan visibilidad en tiempo real sobre el estado de la infraestructura y la actividad de seguridad.

**Automatización y respuesta**
- Implementar playbooks Ansible de respuesta ante incidentes: bloqueo de IPs, aislamiento de hosts, recolección de evidencias y actualización de sistemas.
- Integrar la respuesta automática con el SIEM mediante el mecanismo de Active Response de Wazuh.

**Honeypot**
- Desarrollar un honeypot propio en Python que simule múltiples servicios vulnerables (SSH, FTP, HTTP, HTTPS, SMB, RDP).
- Integrar el honeypot con el SIEM y con el sistema de monitorización.
- Desarrollar un dashboard web dedicado para la visualización de la actividad capturada por el honeypot.

**Servicios de soporte**
- Desplegar servicios de soporte empresarial: gestión de contraseñas (Vaultwarden), directorio de usuarios (OpenLDAP), proxy inverso (Nginx), correo de alertas (Postfix) y VPN de acceso remoto (Tailscale).
- Crear una web corporativa real bajo el dominio `honeycos.com` expuesta a Internet mediante Cloudflare Tunnel.

---

## 4. Marco teórico

### 4.1 Virtualización

La virtualización es la tecnología que permite ejecutar múltiples sistemas operativos de forma aislada sobre un mismo hardware físico mediante software denominado hipervisor. Existen dos tipos principales: los hipervisores de tipo 1 (bare-metal), que se ejecutan directamente sobre el hardware sin sistema operativo anfitrión, y los de tipo 2 (hosted), que corren como aplicaciones sobre un sistema operativo existente. Para entornos de producción y laboratorios técnicos se utilizan preferentemente los de tipo 1 por su rendimiento y estabilidad.

**Proxmox VE** es un hipervisor de tipo 1 de código abierto basado en Debian y KVM. Permite gestionar tanto máquinas virtuales completas como contenedores LXC (Linux Containers), que comparten el kernel del anfitrión y ofrecen un consumo de recursos significativamente inferior al de las VMs convencionales. Esta capacidad de combinar ambos tipos de virtualización lo convierte en una plataforma ideal para laboratorios donde coexisten servicios ligeros (contenedores) con sistemas que requieren aislamiento completo de kernel (VMs para el honeypot, el SIEM o el firewall).

### 4.2 SOC y defensa en profundidad

Un SOC (Security Operations Center) es el conjunto de personas, procesos y tecnologías responsables de la monitorización continua de la seguridad de una organización. Su función principal es detectar, analizar y responder a incidentes de ciberseguridad de forma estructurada. El modelo de defensa en profundidad que sustentan los SOC modernos se basa en la idea de que ninguna medida de seguridad individual es suficiente: la seguridad debe aplicarse en múltiples capas (red, sistema, aplicación, datos) de forma que el compromiso de una capa no implique el compromiso total del entorno.

Los SOC actuales operan bajo marcos de referencia como MITRE ATT&CK, que cataloga las tácticas y técnicas empleadas por los atacantes, y los frameworks NIST o ISO 27001, que establecen procesos de gestión de la seguridad de la información.

### 4.3 SIEM

Un SIEM (Security Information and Event Management) es la plataforma central del SOC. Su función es recopilar logs de múltiples fuentes (sistemas operativos, aplicaciones, dispositivos de red, soluciones de seguridad), normalizarlos, correlacionarlos y generar alertas cuando detecta patrones de comportamiento anómalo o malicioso.

**Wazuh** es una plataforma SIEM de código abierto que combina detección de intrusiones basada en host (HIDS), monitorización de integridad de ficheros (FIM), análisis de vulnerabilidades, cumplimiento normativo y respuesta activa. Su arquitectura cliente-servidor, con un manager centralizado y agentes ligeros desplegados en cada nodo, lo hace especialmente adecuado para entornos distribuidos. En comparación con alternativas comerciales como Splunk o IBM QRadar, Wazuh ofrece una funcionalidad comparable con un coste de despliegue prácticamente nulo, siendo la opción más extendida en entornos formativos y organizaciones con presupuesto limitado.

### 4.4 IDS/IPS

Un IDS (Intrusion Detection System) analiza el tráfico de red en busca de patrones que coincidan con firmas de ataques conocidos o que presenten anomalías respecto al comportamiento esperado. Cuando detecta una amenaza, genera una alerta. Un IPS (Intrusion Prevention System) añade la capacidad de bloquear activamente el tráfico malicioso.

**Suricata** es el motor IDS/IPS de código abierto más avanzado disponible en la actualidad. Desarrollado por la OISF (Open Information Security Foundation), soporta inspección en múltiples hilos de ejecución (multithreading), análisis de protocolos de capa de aplicación (HTTP, DNS, TLS, SMB, etc.) y generación de eventos en formato JSON mediante el log `eve.json`. Este formato estructurado facilita la integración con SIEM y otras herramientas del stack de seguridad. Frente a alternativas como Snort, Suricata destaca por su rendimiento en entornos de alto tráfico y su mayor capacidad de análisis de protocolos.

### 4.5 Monitorización de infraestructura

La monitorización de infraestructura permite conocer en tiempo real el estado de los sistemas: uso de CPU, memoria, disco, tráfico de red, disponibilidad de servicios, etc. Esta información es esencial tanto para la operación normal del entorno como para la detección de anomalías que puedan indicar un compromiso.

**Prometheus** es un sistema de monitorización y alertas de código abierto desarrollado originalmente por SoundCloud y actualmente bajo la CNCF (Cloud Native Computing Foundation). Opera mediante un modelo de recolección pull: consulta periódicamente endpoints HTTP expuestos por los nodos monitorizados (exporters) y almacena las métricas en su base de datos de series temporales. El exporter más utilizado es Node Exporter, que expone métricas del sistema operativo de cada nodo.

**Grafana** es la herramienta de visualización más extendida para datos de Prometheus. Permite construir dashboards interactivos con múltiples tipos de gráficos, paneles de estado y alertas visuales, convirtiéndose en la capa de presentación estándar del stack Prometheus-Grafana.

### 4.6 Automatización de respuesta

La automatización de la respuesta ante incidentes reduce el tiempo de reacción y minimiza el error humano en las acciones de contención. Las herramientas SOAR (Security Orchestration, Automation and Response) permiten definir flujos de trabajo (playbooks) que se ejecutan automáticamente cuando se detecta un incidente.

**Ansible** es una herramienta de automatización de infraestructura de código abierto desarrollada por Red Hat. Opera de forma agentless (sin agentes instalados en los nodos), ejecutando sus tareas mediante SSH. Su modelo declarativo, basado en ficheros YAML denominados playbooks, permite definir con precisión las acciones a ejecutar sobre uno o varios nodos de forma reproducible y auditable.

### 4.7 Honeypots

Un honeypot es un sistema o servicio diseñado deliberadamente para parecer vulnerable y atractivo para los atacantes, con el objetivo de detectar, estudiar y registrar sus técnicas sin poner en riesgo la infraestructura real. Los honeypots se clasifican según su nivel de interacción:

- **Baja interacción:** simulan servicios de forma superficial, registrando solo las conexiones y los primeros intentos de acceso. Son más seguros pero ofrecen menos información.
- **Alta interacción:** ofrecen servicios reales o casi reales, permitiendo al atacante interactuar con ellos y revelando así técnicas más avanzadas. Requieren mayor aislamiento.

En el contexto SOC, los honeypots tienen un valor defensivo doble: permiten detectar exploraciones y ataques que aún no han alcanzado sistemas reales, y generan inteligencia sobre las técnicas de los atacantes que puede usarse para mejorar las reglas de detección del SIEM.

---

## 5. Análisis de requisitos

### 5.1 Requisitos funcionales

**Detección y correlación**
- El sistema debe centralizar logs de todos los nodos del entorno en un único punto de análisis.
- El SIEM debe generar alertas diferenciadas según la gravedad del evento, con niveles que permitan priorizar la respuesta.
- El IDS debe analizar el tráfico de red en tiempo real y enviar sus eventos al SIEM.
- El sistema debe ser capaz de detectar intentos de acceso no autorizados, ejecución de comandos en el honeypot y actividad de fuerza bruta.

**Respuesta automática**
- Ante alertas de alta gravedad, el sistema debe ejecutar automáticamente acciones de contención: bloqueo de IPs maliciosas en el IDS, aislamiento de VLANs comprometidas y recolección de evidencias.
- Las respuestas automáticas deben quedar registradas en un log de incidentes auditable.

**Monitorización**
- El sistema debe monitorizar el estado de todos los nodos (CPU, memoria, disco, red) con una frecuencia mínima de 15 segundos.
- Debe existir un dashboard centralizado con visibilidad en tiempo real sobre toda la infraestructura.
- El honeypot debe tener su propio dashboard con métricas de actividad.

**Honeypot**
- El honeypot debe simular al menos cuatro servicios distintos de forma simultánea.
- Todos los eventos capturados deben enviarse al SIEM y al dashboard en tiempo real.
- El honeypot debe estar completamente aislado de la infraestructura de producción.

**Servicios de soporte**
- El entorno debe disponer de resolución DNS interna para todos sus servicios.
- Debe existir un sistema centralizado de envío de alertas por correo electrónico.
- El acceso a los servicios web debe gestionarse a través de un proxy inverso con autenticación.

### 5.2 Requisitos no funcionales

**Seguridad**
- Cada VLAN debe operar como zona de confianza independiente, con acceso inter-VLAN controlado por reglas de firewall explícitas.
- El honeypot debe residir en una VLAN completamente aislada, sin capacidad de acceso a otras VLANs salvo para el envío de logs al SIEM.
- El acceso SSH a todos los nodos debe realizarse mediante clave pública, sin autenticación por contraseña.
- El puerto SSH debe desplazarse del estándar (22) para reducir la superficie de ataque frente a scanners automatizados.

**Disponibilidad**
- Todos los servicios críticos deben estar configurados para reiniciarse automáticamente ante fallos (systemd restart policy).
- Los backups deben ejecutarse de forma automática y diaria, con retención de al menos dos copias por nodo.

**Escalabilidad**
- La arquitectura de red debe permitir añadir nuevos nodos sin modificar las reglas de firewall existentes.
- El sistema de monitorización debe poder incorporar nuevos exporters sin necesidad de reiniciar el stack.

**Eficiencia de recursos**
- El entorno completo debe poder operar sobre hardware convencional de consumidor (procesador de cuatro núcleos, 16 GB de RAM).
- Los contenedores LXC deben preferirse frente a VMs completas siempre que el servicio lo permita.

---

## 6. Diseño de la arquitectura

### 6.1 Infraestructura física

El entorno completo se despliega sobre un único nodo físico denominado **honeycos**, con las siguientes características:

| Componente | Especificación |
|-----------|---------------|
| CPU | Intel Core i5-3470 @ 3.20 GHz (4 cores) |
| RAM | 16 GB |
| Almacenamiento | ZFS mirror (RAID-1) sobre dos discos de 500 GB |
| Sistema operativo | Proxmox VE 9.1.1 (Debian 13 Trixie) |
| Kernel | 6.17.2-1-pve |
| IP de gestión | 192.168.3.200/24 |

El almacenamiento ZFS en modo espejo garantiza que el fallo de uno de los discos no implique pérdida de datos, proporcionando una capa de alta disponibilidad del almacenamiento sin coste adicional de hardware.

### 6.2 Segmentación de red — VLANs

La red interna del laboratorio se segmenta en cinco VLANs con funciones bien diferenciadas, enrutadas a través de OpenWRT (VM 201) que actúa como firewall y router inter-VLAN. Todo el tráfico interno viaja sobre el bridge `vmbr1` configurado en modo VLAN-aware, lo que permite que un único bridge físico transporte el tráfico de todas las VLANs con el etiquetado IEEE 802.1Q correspondiente.

| VLAN | Nombre | Subred | Gateway | Función |
|------|--------|--------|---------|---------|
| 10 | DMZ | 10.1.1.0/27 | 10.1.1.1 | Zona desmilitarizada |
| 20 | Servicios | 10.1.1.32/27 | 10.1.1.33 | Servicios de infraestructura |
| 30 | SOC | 10.1.1.64/27 | 10.1.1.65 | Herramientas de seguridad |
| 40 | Producción | 10.1.1.96/27 | 10.1.1.97 | Servicios de producción (LDAP) |
| 50 | Honeypot | 10.1.1.128/27 | 10.1.1.129 | Honeypot aislado |

### 6.3 Topología de red

```
Internet
    │
    ▼
Router doméstico (192.168.3.1)
    │
    ▼
honeycos — vmbr0 (192.168.3.200)  ← gestión y NAT
    │
    ▼
OpenWRT VM-201 (192.168.3.201)
    │
    ├── VLAN 10 — DMZ        (10.1.1.0/27)
    ├── VLAN 20 — Servicios  (10.1.1.32/27)
    │     ├── CT103 DNS       (10.1.1.34)
    │     ├── CT105 Nginx     (10.1.1.35)
    │     ├── CT104 SOAR      (10.1.1.37)
    │     ├── CT106 Suricata  (10.1.1.36)
    │     └── CT108 Postfix   (10.1.1.53)
    ├── VLAN 30 — SOC        (10.1.1.64/27)
    │     ├── CT101 Grafana+Prometheus (10.1.1.66)
    │     ├── VM202 Wazuh             (10.1.1.67)
    │     ├── CT107 Homepage          (10.1.1.68)
    │     ├── CT109 Honeypot-dash     (10.1.1.69)
    │     └── CT102 Vaultwarden       (10.1.1.80)
    ├── VLAN 40 — Producción (10.1.1.96/27)
    │     └── CT100 LDAP     (10.1.1.98)
    └── VLAN 50 — Honeypot   (10.1.1.128/27)  [AISLADA]
          └── VM203 Honeypot (10.1.1.130)
```

### 6.4 Política de firewall inter-VLAN

El principio rector del diseño de firewall es el de mínimo privilegio: cada VLAN solo puede comunicarse con las VLANs y puertos estrictamente necesarios para su función. La VLAN 50 (Honeypot) es la más restrictiva: está completamente aislada por defecto, con únicamente tres reglas de excepción explícitas:

- Permite el envío de logs al agente Wazuh en VLAN 30 (puertos 1514/1515).
- Permite que Prometheus scrape las métricas del honeypot (puerto 9100).
- Permite que el honeypot envíe eventos a la API del dashboard en VLAN 30 (puerto 5000).

Ningún tráfico originado en VLAN 50 puede alcanzar otras VLANs salvo por estas tres excepciones. Esto garantiza que un atacante que comprometa el honeypot no pueda moverse lateralmente hacia la infraestructura real.

### 6.5 Inventario de nodos

| ID | Tipo | Nombre | IP | VLAN | Servicio principal |
|----|------|--------|----|------|-------------------|
| VM 201 | VM | openwrt-fw | 192.168.3.201 | — | Firewall / Router |
| VM 202 | VM | wazuh-siem | 10.1.1.67 | 30 | SIEM Wazuh 4.14.4 |
| VM 203 | VM | honeypot | 10.1.1.130 | 50 | Honeypot Python |
| CT 100 | LXC | ldap | 10.1.1.98 | 40 | OpenLDAP |
| CT 101 | LXC | grafana-prometheus | 10.1.1.66 | 30 | Grafana + Prometheus |
| CT 102 | LXC | vaultwarden | 10.1.1.80 | 30 | Vaultwarden |
| CT 103 | LXC | playbooks-dns | 10.1.1.34 | 20 | Bind9 + Ansible |
| CT 104 | LXC | soar-web | 10.1.1.37 | 20 | Plataforma SOAR |
| CT 105 | LXC | nginx-proxy | 10.1.1.35 | 20 | Proxy inverso Nginx |
| CT 106 | LXC | suricata-ids | 10.1.1.36 | 20 | IDS Suricata |
| CT 107 | LXC | homepage | 10.1.1.68 | 30 | Dashboard Homepage |
| CT 108 | LXC | correo | 10.1.1.53 | 20 | Relay SMTP Postfix |
| CT 109 | LXC | honeypot-dashboard | 10.1.1.69 | 30 | Dashboard honeypot |
| CT 200 | LXC | vpn-server | 192.168.3.250 | WAN | VPN Tailscale |

### 6.6 Flujo de eventos SOC

```
Evento en cualquier nodo
        │
        ▼
Agente Wazuh (en el nodo)
        │
        ▼
Wazuh Manager — VM202
        │
        ├── Regla dispara alerta de nivel alto
        │         │
        │         ▼
        │   Active Response → soc-trigger.sh en CT103
        │         │
        │         ▼
        │   Ansible playbook ejecutado
        │
        └── Dashboard Wazuh (https://192.168.3.200)

Suricata — CT106
        │ eve.json
        ├── Wazuh Agent → Wazuh Manager
        └── eve-watcher.py → SSH CT103 → Ansible playbook
```

---

## 7. Implementación

### 7.1 Proxmox VE — Hipervisor

Proxmox VE se instaló sobre el nodo físico `honeycos` como sistema operativo principal. La instalación se realizó desde imagen ISO oficial, configurando el almacenamiento en dos pools ZFS diferenciados: `local` para las imágenes de backup generadas por vzdump, y `local-zfs` como pool ZFS nativo donde residen los discos de todos los contenedores y máquinas virtuales.

El almacenamiento ZFS opera en modo mirror (RAID-1 software) sobre dos discos de 500 GB, con un tamaño de pool disponible de 460 GB y una ocupación del 30% al final del proyecto. El último scrub realizado no reportó errores, confirmando la integridad de los datos.

**Red en Proxmox.** Se configuraron dos bridges:
- `vmbr0` como bridge estándar conectado a la interfaz física, asignándole la IP de gestión `192.168.3.200/24`. Por él entra y sale el tráfico hacia Internet y la red doméstica.
- `vmbr1` como bridge VLAN-aware sin IP asignada y sin puertos físicos. Actúa como trunk virtual que transporta el tráfico etiquetado de las cinco VLANs hacia OpenWRT y entre los contenedores.

El NAT entre la red interna y el exterior se gestiona mediante reglas iptables persistidas con `netfilter-persistent`, que redirigen puertos específicos desde `vmbr0` hacia los servicios correspondientes en la red interna.

La elección de Proxmox frente a otras alternativas como VMware ESXi (de pago tras la adquisición por Broadcom) o VirtualBox (sin soporte empresarial nativo de LXC) se justifica por su coste cero, su capacidad de gestionar LXC y KVM de forma unificada, y su interfaz web completa para la administración del entorno.

### 7.2 Segmentación de red con OpenWRT

OpenWRT se desplegó como máquina virtual (VM 201) sobre Proxmox, actuando como firewall y router inter-VLAN para toda la infraestructura interna. Se eligió OpenWRT por su flexibilidad de configuración, su sistema UCI (Unified Configuration Interface) que permite gestionar toda la configuración mediante comandos o edición directa de ficheros, y su bajo consumo de recursos (128 MB de RAM para gestionar cinco VLANs con quince nodos).

La configuración de red de OpenWRT define dos interfaces físicas: `eth0` conectada a `vmbr0` para el tráfico WAN, y `eth1` conectada a `vmbr1` como trunk que transporta las cinco VLANs etiquetadas. Cada VLAN se presenta como una subinterfaz (`eth1.10` a `eth1.50`) con su propia dirección IP, que actúa como gateway para los nodos de esa VLAN.

**Política de firewall.** La política global establece que todo tráfico de entrada y reenvío está rechazado por defecto, y solo el tráfico de salida se permite libremente. Sobre esta base se definen las excepciones explícitas necesarias para el funcionamiento del entorno.

La VLAN 50 (Honeypot) merece mención especial: tanto su política de entrada como la de salida y reenvío están configuradas como REJECT. Esto significa que el honeypot no puede iniciar ninguna conexión hacia otras VLANs ni recibirlas salvo por las tres reglas explícitas descritas en la sección de diseño. Este aislamiento es la principal medida de contención que previene que un atacante que comprometa el honeypot pueda pivotar hacia la infraestructura real.

El acceso desde la red de gestión (`192.168.3.0/24`) a todos los puertos de servicios del SOC se gestiona mediante una única regla amplia que permite el tráfico administrativo desde el rango completo, mientras que el acceso SSH de gestión al honeypot se controla mediante una regla dedicada que lo limita exclusivamente al nodo `honeycos` (192.168.3.200).

### 7.3 DNS interno — Bind9

El servicio DNS interno (CT 103) resuelve los nombres de todos los servicios del laboratorio bajo la zona `soc.local`, eliminando la necesidad de usar IPs en las configuraciones de los distintos componentes y facilitando el mantenimiento del entorno.

Bind9 opera como servidor maestro autoritativo para dos zonas: la zona directa `soc.local` (resolución nombre → IP) y la zona inversa `1.1.10.in-addr.arpa` (resolución IP → nombre). Para las consultas externas actúa como forwarder hacia los resolvers públicos de Google (8.8.8.8) y Cloudflare (1.1.1.1).

La configuración restringe la recursión a la red interna `10.1.1.0/24`, evitando que el servidor pueda ser utilizado como open resolver desde el exterior. El canal de estadísticas interno en el puerto 8080 es consumido por el `bind_exporter`, que expone las métricas DNS en formato Prometheus para su visualización en Grafana.

CT103 tiene además un rol fundamental en el sistema de automatización: al ser el nodo ejecutor de Ansible, concentra tanto la resolución DNS del entorno como la capacidad de actuar sobre cualquier nodo mediante playbooks. Esta decisión de diseño simplifica la arquitectura de respuesta automática, ya que el SIEM solo necesita comunicarse con un único punto de ejecución.

### 7.4 SIEM — Wazuh

Wazuh se desplegó sobre la VM 202 con 6 GB de RAM y 50 GB de disco, siendo el componente más exigente en recursos del entorno. Se optó por una instalación all-in-one que concentra el indexer (OpenSearch), el manager y el dashboard en una única VM, apropiado para la escala de este laboratorio.

**Agentes desplegados.** Se instaló el agente Wazuh en ocho nodos del entorno, cubriendo las VLANs 20, 30, 40 y 50. El honeypot (VM 203) dispone de su propio agente, lo que permite que todos sus eventos lleguen directamente al SIEM. CT103 actúa como agente especial: además de reportar sus propios eventos, es el nodo designado para recibir las órdenes de Active Response del manager y ejecutar los playbooks Ansible.

**Reglas personalizadas.** Se desarrollaron dos grupos de reglas propias:

El primer grupo (IDs 100500–100508) procesa los eventos del honeypot. Define ocho reglas de granularidad creciente que distinguen entre conexiones genéricas (nivel 3), intentos de login (nivel 8), comandos ejecutados en el honeypot (nivel 10), accesos a rutas sensibles vía HTTP (nivel 10), fuerza bruta (nivel 14) y eventos críticos (nivel 12). Las reglas de nivel 12 o superior disparan el envío de alertas por correo electrónico.

El segundo grupo (IDs 100600–100601) extiende las reglas nativas de Wazuh para Suricata, elevando el nivel de las alertas según la severidad del evento IDS: nivel 12 para alertas críticas (severidad 1) y nivel 10 para alertas de alta gravedad (severidad 2).

**Active Response — soc-trigger.sh.** El mecanismo de respuesta automática de Wazuh se configura para ejecutar el script `soc-trigger.sh` en el agente CT103 cuando saltan reglas específicas. El script analiza el JSON del evento (regla disparada, IP de origen, agente afectado) y decide qué playbook Ansible lanzar: `block-ip.yml` para bloquear IPs maliciosas, `isolate-host.yml` para aislar VLANs comprometidas, `collect-evidence.yml` para recopilar evidencias forenses, `fail2ban.yml` para gestionar la respuesta a fuerza bruta SSH, y `backup-configs.yml` cuando se detecta modificación de ficheros críticos.

**Notificaciones por correo.** Wazuh se configuró para enviar alertas por email a través del relay Postfix de CT108, con un umbral de nivel 12 para notificaciones globales y reglas específicas adicionales para los eventos más relevantes del honeypot y Suricata.

**Listas CDB.** Se creó la estructura de listas de indicadores de compromiso (IOCs) en `/var/ossec/etc/lists/malicious-ioc/`, con ficheros para hashes de malware, IPs maliciosas y dominios maliciosos conocidos, pendientes de poblar con feeds de inteligencia de amenazas reales.

### 7.5 IDS — Suricata

Suricata se desplegó en CT106, contenedor privilegiado con 2 cores y 1 GB de RAM para soportar la carga del análisis de paquetes en tiempo real. El modo privilegiado es necesario para que Suricata pueda acceder directamente a las interfaces de red del host.

Suricata opera en modo IDS pasivo, analizando el tráfico que atraviesa la interfaz de red del contenedor y escribiendo los eventos en formato JSON en el fichero `eve.json`. Este fichero es el punto de integración con el resto del stack: el agente Wazuh lo monitoriza y reenvía los eventos al manager, y el proceso `eve-watcher.py` lo observa en tiempo real para disparar respuestas automáticas ante alertas de alta gravedad.

**eve-watcher.py.** Este proceso Python desarrollado para el proyecto monitoriza `eve.json` en tiempo real (equivalente a un `tail -f`) y aplica una lógica de clasificación sobre cada alerta recibida. Según la combinación de severidad de la alerta, firma detectada y origen de la IP (externa vs. interna), decide qué playbook Ansible ejecutar en CT103 via SSH. Un mecanismo de cooldown de 5 minutos por IP evita la ejecución repetida del mismo playbook ante floods de alertas sobre la misma fuente.

Las IPs bloqueadas por el SOC se añaden automáticamente como reglas `drop` en el fichero `local.rules` de Suricata, que puede recargarse en caliente sin reiniciar el motor mediante `suricatasc -c reload-rules`.

El `suricata_exporter` instalado en CT106 expone métricas del IDS en el puerto 9917, incluyendo el número de alertas por firma, el tráfico analizado y el rendimiento del motor, visualizables en el dashboard de Grafana dedicado al IDS.

### 7.6 Monitorización — Prometheus y Grafana

El stack de monitorización se concentra en CT101, que aloja Prometheus como servicio systemd y Grafana en Docker, compartiendo la misma IP `10.1.1.66`.

**Prometheus** recolecta métricas de once nodos del entorno mediante el job `node_exporter` (que cubre todos los CTs y VMs), un job `bind_exporter` para el servidor DNS y un job `suricata_exporter` para el IDS. Con un intervalo de scraping de 15 segundos, Prometheus almacena el estado histórico de toda la infraestructura, permitiendo identificar tendencias de consumo de recursos, detectar anomalías y correlacionar eventos de seguridad con el comportamiento del sistema.

La decisión de ejecutar Prometheus como binario systemd en lugar de en Docker se tomó para garantizar una mayor estabilidad ante reinicios y evitar la dependencia del daemon Docker para el componente más crítico del stack de monitorización. Grafana, al ser más tolerante a reinicios y beneficiarse de la gestión de imágenes Docker, sí se despliega en contenedor.

**Grafana** se conecta a Prometheus como datasource predeterminado y ofrece cuatro dashboards principales:

- **Node Exporter Full** (UID 1860): CPU, RAM, disco y red de todos los nodos del entorno en una única vista comparativa.
- **Bind9 Exporter DNS**: queries DNS procesadas, respuestas NXDOMAIN (indicadores de configuración incorrecta o reconocimiento) y latencia de resolución.
- **Suricata IDS — SOC honeycos**: alertas del IDS por firma, tráfico analizado, distribución de protocolos y memoria del motor.
- **Honeypot VM203**: métricas de sistema del honeypot con contexto de la actividad de atacantes (conexiones activas, tráfico de red, uptime).

El acceso a Grafana desde la red de gestión se realiza a través del proxy inverso Nginx en CT105, que también gestiona el WebSocket necesario para las actualizaciones en tiempo real de los dashboards (Grafana Live).

### 7.7 Automatización — Ansible y Playbooks

CT103 actúa como nodo central de automatización del entorno, concentrando tanto el servidor DNS Bind9 como el ejecutor Ansible. Esta decisión concentra en un único contenedor el rol de infraestructura y el de respuesta, simplificando el modelo de comunicación del sistema de Active Response.

Los playbooks desarrollados cubren los principales escenarios de respuesta ante incidentes:

**block-ip.yml** — Bloqueo de IPs maliciosas. Recibe la IP a bloquear como variable y añade una regla `drop` en Suricata, actualiza las listas CDB de Wazuh con la nueva IP y registra la acción en el log de incidentes.

**isolate-host.yml** — Aislamiento de VLANs. Recibe el nombre de la VLAN a aislar como variable y aplica reglas en OpenWRT para bloquear todo el tráfico de entrada y salida de esa VLAN, efectivamente desconectando los hosts comprometidos del resto de la red sin apagarlos.

**collect-evidence.yml** — Recolección de evidencias. Se ejecuta sobre el nodo afectado para recopilar logs del sistema, lista de conexiones activas, procesos en ejecución, ficheros modificados recientemente y volcado de memoria de procesos sospechosos. Las evidencias se comprimen y almacenan en CT103 con marca de tiempo.

**fail2ban.yml** — Gestión de fuerza bruta. Verifica el estado de Fail2ban en el nodo afectado, aplica el bloqueo de la IP agresora si no está ya bloqueado y actualiza el umbral de intentos si se detecta una campaña sostenida.

**backup-configs.yml** — Backup de configuraciones. Se ejecuta tras la detección de modificaciones en ficheros críticos, realizando una copia de los ficheros de configuración relevantes antes de cualquier acción de restauración.

**update-all.yml** — Actualización de sistemas. Aplica actualizaciones de seguridad en el nodo afectado cuando Wazuh detecta paquetes vulnerables, reiniciando los servicios afectados si es necesario.

El inventario de Ansible incluye todos los nodos del entorno organizados por grupos correspondientes a sus VLANs, lo que permite ejecutar playbooks sobre subconjuntos específicos de la infraestructura sin afectar al resto.

### 7.8 Honeypot personalizado — HoneyCos

El honeypot es el componente más diferencial del proyecto. Se trata de una aplicación Python desarrollada desde cero, desplegada en la VM 203 dentro de la VLAN 50 completamente aislada, que simula múltiples servicios vulnerables de forma simultánea para capturar y analizar la actividad de atacantes reales.

#### Servicios simulados

El honeypot implementa seis servicios de forma simultánea:

| Servicio | Puerto | Protocolo | Librería |
|---------|--------|-----------|---------|
| SSH | 22 | TCP | paramiko |
| FTP | 21 | TCP | asyncio |
| HTTP | 80 | TCP | aiohttp |
| HTTPS | 443 | TCP | aiohttp + SSL |
| SMB | 445 | TCP | impacket |
| RDP | 3389 | TCP | asyncio |

Cada servicio captura distintos tipos de información: credenciales probadas en los intentos de login (SSH, FTP), rutas y User-Agents en las peticiones HTTP/HTTPS, y comandos ejecutados por los atacantes que consiguen autenticarse en el SSH simulado (que presenta una shell interactiva falsa).

#### Arquitectura técnica

La aplicación se estructura sobre asyncio como bucle de eventos principal, lo que permite gestionar cientos de conexiones simultáneas con un consumo de recursos mínimo sin necesidad de multiprocesado. Los servicios HTTP/HTTPS se implementan sobre aiohttp, el servidor SSH sobre paramiko (que gestiona la negociación del protocolo y el cifrado), y el servicio SMB sobre impacket, que proporciona una implementación completa del protocolo SMB en Python.

Todos los eventos capturados se registran en formato JSON estructurado, con los campos necesarios para su indexación por Wazuh: timestamp, hostname, servicio, IP de origen, acción detectada y metadatos específicos del protocolo. Este formato permite que las reglas personalizadas de Wazuh (100500–100508) correlacionen los eventos del honeypot con el mismo motor que procesa el resto de alertas del SOC.

#### Integración con el SOC

El honeypot se integra con tres componentes del stack:

- **Wazuh:** el agente instalado en VM203 monitoriza el fichero de log del honeypot y envía los eventos al manager, donde las reglas personalizadas los procesan y generan alertas.
- **Dashboard (CT109):** el honeypot envía eventos en tiempo real a la API Flask del dashboard mediante HTTP POST al puerto 5000. Esta es la única comunicación iniciada desde VLAN 50 hacia VLAN 30, y está explícitamente autorizada en el firewall de OpenWRT.
- **Prometheus:** el Node Exporter instalado en VM203 expone métricas del sistema del honeypot, permitiendo correlacionar picos de actividad de atacantes con el consumo de recursos del nodo.

#### Dashboard del honeypot (CT109)

El dashboard del honeypot es un servicio independiente desplegado en CT109 (VLAN 30) que recibe los eventos del honeypot mediante la API Flask y los presenta en tiempo real. Incluye un contador de eventos por tipo y servicio, un mapa de IPs de origen, un timeline de actividad y los últimos comandos ejecutados por los atacantes.

El acceso al dashboard se realiza a través del proxy Nginx en CT105 (puerto 8765), protegido con autenticación Basic Auth mediante un fichero htpasswd independiente del resto de servicios.

#### Problemas encontrados y soluciones

Durante el desarrollo del honeypot se encontraron varios problemas técnicos que merecen mención por su relevancia:

**Persistencia de clave SSH.** paramiko genera una clave de host nueva en cada arranque del servicio, lo que hace que los clientes SSH que recuerdan la clave anterior rechacen la conexión. Se resolvió generando la clave en el primer arranque y persistiéndola en disco para reutilizarla en arranques posteriores.

**Compatibilidad SMB con impacket.** La implementación SMB de impacket requiere ajustes específicos para responder correctamente a los negotiation requests de los clientes Windows modernos, que envían una lista de dialectos SMB2/3 que el servidor debe reconocer aunque no los implemente completamente.

**Shell interactiva SSH.** Implementar una shell que parezca funcional sin serlo realmente requirió un sistema de respuestas predefinidas para los comandos más comunes (ls, pwd, whoami, cat, wget, curl), con logs de cada comando intentado independientemente de si tiene respuesta simulada.

**Parsing de logs en Wazuh.** El formato JSON del log del honeypot tuvo que ajustarse para que el decoder JSON de Wazuh pudiera extraer correctamente los campos relevantes, especialmente el campo `action` que determina qué regla de las 100500–100508 se aplica.

### 7.9 Servicios de soporte

**Nginx — proxy inverso (CT105).** Nginx actúa como punto de entrada único para todos los servicios web del laboratorio. Escucha en siete puertos distintos y redirige el tráfico hacia el servicio correspondiente, centralizando la autenticación (Homepage y Honeypot Dashboard mediante Basic Auth) y añadiendo soporte WebSocket donde es necesario (Grafana, Vaultwarden). Vaultwarden dispone de dos virtual hosts: uno HTTP en el puerto 8091 y uno HTTPS en el 8443 con certificado autofirmado.

**Vaultwarden (CT102).** Vaultwarden es una implementación alternativa de Bitwarden Server en Rust, que proporciona gestión centralizada de contraseñas para el equipo. Se despliega en Docker dentro de CT102, con los registros de nuevos usuarios deshabilitados y un token de administración configurado. Todas las credenciales del entorno (claves SSH, tokens de API, contraseñas de servicios) se almacenan en Vaultwarden, eliminando la necesidad de distribuirlas por otros canales.

**OpenLDAP (CT100).** Se configuró un servidor LDAP con la estructura básica de OUs (usuarios y grupos) bajo el dominio `soc.local`. La integración con el resto de servicios del entorno está parcialmente desarrollada, actuando principalmente como directorio de referencia durante el período del proyecto.

**Postfix — relay de correo (CT108).** El sistema de alertas por correo se centraliza en CT108, que actúa como relay SMTP hacia Gmail. Todos los nodos del entorno (Wazuh, honeycos, honeycos-bk) envían el correo localmente a CT108 por el puerto 25, eliminando la necesidad de gestionar credenciales de Gmail en cada nodo. El diseño resolvió un problema de compatibilidad con caracteres UTF-8 en los asuntos de los correos, que causaba rebotes, mediante la directiva `smtputf8_enable = no` en los nodos origen.

**Homepage (CT107).** Dashboard de inicio desplegado en Docker que centraliza el acceso a todos los servicios del SOC mediante un panel de enlaces organizados por categorías. Protegido con autenticación Basic Auth gestionada por Nginx.

**Tailscale VPN (CT200).** CT200 proporciona acceso remoto seguro al entorno mediante Tailscale, una VPN basada en WireGuard con gestión simplificada. Conectado directamente a `vmbr0` (red WAN), permite acceder a `192.168.3.200` y a todos los servicios del laboratorio desde cualquier dispositivo del equipo sin necesidad de abrir puertos en el router doméstico.

**Web corporativa — honeycos.com (CT104).** Se desarrolló una web corporativa ficticia para la empresa "HoneyCos Security" bajo el dominio real `honeycos.com`, adquirido en IONOS. La web se expone a Internet sin abrir puertos mediante Cloudflare Tunnel, que establece una conexión saliente cifrada desde el servidor hasta la red de Cloudflare. La web incluye un formulario de contacto con verificación de identidad por OTP enviado al email del remitente, y almacena los contactos verificados en una base de datos MariaDB. El formulario implementa validaciones del lado cliente para formatos de teléfono internacional y NIF/CIF de múltiples países.

### 7.10 Hardening

El hardening del entorno se aplicó de forma sistemática a todos los nodos, combinando medidas a nivel de sistema operativo, red y configuración de servicios.

**SSH.** En todos los contenedores y VMs, el demonio SSH se configuró para escuchar en el puerto 2222 en lugar del estándar 22, rechazar la autenticación por contraseña (`PasswordAuthentication no`) y aceptar únicamente claves públicas. Se generaron pares de claves ed25519 específicos para cada conexión de servicio a servicio (como la conexión de CT106 a CT103 para la ejecución de playbooks).

**Fail2ban.** Instalado en los nodos expuestos, Fail2ban monitoriza los intentos de autenticación fallidos y bloquea automáticamente las IPs que superan el umbral configurado, complementando las reglas de Suricata para la detección de fuerza bruta.

**Segmentación de red.** La propia arquitectura de VLANs constituye la medida de hardening más importante del entorno. La política de deny-by-default en OpenWRT garantiza que cualquier nuevo nodo que se añada al entorno no tenga conectividad con otros hasta que se autorice explícitamente.

**Aislamiento del honeypot.** El honeypot opera en la VLAN más restrictiva del entorno, con políticas de REJECT en todas las direcciones por defecto. Esta medida de contención es la que proporciona la garantía de que el honeypot no puede ser utilizado como pivot hacia la infraestructura real.

**Acceso a servicios web.** El proxy inverso Nginx centraliza el acceso a todos los servicios web, aplicando autenticación Basic Auth en los paneles administrativos (Homepage, Honeypot Dashboard) y gestionando el cifrado TLS para Vaultwarden.

### 7.11 Sistema de backups

El sistema de backups utiliza la herramienta nativa de Proxmox, `vzdump`, para generar copias completas de todos los contenedores y máquinas virtuales del entorno. El proceso se automatiza mediante el script `/root/victor/backup-sync.sh`, que se ejecuta diariamente a las 2:00 mediante cron.

El script realiza vzdump de todos los CTs en modo `suspend` (suspende el contenedor brevemente para garantizar consistencia) y de todas las VMs en modo `snapshot`. La compresión `zstd` reduce el tamaño de las copias manteniendo velocidades de compresión adecuadas. La opción `--maxfiles 2` limita la retención a las dos últimas copias de cada nodo, evitando el agotamiento del espacio de almacenamiento.

Tras el vzdump, el script ejecuta un rsync hacia el servidor de backup dedicado `honeycos-bk` (192.168.3.111), organizando los backups por fecha. Al finalizar, envía un email de resumen con el estado de cada operación (OK/FAIL por CT/VM) y el log completo, a través del relay Postfix de CT108.

Durante el desarrollo del proyecto se detectó una incidencia relevante: tras una ejecución sin la opción `--maxfiles`, los backups acumulados ocuparon más de 207 GB en el almacenamiento local, aproximándose al límite del pool ZFS. La solución implicó eliminar manualmente los backups más antiguos y añadir la opción de retención a todas las llamadas de vzdump en el script.

---

## 8. Conclusiones

El proyecto ha cumplido con todos sus objetivos principales, logrando construir un entorno SOC completamente funcional sobre hardware convencional y herramientas de código abierto. Las conclusiones más relevantes se organizan en torno a los cuatro pilares del proyecto:

**Arquitectura y virtualización.** Proxmox VE ha demostrado ser una plataforma sólida y flexible para este tipo de laboratorios. La combinación de LXC para servicios ligeros y KVM para los componentes que requieren aislamiento completo de kernel (honeypot, firewall, SIEM) permite optimizar el uso de recursos sin sacrificar seguridad ni funcionalidad. El almacenamiento ZFS en mirror ha aportado integridad de datos y facilidad de gestión sin coste adicional.

**Detección y correlación.** La integración de Wazuh con Suricata, el honeypot y los agentes en todos los nodos proporciona una visibilidad completa del entorno. Las reglas personalizadas desarrolladas demuestran que es posible adaptar un SIEM de código abierto a las necesidades específicas de cualquier entorno sin necesidad de soluciones comerciales. El mecanismo de Active Response de Wazuh, integrado con Ansible, cierra el ciclo de detección-respuesta de forma automática.

**Automatización.** Los playbooks Ansible desarrollados cubren los escenarios de respuesta más habituales en un SOC real: bloqueo de IPs, aislamiento de hosts comprometidos, recolección de evidencias y actualización de sistemas. La arquitectura de ejecución centralizada en CT103 simplifica el modelo de comunicación y proporciona un log de incidentes auditable.

**Honeypot.** El honeypot propio es el componente más diferencial del proyecto. Desarrollarlo en Python ha requerido un conocimiento profundo de los protocolos implementados y ha permitido adaptarlo exactamente a las necesidades del entorno (logging estructurado para Wazuh, API para el dashboard, etc.). La exposición parcial a Internet a través de `honeycos.com` ha permitido capturar actividad real de atacantes automatizados, lo que ha validado el funcionamiento del stack completo en condiciones reales.

**Aprendizajes transversales.** El proyecto ha consolidado competencias en virtualización, administración de Linux, networking (VLANs, routing, firewall), protocolos de seguridad (SIEM, IDS, honeypots), automatización de infraestructura y desarrollo Python. Igualmente relevante ha sido la experiencia en troubleshooting de sistemas complejos: la resolución de problemas reales (WAL de Prometheus corrupto, compatibilidad SMB en el honeypot, retención de backups, caracteres UTF-8 en Postfix) ha sido tan formativa como la implementación de los componentes en condiciones nominales.

El entorno construido es reproducible, escalable y suficientemente documentado para servir como base de futuros proyectos de ciberseguridad.

---

## 9. Trabajo futuro

Las siguientes líneas de mejora han sido identificadas durante el desarrollo del proyecto y quedan pendientes para iteraciones futuras:

**Honeypot**
- Implementar una API REST Flask en VM203 para exponer las estadísticas del honeypot a sistemas externos sin depender del log en fichero.
- Añadir un dashboard en tiempo real con WebSocket en el CT109 para visualizar los eventos del honeypot sin necesidad de recargar la página.
- Ampliar los servicios simulados con MySQL, Redis o Telnet para capturar un mayor espectro de técnicas de ataque.
- Integrar feeds de Threat Intelligence externos para enriquecer los eventos del honeypot con contexto sobre las IPs atacantes.

**SIEM y detección**
- Poblar las listas CDB de Wazuh con IOCs reales procedentes de fuentes públicas (AbuseIPDB, OpenPhish, MalwareBazaar).
- Desarrollar reglas de correlación de mayor complejidad que detecten patrones de ataque multi-etapa (reconocimiento → explotación → persistencia).
- Configurar el módulo de vulnerability assessment de Wazuh para monitorizar continuamente el estado de parcheo de todos los nodos.

**Infraestructura**
- Migrar CT101 (Grafana-Prometheus) de Debian 11 a Debian 12, eliminando la deuda técnica pendiente de actualización.
- Actualizar Prometheus a la versión más reciente para beneficiarse de las mejoras de rendimiento y nuevas funcionalidades.
- Configurar SSL válido en Vaultwarden mediante Let's Encrypt a través del túnel Cloudflare, sustituyendo el certificado autofirmado actual.

**Automatización**
- Desarrollar playbooks adicionales para la gestión de compliance: verificación de configuraciones de hardening, auditoría de usuarios y grupos, y revisión de permisos de ficheros críticos.
- Implementar un sistema de tickets integrado con la plataforma SOAR para el seguimiento de incidentes de principio a fin.

**Red**
- Implementar DHCP por VLAN en OpenWRT para facilitar la incorporación de nuevos nodos sin necesidad de configuración manual de red.
- Desplegar un segundo nodo Proxmox para explorar las capacidades de clustering y migración en vivo de VMs.

---

## 10. Anexos

### Anexo A — Inventario completo de nodos

| ID | Tipo | Hostname | IP | VLAN | RAM | Disco | OS | Servicio |
|----|------|----------|----|------|-----|-------|----|---------|
| VM 201 | VM | openwrt-fw | 192.168.3.201 | — | 128 MB | 124 MB | OpenWRT 23.05.5 | Firewall/Router |
| VM 202 | VM | wazuh-siem | 10.1.1.67 | 30 | 6 GB | 50 GB | Debian 12 | Wazuh SIEM |
| VM 203 | VM | honeypot | 10.1.1.130 | 50 | 1 GB | 16 GB | Debian 12 | Honeypot Python |
| CT 100 | LXC | ldap | 10.1.1.98 | 40 | 256 MB | 10 GB | Ubuntu 22.04 | OpenLDAP |
| CT 101 | LXC | grafana-prometheus | 10.1.1.66 | 30 | 512 MB | 8 GB | Debian 11 | Grafana + Prometheus |
| CT 102 | LXC | vaultwarden | 10.1.1.80 | 30 | 256 MB | 10 GB | Debian 12 | Vaultwarden |
| CT 103 | LXC | playbooks-dns | 10.1.1.34 | 20 | 512 MB | 8 GB | Debian 12 | Bind9 + Ansible |
| CT 104 | LXC | soar-web | 10.1.1.37 | 20 | 256 MB | 20 GB | Debian 11 | SOAR + Web |
| CT 105 | LXC | nginx-proxy | 10.1.1.35 | 20 | 256 MB | 4 GB | Debian 12 | Nginx proxy |
| CT 106 | LXC | suricata-ids | 10.1.1.36 | 20 | 1 GB | 8 GB | Debian 12 | Suricata IDS |
| CT 107 | LXC | homepage | 10.1.1.68 | 30 | 512 MB | 4 GB | Debian 12 | Homepage |
| CT 108 | LXC | correo | 10.1.1.53 | 20 | 512 MB | 10 GB | Debian 12 | Postfix relay |
| CT 109 | LXC | honeypot-dashboard | 10.1.1.69 | 30 | 1 GB | 16 GB | Debian 12 | Dashboard honeypot |
| CT 200 | LXC | vpn-server | 192.168.3.250 | WAN | 128 MB | 4 GB | Debian 12 | Tailscale VPN |

### Anexo B — Puertos de servicio expuestos

| Puerto externo | Servicio | Destino interno | Via |
|---------------|---------|----------------|-----|
| 443 | Wazuh Dashboard | 10.1.1.67:443 | Directo PREROUTING |
| 3000 | Grafana | 10.1.1.66:3000 | Nginx CT105 |
| 8080 | SOAR | 10.1.1.37:8080 | Nginx CT105 |
| 8091 | Vaultwarden HTTP | 10.1.1.80:8090 | Nginx CT105 |
| 8443 | Vaultwarden HTTPS | 10.1.1.80:8090 | Nginx CT105 (cert autofirmado) |
| 8765 | Honeypot Dashboard | 10.1.1.69:80 | Nginx CT105 (Basic Auth) |
| 8888 | Homepage | 10.1.1.68:3001 | Nginx CT105 (Basic Auth) |

### Anexo C — Reglas Wazuh personalizadas (resumen)

| ID | Nivel | Origen | Evento | Email | Active Response |
|----|-------|--------|--------|-------|----------------|
| 100500 | 3 | Honeypot | Evento genérico | No | No |
| 100501 | 5 | Honeypot | Conexión detectada | No | No |
| 100502 | 8 | Honeypot | Intento de login | No | No |
| 100503 | 10 | Honeypot | Comando SSH ejecutado | Sí | collect-evidence.yml |
| 100504 | 5 | Honeypot | Request HTTP/HTTPS | No | No |
| 100505 | 10 | Honeypot | Acceso a ruta sensible | No | No |
| 100506 | 8 | Honeypot | Acceso a fichero | No | No |
| 100507 | 14 | Honeypot | Brute force detectado | Sí | block-ip.yml + collect-evidence.yml |
| 100508 | 12 | Honeypot | Evento crítico | Sí | block-ip.yml + isolate-host.yml + collect-evidence.yml |
| 100600 | 12 | Suricata | Alerta crítica (sev=1) | Sí | — |
| 100601 | 10 | Suricata | Alerta alta (sev=2) | No | — |

### Anexo D — Zona DNS soc.local (registros A)

| Hostname | FQDN | IP | VLAN | CT/VM |
|----------|------|----|------|-------|
| openwrt-fw | openwrt-fw.soc.local | 10.1.1.1 | 10 | VM 201 |
| dns | dns.soc.local | 10.1.1.34 | 20 | CT 103 |
| nginx | nginx.soc.local | 10.1.1.35 | 20 | CT 105 |
| suricata | suricata.soc.local | 10.1.1.36 | 20 | CT 106 |
| soar | soar.soc.local | 10.1.1.37 | 20 | CT 104 |
| grafana | grafana.soc.local | 10.1.1.66 | 30 | CT 101 |
| prometheus | prometheus.soc.local | 10.1.1.66 | 30 | CT 101 |
| wazuh | wazuh.soc.local | 10.1.1.67 | 30 | VM 202 |
| homepage | homepage.soc.local | 10.1.1.68 | 30 | CT 107 |
| vaultwarden | vaultwarden.soc.local | 10.1.1.80 | 30 | CT 102 |
| ldap | ldap.soc.local | 10.1.1.98 | 40 | CT 100 |
| honeypot | honeypot.soc.local | 10.1.1.130 | 50 | VM 203 |

### Anexo E — Forwardings inter-VLAN en OpenWRT

| Origen | Destino | Justificación |
|--------|---------|---------------|
| vlan10 | wan | DMZ → Internet |
| vlan20 | wan | Servicios → Internet |
| vlan30 | wan | SOC → Internet |
| vlan40 | wan | Producción → Internet |
| vlan50 | wan | Honeypot → Internet (tráfico señuelo) |
| vlan30 | vlan20 | SOC puede gestionar servicios |
| vlan20 | vlan30 | Servicios reportan al SOC |
| vlan40 | vlan30 | Producción reporta al SOC |
| vlan30 | vlan40 | SOC puede gestionar producción |
| vlan20 | vlan40 | Servicios acceden a LDAP |

---

*Memoria de Proyecto de Síntesis — CFGS ASIR — Centro Educativo — 2025–2026*
