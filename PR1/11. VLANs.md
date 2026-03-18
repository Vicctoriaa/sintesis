# Configuración de VLANs — SOC Proxmox

## Esquema de VLANs

| VLAN | Red | Uso |
|------|-----|-----|
| VLAN 10 | 192.168.10.0/24 | DMZ — Firewall |
| VLAN 20 | 192.168.20.0/24 | Servicios — DNS, IDS |
| VLAN 30 | 192.168.30.0/24 | SOC — Grafana, SOAR, SIEM |
| VLAN 40 | 192.168.40.0/24 | Producción — Windows AD |

---

## 1. Habilitar VLAN awareness en Proxmox

Editar `/etc/network/interfaces` y añadir `bridge-vlan-aware yes` al bloque de `vmbr1`:

```
auto vmbr1
iface vmbr1 inet static
        address 192.168.10.254/24
        bridge-ports enp0s8
        bridge-stp off
        bridge-fd 0
        bridge-vlan-aware yes
```

Aplicar cambios:

```bash
systemctl restart networking
```

---

## 2. Crear interfaces VLAN en Proxmox

Añadir al final de `/etc/network/interfaces`:

```
auto vmbr1.10
iface vmbr1.10 inet static
        address 192.168.10.1/24

auto vmbr1.20
iface vmbr1.20 inet static
        address 192.168.20.1/24

auto vmbr1.30
iface vmbr1.30 inet static
        address 192.168.30.1/24

auto vmbr1.40
iface vmbr1.40 inet static
        address 192.168.40.1/24
```

Aplicar y verificar:

```bash
systemctl restart networking
ip a | grep vmbr1
```

Resultado esperado:

```
vmbr1.10@vmbr1  inet 192.168.10.1/24
vmbr1.20@vmbr1  inet 192.168.20.1/24
vmbr1.30@vmbr1  inet 192.168.30.1/24
vmbr1.40@vmbr1  inet 192.168.40.1/24
```

---

## 3. Configurar VLANs en OpenWRT (CT100)

Entrar al contenedor:

```bash
pct exec 100 -- sh
```

Crear interfaces VLAN sobre `eth1`:

```bash
uci set network.vlan10=interface
uci set network.vlan10.device=eth1.10
uci set network.vlan10.proto=static
uci set network.vlan10.ipaddr=192.168.10.1
uci set network.vlan10.netmask=255.255.255.0

uci set network.vlan20=interface
uci set network.vlan20.device=eth1.20
uci set network.vlan20.proto=static
uci set network.vlan20.ipaddr=192.168.20.1
uci set network.vlan20.netmask=255.255.255.0

uci set network.vlan30=interface
uci set network.vlan30.device=eth1.30
uci set network.vlan30.proto=static
uci set network.vlan30.ipaddr=192.168.30.1
uci set network.vlan30.netmask=255.255.255.0

uci set network.vlan40=interface
uci set network.vlan40.device=eth1.40
uci set network.vlan40.proto=static
uci set network.vlan40.ipaddr=192.168.40.1
uci set network.vlan40.netmask=255.255.255.0

uci commit network
service network restart
```

Verificar:

```bash
ip a | grep eth1
```

---

## 4. Configurar DHCP por VLAN en OpenWRT

```bash
uci set dhcp.vlan10=dhcp
uci set dhcp.vlan10.interface=vlan10
uci set dhcp.vlan10.start=100
uci set dhcp.vlan10.limit=50
uci set dhcp.vlan10.leasetime=12h

uci set dhcp.vlan20=dhcp
uci set dhcp.vlan20.interface=vlan20
uci set dhcp.vlan20.start=100
uci set dhcp.vlan20.limit=50
uci set dhcp.vlan20.leasetime=12h

uci set dhcp.vlan30=dhcp
uci set dhcp.vlan30.interface=vlan30
uci set dhcp.vlan30.start=100
uci set dhcp.vlan30.limit=50
uci set dhcp.vlan30.leasetime=12h

uci set dhcp.vlan40=dhcp
uci set dhcp.vlan40.interface=vlan40
uci set dhcp.vlan40.start=100
uci set dhcp.vlan40.limit=50
uci set dhcp.vlan40.leasetime=12h

uci commit dhcp
service dnsmasq restart
```

---

## 5. Crear zonas de firewall por VLAN en OpenWRT

```bash
uci add firewall zone
uci set firewall.@zone[-1].name=vlan10
uci set firewall.@zone[-1].network=vlan10
uci set firewall.@zone[-1].input=ACCEPT
uci set firewall.@zone[-1].output=ACCEPT
uci set firewall.@zone[-1].forward=REJECT

uci add firewall zone
uci set firewall.@zone[-1].name=vlan20
uci set firewall.@zone[-1].network=vlan20
uci set firewall.@zone[-1].input=ACCEPT
uci set firewall.@zone[-1].output=ACCEPT
uci set firewall.@zone[-1].forward=REJECT

uci add firewall zone
uci set firewall.@zone[-1].name=vlan30
uci set firewall.@zone[-1].network=vlan30
uci set firewall.@zone[-1].input=ACCEPT
uci set firewall.@zone[-1].output=ACCEPT
uci set firewall.@zone[-1].forward=REJECT

uci add firewall zone
uci set firewall.@zone[-1].name=vlan40
uci set firewall.@zone[-1].network=vlan40
uci set firewall.@zone[-1].input=ACCEPT
uci set firewall.@zone[-1].output=ACCEPT
uci set firewall.@zone[-1].forward=REJECT

uci commit firewall
service firewall restart
```

Verificar zonas creadas:

```bash
uci show firewall | grep name
```
