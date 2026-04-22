# OpenWRT — VM 201 — Documentación de Configuración

**Proxmox Host:** honeycos — PVE 8.4.0
**Fecha de configuración:** Marzo 2026
**Versión OpenWRT:** 23.05.5 (r24106-10cc5fcd00)

OpenWRT actúa como router/firewall principal del laboratorio. Se ejecuta como máquina virtual (en lugar de LXC) para tener acceso directo a interfaces de red virtuales y gestionar el tráfico VLAN entre todos los segmentos del entorno.

---

## 1. Datos de la Máquina Virtual

La VM se configura con recursos mínimos suficientes para un router software. El arranque prioritario garantiza que el gateway esté operativo antes de que los contenedores dependientes intenten conectarse.

| Campo | Valor |
|-------|-------|
| VMID | 201 |
| Nombre | openwrt-fw |
| Imagen base | openwrt-23.05.5-x86-64-generic-ext4-combined-efi.img |
| Memoria | 512 MB |
| Cores | 2 |
| Almacenamiento | local-lvm:vm-201-disk-0 |
| Arranque automático | Sí (onboot=1, order=1) |

El `startup order=1` garantiza que OpenWRT arranque antes que todos los contenedores LXC, asegurando que el gateway esté disponible cuando los contenedores levantan.

---

## 2. Interfaces de Red

El diseño usa dos interfaces con roles bien diferenciados: una para la salida a internet y otra como trunk que transporta todas las VLANs internas.

| Interfaz VM | Bridge Proxmox | Tipo | Rol |
|-------------|---------------|------|-----|
| eth0 | vmbr0 | VirtIO | WAN — salida a internet |
| eth1 | vmbr1 | VirtIO | Trunk — VLANs internas |

### 2.1 Configuración WAN (eth0)

IP estática en la red del host físico. Esta interfaz es la que recibe y envía tráfico hacia el router upstream (gateway de la red física).

| Campo | Valor |
|-------|-------|
| IP | 192.168.3.201/24 |
| Gateway | 192.168.3.1 |
| DNS primario | 1.1.1.1 |
| DNS secundario | 8.8.8.8 |
| Proto | static |

### 2.2 Trunk VLAN (eth1)

`eth1` no tiene IP asignada. Actúa como trunk 802.1Q sobre el que se crean las subinterfaces VLAN. `vmbr1` en Proxmox tiene `bridge-vlan-aware yes`.

Un trunk VLAN transporta tráfico de múltiples VLANs etiquetado con 802.1Q en una sola interfaz física. Cada VLAN se expone en OpenWRT como una subinterfaz (`eth1.10`, `eth1.20`...) con su propia IP y configuración.

---

## 3. Esquema de VLANs

Cada VLAN define un segmento de red aislado con un propósito específico. La segmentación impide que un compromiso en una zona se propague libremente al resto del entorno.

| VLAN | Interfaz | Red | Gateway (OpenWRT) | Uso |
|------|----------|-----|-------------------|-----|
| 10 | eth1.10 | 10.1.1.0/27 | 10.1.1.1 | DMZ — Firewall |
| 20 | eth1.20 | 10.1.1.32/27 | 10.1.1.33 | Servicios — DNS, IDS, SOAR |
| 30 | eth1.30 | 10.1.1.64/27 | 10.1.1.65 | SOC — Grafana, Prometheus |
| 40 | eth1.40 | 10.1.1.96/27 | 10.1.1.97 | Producción — Windows AD |
| 50 | eth1.50 | 10.1.1.128/27 | 10.1.1.129 | Honeypot |

Cada subred `/27` ofrece 30 IPs usables. La máscara en decimal es `255.255.255.224`.

---

## 4. Zonas de Firewall

Cada VLAN tiene su propia zona de firewall con una política adaptada a su nivel de confianza. Las políticas de `input`/`output`/`forward` controlan respectivamente el tráfico hacia OpenWRT, desde OpenWRT y entre zonas.

| Zona | Red | Input | Output | Forward | Notas |
|------|-----|-------|--------|---------|-------|
| wan | eth0 | REJECT | ACCEPT | REJECT | Masquerade activado |
| vlan10 | eth1.10 | REJECT | ACCEPT | REJECT | DMZ restrictiva |
| vlan20 | eth1.20 | ACCEPT | ACCEPT | REJECT | Servicios internos |
| vlan30 | eth1.30 | ACCEPT | ACCEPT | REJECT | SOC |
| vlan40 | eth1.40 | ACCEPT | ACCEPT | REJECT | Producción |
| vlan50 | eth1.50 | REJECT | REJECT | REJECT | Honeypot — completamente aislada |

