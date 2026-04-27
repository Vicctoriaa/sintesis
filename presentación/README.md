# Proyecto de Síntesis

Este proyecto se centra en el desarrollo de un Honeypot y la centralización de eventos de seguridad.

---

## Objetivos Principales
* Aislamiento de Amenazas: Uso de la VLAN 50 para confinar el tráfico del honeypot, evitando desplazamientos laterales hacia la infraestructura crítica.
* Monitorización Avanzada: Integración de agentes Wazuh para la correlación de logs y detección de intrusiones.
* Análisis de Datos: Desarrollo de una API propia para la geolocalización y normalización de eventos mediante bases de datos MaxMind GeoLite2.
* Automatización: Gestión de la configuración mediante Ansible Playbooks para garantizar la repetibilidad del entorno.

---

## Arquitectura del Sistema

El ecosistema se distribuye en varias capas tecnológicas coordinadas:

| Capa | Componentes |
| :--- | :--- |
| Virtualización | Proxmox VE |
| Networking | OpenWRT (VLANs), VPN Server |
| Seguridad Perimetral | Nginx Proxy Manager |
| Detección (EDR/IDS) | Wazuh, Suricata |
| Honeypot (honeycos) | Emulación de SSH, FTP, HTTP/S, RDP y SMB |
| Observabilidad | Prometheus y Grafana |
