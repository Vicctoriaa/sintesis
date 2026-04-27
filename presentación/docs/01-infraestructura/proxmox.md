# Proxmox VE

> Nodo Proxmox principal del laboratorio SOC. Actúa como hipervisor de todos los contenedores LXC y VMs del entorno.

---

## Hardware y sistema

| Campo | Valor |
|-------|-------|
| Hostname | `honeycos` |
| IP gestión | `192.168.3.200/24` |
| Gateway | `192.168.3.1` |
| OS | Proxmox VE 9.1.1 — Debian 13 Trixie |
| Kernel | 6.17.2-1-pve |
| CPU | Intel Core i5-3470 @ 3.20GHz (4 cores) |
| RAM | 16 GB — sin swap |
| Repos APT | debian.sources + proxmox.sources (no-subscription) |

---

## Almacenamiento

### ZFS — rpool

| Campo | Valor |
|-------|-------|
| Pool | rpool |
| Tipo | Mirror (RAID-1) |
| Estado | ONLINE |
| Tamaño total | 460 GB |
| Usado | 138 GB (30%) |
| Libre | 322 GB |
| Último scrub | 2026-04-12 — 0 errores |

### Datastores Proxmox

| Name | Tipo | Total | Usado | Libre | Uso |
|------|------|-------|-------|-------|-----|
| local | dir | 439 GB | 117 GB | 322 GB | 26.7% |
| local-zfs | zfspool | 346 GB | 24 GB | 322 GB | 6.9% |

> Los backups vzdump se almacenan en `local` (`/var/lib/vz/dump`). Las imágenes de disco de CTs y VMs van a `local-zfs`.

---

## Red

### Bridges

| Bridge | Tipo | IP | Uso |
|--------|------|----|-----|
| `vmbr0` | Linux Bridge | `192.168.3.200/24` | WAN / gestión Proxmox |
| `vmbr1` | Linux Bridge VLAN-aware | sin IP | Trunk VLANs internas |

### Subinterfaces vmbr1

> Proxmox asigna la última IP de cada subred a `vmbr1.X` para monitorización interna. No son gateways — los gateways de cada VLAN son las IPs de OpenWRT.

| Interfaz | IP | VLAN |
|----------|----|------|
| `vmbr1.10` | `10.1.1.30/27` | VLAN 10 — DMZ |
| `vmbr1.20` | `10.1.1.62/27` | VLAN 20 — Servicios |
| `vmbr1.30` | `10.1.1.94/27` | VLAN 30 — SOC |
| `vmbr1.40` | `10.1.1.126/27` | VLAN 40 — Producción |
| `vmbr1.50` | `10.1.1.158/27` | VLAN 50 — Honeypot |

---

## NAT / iptables

Las reglas NAT se gestionan con `iptables` y se persisten con `netfilter-persistent`. Redirigen el tráfico entrante por `vmbr0` hacia los servicios internos.

### PREROUTING — redirección de puertos

| Puerto externo | Destino | Servicio |
|----------------|---------|----------|
| `:3000` | `10.1.1.35:3000` | Grafana (via Nginx CT105) |
| `:8080` | `10.1.1.35:8080` | SOAR (via Nginx CT105) |
| `:443` | `10.1.1.67:443` | Wazuh Dashboard (directo) |
| `:8888` | `10.1.1.35:8888` | Homepage (via Nginx CT105) |
| `:8091` | `10.1.1.35:8091` | Vaultwarden (via Nginx CT105) |
| `:8443` | `10.1.1.35:8443` | Vaultwarden SSL (via Nginx CT105) |
| `:8765` | `10.1.1.35:8765` | Honeypot Dashboard (via Nginx CT105) |

---

## Inventario de VMs y CTs

### VMs

| VMID | Nombre | RAM | Disco | Estado | Descripción |
|------|--------|-----|-------|--------|-------------|
| 201 | openwrt-fw | 128 MB | 124 MB | running | Router/Firewall principal |
| 202 | wazuh-siem | 6 GB | 50 GB | running | Wazuh SIEM 4.14.4 |
| 203 | honeypot | 1 GB | 16 GB | running | Honeypot (SSH/FTP/HTTP/HTTPS/RDP/SMB) |

### LXCs

| VMID | Nombre | RAM | Disco | CPUs | VLAN | IP |
|------|--------|-----|-------|------|------|----|
| 100 | LDAP | 256 MB | 10 GB | 1 | VLAN40 | `10.1.1.98` |
| 101 | Grafana-Prometheus | 512 MB | 8 GB | 1 | VLAN30 | `10.1.1.66` |
| 102 | Gestor-Vaultwarden | 256 MB | 10 GB | 1 | VLAN30 | `10.1.1.80` |
| 103 | playbooks-dns | 512 MB | 8 GB | 1 | VLAN20 | `10.1.1.34` |
| 104 | Soar-web | 256 MB | 20 GB | 1 | VLAN20 | `10.1.1.37` |
| 105 | nginx-proxy | 256 MB | 4 GB | 1 | VLAN20 | `10.1.1.35` |
| 106 | suricata-ids | 1 GB | 8 GB | 2 | VLAN20 | `10.1.1.36` |
| 107 | homepage | 512 MB | 4 GB | 1 | VLAN30 | `10.1.1.68` |
| 108 | Correo | 512 MB | 10 GB | 1 | VLAN20 | `10.1.1.53` |
| 109 | honeypot-dashboard | 1 GB | 16 GB | 1 | VLAN30 | `10.1.1.69` |
| 200 | vpn-server | 128 MB | 4 GB | 4 | vmbr0 (WAN) | `192.168.3.250` |

> **CT200 (vpn-server):** conectado a `vmbr0` directamente, no a VLANs. Requiere opciones especiales LXC para `/dev/net/tun`. No modificar sin precaución.
> **CT106 (suricata-ids):** 2 CPUs asignadas por la carga del IDS.

---

## Backups

### Script `/root/backup-sync.sh`

| Parámetro | Valor |
|-----------|-------|
| Destino local | `/var/lib/vz/dump` |
| Destino remoto | `backupuser@192.168.3.111:/backups/proxmox` |
| Retención | `--maxfiles 2` |
| Compresión | zstd |
| Modo CTs | suspend |
| Modo VMs | snapshot |
| Email informe | telenecos9@gmail.com (via CT108 Postfix) |

---

## Arquitectura resumida

```
honeycos (192.168.3.200) — Proxmox VE 9.1.1
   ├── vmbr0 → WAN/gestión
   │     └── NAT/DNAT → servicios internos
   ├── vmbr1 → Trunk VLANs (VLAN-aware)
   │     ├── VLAN 10 — DMZ        (10.1.1.1–30)
   │     ├── VLAN 20 — Servicios  (10.1.1.33–62)
   │     ├── VLAN 30 — SOC        (10.1.1.65–94)
   │     ├── VLAN 40 — Producción (10.1.1.97–126)
   │     └── VLAN 50 — Honeypot   (10.1.1.129–158)
   ├── ZFS mirror — rpool 460 GB (30% usado)
   │     ├── local     439 GB  (backups vzdump)
   │     └── local-zfs 346 GB  (discos CTs/VMs)
   └── Backups → rsync → 192.168.3.111 (honeycos-bk)
```
