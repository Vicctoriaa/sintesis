# OpenWRT — VM201

> Router y firewall principal del laboratorio SOC. Gestiona el enrutamiento inter-VLAN, el firewall perimetral y el relay DNS hacia Bind9.

---

## Datos de la VM

| Campo | Valor |
|-------|-------|
| VMID | 201 |
| Hostname | `openwrt-fw` |
| OS | OpenWRT 23.05.5 |
| Memoria | 128 MB |
| IP WAN | `192.168.3.201/24` |
| Gateway | `192.168.3.1` |

---

## Interfaces de red

| Interfaz | Bridge Proxmox | Rol | IP |
|----------|---------------|-----|----|
| `eth0` | `vmbr0` | WAN — red externa / gestión | `192.168.3.201/24` |
| `eth1` | `vmbr1` | LAN trunk (VLANs SOC) | — |
| `eth1.10` | `vmbr1` tag 10 | VLAN 10 — DMZ | `10.1.1.1/27` |
| `eth1.20` | `vmbr1` tag 20 | VLAN 20 — Servicios | `10.1.1.33/27` |
| `eth1.30` | `vmbr1` tag 30 | VLAN 30 — SOC | `10.1.1.65/27` |
| `eth1.40` | `vmbr1` tag 40 | VLAN 40 — Producción/LDAP | `10.1.1.97/27` |
| `eth1.50` | `vmbr1` tag 50 | VLAN 50 — Honeypot (aislado) | `10.1.1.129/27` |

### Topología

```
Internet
   ↓
Router (192.168.3.1)
   ↓
Proxmox vmbr0
   ↓
OpenWRT VM-201 (192.168.3.201)
   ├── eth0  → 192.168.3.201/24  (WAN)
   └── eth1  → trunk VLANs
         ├── eth1.10 → 10.1.1.1/27    (VLAN 10 — DMZ)
         ├── eth1.20 → 10.1.1.33/27   (VLAN 20 — Servicios)
         ├── eth1.30 → 10.1.1.65/27   (VLAN 30 — SOC)
         ├── eth1.40 → 10.1.1.97/27   (VLAN 40 — Producción/LDAP)
         └── eth1.50 → 10.1.1.129/27  (VLAN 50 — Honeypot aislado)
```

---

## Configuración de red (UCI)

```bash
# WAN — IP estática
uci set network.wan.device='eth0'
uci set network.wan.proto='static'
uci set network.wan.ipaddr='192.168.3.201'
uci set network.wan.netmask='255.255.255.0'
uci set network.wan.gateway='192.168.3.1'
uci set network.wan.dns='1.1.1.1 8.8.8.8'

# Trunk eth1 (sin IP)
uci set network.trunk=interface
uci set network.trunk.device='eth1'
uci set network.trunk.proto='none'

# VLANs
uci set network.vlan10.device='eth1.10' && uci set network.vlan10.ipaddr='10.1.1.1'   && uci set network.vlan10.netmask='255.255.255.224'
uci set network.vlan20.device='eth1.20' && uci set network.vlan20.ipaddr='10.1.1.33'  && uci set network.vlan20.netmask='255.255.255.224'
uci set network.vlan30.device='eth1.30' && uci set network.vlan30.ipaddr='10.1.1.65'  && uci set network.vlan30.netmask='255.255.255.224'
uci set network.vlan40.device='eth1.40' && uci set network.vlan40.ipaddr='10.1.1.97'  && uci set network.vlan40.netmask='255.255.255.224'
uci set network.vlan50.device='eth1.50' && uci set network.vlan50.ipaddr='10.1.1.129' && uci set network.vlan50.netmask='255.255.255.224'

uci commit network && service network restart
```

---

## DHCP

No hay servidor DHCP activo — todos los contenedores tienen IPs estáticas. Solo está activo el relay DNS hacia Bind9 en CT103:

```bash
uci set dhcp.@dnsmasq[0].server='10.1.1.34'
uci set dhcp.@dnsmasq[0].noresolv='1'
uci commit dhcp && service dnsmasq restart
```

---

## Firewall

### Política por defecto

| Dirección | Política |
|-----------|----------|
| Input global | REJECT |
| Output global | ACCEPT |
| Forward global | REJECT |
| SYN flood protection | Activo |

### Zonas

