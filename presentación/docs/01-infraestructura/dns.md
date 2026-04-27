# DNS Bind9 — CT103

> Servidor DNS interno del laboratorio. Resuelve nombres de la zona privada `soc.local` para todos los contenedores y VMs, y reenvía las consultas externas a resolvers públicos. Comparte contenedor con el nodo de control Ansible (`playbooks-dns`).

---

## Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 103 |
| Hostname | `playbooks-dns` |
| IP | `10.1.1.34/27` |
| Gateway | `10.1.1.33` (OpenWRT VLAN 20) |
| VLAN | 20 — Servicios |
| OS | Debian 12 Bookworm |
| Servicio | `named` (BIND 9.16.50-Debian ESV) |
| Puertos | `53/udp`, `53/tcp` |
| Stats channel | `127.0.0.1:8080` |
| Estado | active (running) desde 2026-04-23 |

---

## Arquitectura DNS

```
Contenedores SOC / Red gestión (192.168.3.0/24)
      │
      ▼
Bind9 (10.1.1.34)
      │
      ├── Zona directa:  soc.local            (master)
      ├── Zona inversa:  1.1.10.in-addr.arpa  (master)
      │
      └── Forwarders externos
            ├── 8.8.8.8  (Google)
            └── 1.1.1.1  (Cloudflare)
```

---

## Configuración principal

### `named.conf.options`

```
options {
    directory "/var/cache/bind";
    recursion yes;
    allow-recursion { 10.1.1.0/24; 192.168.3.0/24; localhost; };
    allow-query { 10.1.1.0/24; 192.168.3.0/24; localhost; };
    forwarders {
        8.8.8.8;
        1.1.1.1;
    };
    dnssec-validation auto;
    listen-on { 10.1.1.34; localhost; };
};

statistics-channels {
    inet 127.0.0.1 port 8080 allow { 127.0.0.1; };
};
```

> `allow-recursion` y `allow-query` incluyen tanto la red interna `10.1.1.0/24` como la red de gestión `192.168.3.0/24` (honeycos, honeycos-bk). El `statistics-channels` en `127.0.0.1:8080` es consumido por `bind_exporter` para enviar métricas a Prometheus.

### `named.conf.local`

```
zone "soc.local" {
    type master;
    file "/etc/bind/zones/db.soc.local";
};

zone "1.1.10.in-addr.arpa" {
    type master;
    file "/etc/bind/zones/db.10.1.1";
};
```

---

## Zona directa — `soc.local`

**Fichero:** `/etc/bind/zones/db.soc.local`
**Serial:** `2026041301`
**TTL:** 604800 (7 días)

```
$TTL    604800
@       IN      SOA     dns.soc.local. admin.soc.local. (
                        2026041301
                        604800
                        86400
                        2419200
                        604800 )
@       IN      NS      dns.soc.local.

; VLAN 10 - DMZ (10.1.1.0/27)
openwrt-fw      IN  A   10.1.1.1

; VLAN 20 - Servicios (10.1.1.32/27)
dns             IN  A   10.1.1.34
nginx           IN  A   10.1.1.35
suricata        IN  A   10.1.1.36
soar            IN  A   10.1.1.37

; VLAN 30 - SOC (10.1.1.64/27)
grafana         IN  A   10.1.1.66
prometheus      IN  A   10.1.1.66
wazuh           IN  A   10.1.1.67
homepage        IN  A   10.1.1.68
vaultwarden     IN  A   10.1.1.80

; VLAN 40 - Produccion (10.1.1.96/27)
ldap            IN  A   10.1.1.98

; VLAN 50 - Honeypot (10.1.1.128/27)
honeypot        IN  A   10.1.1.130
```

### Registros A activos

| Hostname | FQDN | IP | VLAN | CT/VM |
|----------|------|----|------|-------|
| openwrt-fw | `openwrt-fw.soc.local` | `10.1.1.1` | 10 | VM201 |
| dns | `dns.soc.local` | `10.1.1.34` | 20 | CT103 |
| nginx | `nginx.soc.local` | `10.1.1.35` | 20 | CT105 |
| suricata | `suricata.soc.local` | `10.1.1.36` | 20 | CT106 |
| soar | `soar.soc.local` | `10.1.1.37` | 20 | CT104 |
| grafana | `grafana.soc.local` | `10.1.1.66` | 30 | CT101 |
| prometheus | `prometheus.soc.local` | `10.1.1.66` | 30 | CT101 |
| wazuh | `wazuh.soc.local` | `10.1.1.67` | 30 | VM202 |
| homepage | `homepage.soc.local` | `10.1.1.68` | 30 | CT107 |
| vaultwarden | `vaultwarden.soc.local` | `10.1.1.80` | 30 | CT102 |
| ldap | `ldap.soc.local` | `10.1.1.98` | 40 | CT100 |
| honeypot | `honeypot.soc.local` | `10.1.1.130` | 50 | VM203 |

> `grafana` y `prometheus` comparten IP (`10.1.1.66`) — ambos servicios corren en CT101.

---

## Zona inversa — `1.1.10.in-addr.arpa`

**Fichero:** `/etc/bind/zones/db.10.1.1`
**Serial:** `2026041301`
**TTL:** 604800 (7 días)

```
$TTL 604800
@   IN  SOA     dns.soc.local. admin.soc.local. (
                2026041301  ; Serial
                604800      ; Refresh
                86400       ; Retry
                2419200     ; Expire
                604800 )    ; Negative Cache TTL
@       IN  NS      dns.soc.local.

; VLAN 10 - DMZ
1       IN  PTR     openwrt-fw.soc.local.

; VLAN 20 - Servicios
34      IN  PTR     dns.soc.local.
35      IN  PTR     nginx.soc.local.
36      IN  PTR     suricata.soc.local.
37      IN  PTR     soar.soc.local.

; VLAN 30 - SOC
66      IN  PTR     grafana.soc.local.
67      IN  PTR     wazuh.soc.local.
68      IN  PTR     homepage.soc.local.
80      IN  PTR     vaultwarden.soc.local.

; VLAN 40 - Produccion
98      IN  PTR     ldap.soc.local.

; VLAN 50 - Honeypot
130     IN  PTR     honeypot.soc.local.
```

### Registros PTR activos

| Último octeto | IP completa | PTR |
|--------------|-------------|-----|
| 1 | `10.1.1.1` | `openwrt-fw.soc.local.` |
| 34 | `10.1.1.34` | `dns.soc.local.` |
| 35 | `10.1.1.35` | `nginx.soc.local.` |
| 36 | `10.1.1.36` | `suricata.soc.local.` |
| 37 | `10.1.1.37` | `soar.soc.local.` |
| 66 | `10.1.1.66` | `grafana.soc.local.` |
| 67 | `10.1.1.67` | `wazuh.soc.local.` |
| 68 | `10.1.1.68` | `homepage.soc.local.` |
| 80 | `10.1.1.80` | `vaultwarden.soc.local.` |
| 98 | `10.1.1.98` | `ldap.soc.local.` |
| 130 | `10.1.1.130` | `honeypot.soc.local.` |
