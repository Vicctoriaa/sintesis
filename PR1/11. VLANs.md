# Configuración de VLANs — SOC Proxmox

## Esquema de Direccionamiento (Máscara /27)

| VLAN | Rango de Red | IPs Usables | Broadcast | Uso |
|------|-------------|-------------|-----------|-----|
| VLAN 10 | 10.1.1.0/27 | 10.1.1.1 — 10.1.1.30 | 10.1.1.31 | DMZ — Firewall |
| VLAN 20 | 10.1.1.32/27 | 10.1.1.33 — 10.1.1.62 | 10.1.1.63 | Servicios — DNS, IDS |
| VLAN 30 | 10.1.1.64/27 | 10.1.1.65 — 10.1.1.94 | 10.1.1.95 | SOC — Grafana, SOAR, SIEM |
| VLAN 40 | 10.1.1.96/27 | 10.1.1.97 — 10.1.1.126 | 10.1.1.127 | Producción — Windows AD |
| VLAN 50 | 10.1.1.128/27 | 10.1.1.129 — 10.1.1.158 | 10.1.1.159 | Honeypot|

> Cada subred /27 ofrece 30 IPs usables, suficientes para el entorno del SOC.

---

## 1. Habilitar VLAN awareness en Proxmox

Editar `/etc/network/interfaces` y añadir `bridge-vlan-aware yes` al bloque de `vmbr1`.  
La IP base de `vmbr1` usa la primera IP fuera de todas las subredes VLAN como gestión:

```
auto vmbr1
iface vmbr1 inet static
        address 10.1.1.2/24
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
        address 10.1.1.1/27

auto vmbr1.20
iface vmbr1.20 inet static
        address 10.1.1.33/27

auto vmbr1.30
iface vmbr1.30 inet static
        address 10.1.1.65/27

auto vmbr1.40
iface vmbr1.40 inet static
        address 10.1.1.97/27

auto vmbr1.50
iface vmbr1.50 inet static
        address 10.1.1.129/27
```

Aplicar y verificar:

```bash
systemctl restart networking
ip a | grep vmbr1
```

Resultado esperado:

```
vmbr1       inet 10.1.1.2/24
vmbr1.10    inet 10.1.1.1/27
vmbr1.20    inet 10.1.1.33/27
vmbr1.30    inet 10.1.1.65/27
vmbr1.40    inet 10.1.1.97/27
vmbr1.50    inet 10.1.1.129/27
```

---

## 3. Configurar VLANs en OpenWRT (CT100)

Entrar al contenedor:

```bash
pct exec 100 -- sh
```

Crear interfaces VLAN sobre `eth1`. Los gateways son la primera IP usable de cada subred:

```bash
uci set network.vlan10=interface
uci set network.vlan10.device=eth1.10
uci set network.vlan10.proto=static
uci set network.vlan10.ipaddr=10.1.1.1
uci set network.vlan10.netmask=255.255.255.224

uci set network.vlan20=interface
uci set network.vlan20.device=eth1.20
uci set network.vlan20.proto=static
uci set network.vlan20.ipaddr=10.1.1.33
uci set network.vlan20.netmask=255.255.255.224

uci set network.vlan30=interface
uci set network.vlan30.device=eth1.30
uci set network.vlan30.proto=static
uci set network.vlan30.ipaddr=10.1.1.65
uci set network.vlan30.netmask=255.255.255.224

uci set network.vlan40=interface
uci set network.vlan40.device=eth1.40
uci set network.vlan40.proto=static
uci set network.vlan40.ipaddr=10.1.1.97
uci set network.vlan40.netmask=255.255.255.224

uci set network.vlan50=interface
uci set network.vlan50.device=eth1.50
uci set network.vlan50.proto=static
uci set network.vlan50.ipaddr=10.1.1.129
uci set network.vlan50.netmask=255.255.255.224

uci commit network
service network restart
```

> La máscara /27 en formato decimal es `255.255.255.224`

Verificar:

```bash
ip a | grep eth1
```

---

## 4. Configurar DHCP por VLAN en OpenWRT

```bash
uci set dhcp.vlan10=dhcp
uci set dhcp.vlan10.interface=vlan10
uci set dhcp.vlan10.start=10
uci set dhcp.vlan10.limit=20
uci set dhcp.vlan10.leasetime=12h

uci set dhcp.vlan20=dhcp
uci set dhcp.vlan20.interface=vlan20
uci set dhcp.vlan20.start=10
uci set dhcp.vlan20.limit=20
uci set dhcp.vlan20.leasetime=12h

uci set dhcp.vlan30=dhcp
uci set dhcp.vlan30.interface=vlan30
uci set dhcp.vlan30.start=10
uci set dhcp.vlan30.limit=20
uci set dhcp.vlan30.leasetime=12h

uci set dhcp.vlan40=dhcp
uci set dhcp.vlan40.interface=vlan40
uci set dhcp.vlan40.start=10
uci set dhcp.vlan40.limit=20
uci set dhcp.vlan40.leasetime=12h

uci set dhcp.vlan50=dhcp
uci set dhcp.vlan50.interface=vlan50
uci set dhcp.vlan50.start=10
uci set dhcp.vlan50.limit=20
uci set dhcp.vlan50.leasetime=12h

uci commit dhcp
service dnsmasq restart
```

> El `start=10` evita colisionar con las IPs estáticas asignadas a los contenedores.

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

uci add firewall zone
uci set firewall.@zone[-1].name=vlan50
uci set firewall.@zone[-1].network=vlan50
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