| Zona | Red | Input | Output | Forward | Masquerade |
|------|-----|-------|--------|---------|------------|
| `wan` | eth0 | REJECT | ACCEPT | REJECT | Si |
| `vlan10` | eth1.10 | REJECT | ACCEPT | REJECT | — |
| `vlan20` | eth1.20 | ACCEPT | ACCEPT | REJECT | — |
| `vlan30` | eth1.30 | ACCEPT | ACCEPT | REJECT | — |
| `vlan40` | eth1.40 | ACCEPT | ACCEPT | REJECT | — |
| `vlan50` | eth1.50 | REJECT | REJECT | REJECT | — |

> **VLAN10 (DMZ):** los hosts no pueden iniciar conexiones al router.
> **VLAN50 (Honeypot):** completamente aislada — todo REJECT salvo tráfico explícito por reglas.

### Forwardings inter-VLAN

| Origen | Destino | Descripción |
|--------|---------|-------------|
| vlan10 | wan | DMZ → Internet |
| vlan20 | wan | Servicios → Internet |
| vlan30 | wan | SOC → Internet |
| vlan40 | wan | Producción → Internet |
| vlan50 | wan | Honeypot → Internet |
| vlan30 | vlan20 | SOC → Servicios |
| vlan20 | vlan30 | Servicios → SOC |
| vlan40 | vlan30 | Producción → SOC |
| vlan30 | vlan40 | SOC → Producción |
| vlan20 | vlan40 | Servicios → Producción |

### Reglas SOC honeycos

| # | Nombre | Src | Src IP | Dest IP | Puertos | Acción | Propósito |
|---|--------|-----|--------|---------|---------|--------|-----------|
| 9 | Allow-Proxmox-Monitoring | wan | `192.168.3.0/24` | * | 22 2222 53 80 443 587 1514 1515 3000 8080 8091 8443 8765 8888 9090 9100 9119 9917 | ACCEPT | Acceso desde red de gestión a todos los puertos de servicios del SOC |
| 10 | allow-mgmt-honeypot | wan | `192.168.3.200` | `10.1.1.130` | 2222 | ACCEPT | SSH de gestión desde honeycos al honeypot (puerto real 2222) |
| 11 | honeypot-to-wazuh | vlan50 | — | `10.1.1.67` | 1514 1515 | ACCEPT | Agente Wazuh del honeypot comunica con el manager VM202 |
| 12 | prometheus-to-honeypot | vlan30 | — | `10.1.1.130` | 9100 | ACCEPT | Prometheus CT101 scrapea node_exporter del honeypot |
| 13 | honeycos-to-postfix | wan | `192.168.3.200` | `10.1.1.53` | 25 | ACCEPT | honeycos envía correo a través de Postfix CT108 |
| 14 | honeycos-bk-to-postfix | wan | `192.168.3.111` | `10.1.1.53` | 25 | ACCEPT | honeycos-bk envía correo a través de Postfix CT108 |
| 15 | honeypot-to-dashboard-api | vlan50 | — | `10.1.1.69` | 5000 | ACCEPT | Honeypot envía eventos HTTP POST a la API Flask en CT109 (:5000) |

### Aplicar cambios

```bash
uci commit firewall && service firewall restart
```

### Añadir una regla nueva

```bash
uci add firewall rule
uci set firewall.@rule[-1].name='nombre-regla'
uci set firewall.@rule[-1].src='vlan50'
uci set firewall.@rule[-1].dest='vlan30'
uci set firewall.@rule[-1].dest_ip='10.1.1.x'
uci set firewall.@rule[-1].dest_port='puerto'
uci set firewall.@rule[-1].proto='tcp'
uci set firewall.@rule[-1].target='ACCEPT'
uci commit firewall && service firewall restart
```

---

## Comandos útiles

```bash
# Acceder a la VM desde Proxmox
qm terminal 201

# Ver interfaces y direcciones IP
ip a

# Ver configuración UCI completa
uci show network
uci show firewall

# Reiniciar servicios
service network restart
service dnsmasq restart
service firewall restart
```

---

## Resumen

```
OpenWRT VM-201 (192.168.3.201)
   ├── eth0    → 192.168.3.201/24  (WAN — gw 192.168.3.1)
   ├── eth1.10 → 10.1.1.1/27      (VLAN 10 — DMZ)
   ├── eth1.20 → 10.1.1.33/27     (VLAN 20 — Servicios)
   ├── eth1.30 → 10.1.1.65/27     (VLAN 30 — SOC)
   ├── eth1.40 → 10.1.1.97/27     (VLAN 40 — Producción/LDAP)
   ├── eth1.50 → 10.1.1.129/27    (VLAN 50 — Honeypot — aislado total)
   ├── NAT     → masquerade en zona wan
   ├── DNS relay → 10.1.1.34 (CT103 Bind9)
   └── Firewall → 16 reglas activas (rule[0..15])
```
