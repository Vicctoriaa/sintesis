# VPN Server — CT200

> Contenedor dedicado a la VPN del laboratorio SOC mediante Tailscale. Proporciona acceso remoto seguro a la red de gestión (`192.168.3.0/24`) desde cualquier dispositivo. Conectado directamente a `vmbr0` (WAN), no a la red interna de VLANs.

---

## Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 200 |
| Hostname | `vpn-server` |
| OS | Debian 12 Bookworm |
| Memoria | 128 MB |
| Swap | 128 MB |
| Disco | 4 GB |
| Cores | 4 |
| Privilegiado | No |
| Features | `nesting=1` |

---

## Red

| Campo | Valor |
|-------|-------|
| Bridge | `vmbr0` (WAN — red de gestión) |
| IP | `192.168.3.250/24` |
| Gateway | `192.168.3.1` |
| IP Tailscale (IPv4) | `100.82.41.3/32` |
| IP Tailscale (IPv6) | `fd7a:115c:a1e0::5001:299d/128` |

> El contenedor está en `vmbr0` (red `192.168.3.x`), no en `vmbr1` (VLANs SOC). Esto le permite actuar como punto de entrada VPN sin interferir con el tráfico inter-VLAN.

---

## Tailscale

| Campo | Valor |
|-------|-------|
| Servicio | `tailscaled.service` — active (running) |
| Interfaz | `tailscale0` — MTU 1280 |
| IP Tailnet | `100.82.41.3` |

### Servicio systemd

```ini
[Unit]
Description=Tailscale node agent
Wants=network-pre.target
After=network-pre.target NetworkManager.service systemd-resolved.service

[Service]
EnvironmentFile=/etc/default/tailscaled
ExecStart=/usr/sbin/tailscaled \
  --state=/var/lib/tailscale/tailscaled.state \
  --socket=/run/tailscale/tailscaled.sock \
  --port=${PORT} $FLAGS
ExecStopPost=/usr/sbin/tailscaled --cleanup
Restart=on-failure
Type=notify

[Install]
WantedBy=multi-user.target
```

### Configuración LXC requerida

En `/etc/pve/lxc/200.conf` — necesario para que Tailscale pueda crear la interfaz TUN dentro del contenedor no privilegiado:

```
features: nesting=1
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net dev/net none bind,create=dir
```

> Sin estas opciones Tailscale no puede levantar la interfaz `tailscale0` en un LXC no privilegiado.

---

## Comandos útiles

```bash
# Ver estado de la VPN
tailscale status

# Ver IPs asignadas
tailscale ip

# Reconectar si hay problemas
tailscale down && tailscale up

# Ver logs del agente
journalctl -u tailscaled -f

# Ver estado del servicio
systemctl status tailscaled
```
