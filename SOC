# 🔐 SOC Lab - Proyecto de Seguridad

Infraestructura de **Security Operations Center (SOC)** diseñada para la detección de intrusiones, monitorización de sistemas, automatización de alertas y gestión de incidentes.

---

# 🛡️ 1. Detección de Intrusiones

Sistema encargado de detectar comportamientos sospechosos o ataques dentro de la red.

- Monitorización de eventos de red
- Análisis de logs
- Generación de alertas de seguridad

---

# 📊 2. Dashboard de Monitorización

Visualización en tiempo real del estado de la infraestructura y métricas del sistema.

- **Grafana** (contenedor Docker)  
  Visualización de métricas mediante dashboards.

- **Prometheus** (contenedor Docker)  
  Recolección y almacenamiento de métricas.

---

# 🔥 3. Firewall

Sistema encargado de controlar y filtrar el tráfico de red.

- **OpenWRT**
- Implementación en:
  - Contenedor **LXC**
  - Máquina virtual

---

# 🤖 4. Playbooks (Automatización)

Scripts diseñados para automatizar respuestas ante eventos de seguridad.

- Scripts en **Bash**
- Automatización de alertas
- Envío de correos electrónicos mediante **SMTP**

---

# ⚙️ 5. SOAR - Plataforma Web

Sistema web para la gestión y automatización de incidentes de seguridad.

### Tecnologías

- **HTML**
- **CSS**
- **PHP seguro**
- **JavaScript** (posible implementación)

### Base de datos

- **MySQL**
- **MariaDB**

### Funcionalidades

- Formularios de reporte de incidentes
- Gestión de alertas
- Integración con playbooks

---

# 🖥️ 6. Infraestructura

Plataforma donde se ejecuta todo el laboratorio SOC.

- **Proxmox** como hipervisor
- Máquina dedicada para **backups**
- Posible implementación de **cluster**

---

# 💾 7. Backup

Sistema de copias de seguridad de la infraestructura.

- Máquina dedicada para **backup**
- Posible **cluster de almacenamiento**

---

# 🧑‍💻 8. Máquina Supervisada

Sistema monitorizado dentro del SOC.

- **Windows Server**
- **Active Directory (AD)**

---

# 🎯 9. Intrusión Final (Simulación)

Simulación de un ataque real para comprobar la capacidad de detección del SOC.

- Equipos atacantes: **nuestros PCs**
- Evaluación del sistema de detección y respuesta

---

# 🧱 Arquitectura General

```
Atacante (PC)
     │
     ▼
Firewall (OpenWRT)
     │
     ▼
Infraestructura (Proxmox)
     │
     ▼
Máquinas monitorizadas (Windows AD)
     │
     ▼
SOC
 ├── Prometheus
 ├── Grafana
 ├── Playbooks
 └── Plataforma SOAR
```

---

# 🎯 Objetivo del Proyecto

Construir un **SOC funcional en laboratorio** capaz de:

- Detectar intrusiones
- Monitorizar sistemas
- Automatizar respuestas
- Gestionar incidentes de seguridad
- Analizar ataques simulados