`vlan50` tiene `input`, `output` y `forward` en REJECT — el honeypot no puede iniciar ni recibir tráfico fuera de su zona. Esto garantiza que cualquier atacante que llegue al honeypot quede confinado sin posibilidad de pivotar o exfiltrar datos.

---

## 5. Reglas de Forwarding Inter-VLAN

El forwarding define qué zonas pueden comunicarse entre sí. Por defecto todo está bloqueado; solo se habilitan las rutas estrictamente necesarias para el funcionamiento del laboratorio.

| Origen | Destino | Motivo |
|--------|---------|--------|
| vlan10 | wan | DMZ sale a internet |
| vlan20 | wan | Servicios salen a internet |
| vlan30 | wan | SOC sale a internet |
| vlan40 | wan | Producción sale a internet |
| vlan50 | wan | Honeypot sale a internet |
| vlan30 | vlan20 | SOC puede acceder a Servicios (Grafana → DNS/IDS) |
| vlan20 | vlan30 | Servicios pueden acceder a SOC (IDS → enviar alertas) |

No existe forwarding entre el resto de VLANs. La segmentación es estricta.

---

## 6. DNS

OpenWRT usa `dnsmasq` como resolver local. Las consultas que no resuelve internamente se reenvían al DNS upstream. Se apunta también al DNS interno del laboratorio para resolver nombres de los contenedores.

| Parámetro | Valor |
|-----------|-------|
| DNS upstream WAN | 1.1.1.1, 8.8.8.8 |
| DNS interno (dnsmasq) | 10.1.1.34 (CT 103 — playbooks-dns) |
| rebind_protection | Desactivado (necesario para DNS interno) |

La `rebind_protection` se desactiva porque el DNS interno devuelve respuestas con IPs privadas, lo que normalmente bloquearía `dnsmasq` como medida anti-rebinding.

---

## 7. Contenedores LXC asociados

### VLAN 20 — Servicios

| CT | Nombre | IP | Rol |
|----|--------|----|-----|
| 103 | playbooks-dns | 10.1.1.34/27 | DNS interno (Bind9) + Ansible |
| 104 | Soar-web | 10.1.1.37/27 | SOAR |
| 105 | nginx-proxy | 10.1.1.35/27 | Reverse proxy |
| 106 | suricata-ids | 10.1.1.36/27 | IDS |

### VLAN 30 — SOC

| CT | Nombre | IP | VLAN | Rol |
|----|--------|----|------|-----|
| 101 | Grafana-Prometheus | 10.1.1.66/27 | 30 | Monitorización SOC |

---

## 8. Comandos de gestión

### Acceder a la consola de OpenWRT desde Proxmox

Abre una terminal serie directamente sobre la VM desde el host Proxmox, sin necesidad de red.

```bash
qm terminal 201
# Salir: Ctrl+O
```

### Verificar estado de red

Muestra las interfaces activas y sus IPs asignadas, y la tabla de rutas para comprobar que el gateway WAN y las subinterfaces VLAN están correctamente configuradas.

```bash
ip addr show | grep "eth\|inet "
ip route show
```

### Verificar zonas firewall

Consulta la configuración UCI de las zonas para confirmar las políticas de input/output/forward sin necesidad de abrir la interfaz web.

```bash
uci show firewall | grep -E "name|input|output|forward"
```

### Verificar forwardings

Lista las reglas de forwarding inter-VLAN activas definidas en UCI.

```bash
uci show firewall | grep forwarding
```

### Reiniciar servicios

Aplica cambios en red, firewall o DNS sin necesidad de reiniciar la VM completa.

```bash
service network restart
service firewall restart
service dnsmasq restart
```

### Apagar / encender desde Proxmox

Gestión de la VM directamente desde el host cuando no hay acceso a la consola de OpenWRT.

```bash
qm stop 201
qm start 201
```

---


## 9. Notas importantes

>  **No modificar las IPs gateway de OpenWRT** (`10.1.1.1`, `10.1.1.33`, etc.) sin actualizar también los `gw=` en las configs de los contenedores LXC en `/etc/pve/lxc/*.conf`.

>  **El LXC 100** (`openwrt-fw` antiguo) está parado y con `onboot=0`. No eliminarlo hasta validar estabilidad de la VM durante al menos una semana.

>  **El rango DHCP** de cada VLAN empieza en `start=10` (décima IP usable), dejando las primeras IPs para asignación estática a contenedores.

>  **La VLAN 50 (Honeypot)** está completamente aislada a nivel de firewall — cualquier cambio en sus reglas debe ser deliberado y documentado.
