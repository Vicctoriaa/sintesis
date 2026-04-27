# Alertas por Correo — CT108

> Sistema centralizado de alertas por correo. Todos los nodos del SOC delegan el envío en CT108 (Postfix relay), que actúa como único punto de salida hacia Gmail. Esto centraliza las credenciales y simplifica el troubleshooting.

---

## Arquitectura

```
honeycos (192.168.3.200)      --|
honeycos-bk (192.168.3.111)   --|
wazuh-siem (10.1.1.67)        --|→ CT108 Postfix relay (10.1.1.53) → Gmail (:587)
(cualquier nodo SOC)          --|
```

---

## CT108 — Servidor relay

### Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 108 |
| Hostname | `Correo` |
| OS | Debian 12 |
| IP | `10.1.1.53/27` |
| VLAN | 20 — Servicios |
| Servicios | Postfix + rsyslog |

### Instalación

```bash
apt update && apt install postfix mailutils libsasl2-modules ca-certificates -y
```

> Durante la instalación seleccionar **Internet Site** y como nombre `wazuh-relay.local`.

### Configuración — `/etc/postfix/main.cf`

```
myhostname = wazuh-relay.local
myorigin = /etc/mailname
mydestination = localhost, localhost.localdomain, localhost
relayhost = [smtp.gmail.com]:587
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
smtp_sasl_security_options = noanonymous
smtp_tls_CAfile = /etc/ssl/certs/ca-certificates.crt
smtp_use_tls = yes
smtp_tls_security_level = encrypt
mynetworks = 127.0.0.0/8, 10.1.1.0/24, 192.168.3.0/24
inet_interfaces = all
inet_protocols = ipv4
smtpd_relay_restrictions = permit_mynetworks, reject_unauth_destination
```

### Credenciales Gmail — `/etc/postfix/sasl_passwd`

```
[smtp.gmail.com]:587 usuario@gmail.com:PASSWORD_APP
```

> La contraseña debe ser una **contraseña de aplicación** de Google (no la contraseña de la cuenta). Se genera en: Cuenta Google → Seguridad → Verificación en dos pasos → Contraseñas de aplicación.

```bash
postmap /etc/postfix/sasl_passwd
chmod 600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db
systemctl restart postfix
```

### Comandos de gestión

```bash
# Estado
postfix status
systemctl status postfix

# Recargar configuración
postfix reload

# Ver cola de correo
mailq

# Vaciar cola
postsuper -d ALL

# Ver logs
tail -f /var/log/syslog | grep postfix

# Probar envío desde CT108
echo "Test" | mail -s "Test CT108" destino@gmail.com
```

---

## Integrar un nodo nuevo

### 1. Instalar paquetes

```bash
apt install -y postfix mailutils
```

> Seleccionar **Internet Site** y hostname del nodo (ej: `wazuh-siem.soc.local`).

### 2. Configurar relay hacia CT108

```bash
postconf -e "relayhost = [10.1.1.53]:25"
postconf -e "inet_interfaces = loopback-only"
postconf -e "inet_protocols = ipv4"
postconf -e "smtputf8_enable = no"
postfix reload
```

> `smtputf8_enable = no` es crítico — sin esto el correo rebota con `SMTPUTF8 is required, but was not offered` si el asunto o cuerpo contiene caracteres especiales.

### 3. Verificar conectividad

```bash
telnet 10.1.1.53 25
# Debe responder: 220 wazuh-relay.local ESMTP Postfix
```

### 4. Probar envío

```bash
echo "Test desde $(hostname)" | mail -s "[SOC] Test correo" telenecos9@gmail.com
```

### 5. Verificar en CT108

```bash
tail -20 /var/log/syslog | grep postfix
# Debe aparecer: status=sent
```

---

## Nodos configurados

| Nodo | IP | Rol |
|------|----|-----|
| CT108 Correo | `10.1.1.53` | Servidor relay |
| VM202 wazuh-siem | `10.1.1.67` | Configurado — alertas Wazuh |
| honeycos | `192.168.3.200` | Configurado — alertas backup-sync |
| honeycos-bk | `192.168.3.111` | Configurado — alertas organizar-backups |

---

## Reglas OpenWRT

Los nodos en VLAN20 tienen acceso directo a CT108 sin reglas adicionales. Los nodos en la red de gestión (`192.168.3.0/24`) necesitan regla explícita.

| Nombre | Origen | Destino | Puerto |
|--------|--------|---------|--------|
| honeycos-to-postfix | `192.168.3.200` | `10.1.1.53` | 25 |
| honeycos-bk-to-postfix | `192.168.3.111` | `10.1.1.53` | 25 |

```bash
uci add firewall rule
uci set firewall.@rule[-1].name='honeycos-to-postfix'
uci set firewall.@rule[-1].src='wan'
uci set firewall.@rule[-1].src_ip='192.168.3.200'
uci set firewall.@rule[-1].dest='vlan20'
uci set firewall.@rule[-1].dest_ip='10.1.1.53'
uci set firewall.@rule[-1].dest_port='25'
uci set firewall.@rule[-1].proto='tcp'
uci set firewall.@rule[-1].target='ACCEPT'
uci commit firewall && service firewall restart
```

---

## Ruta estática en honeycos-bk

`honeycos-bk` tiene como gateway el router doméstico (`192.168.3.1`), que no conoce la red `10.1.1.0/24`. Se necesita ruta estática hacia `192.168.3.201` (OpenWRT).

**`/etc/netplan/00-installer-config.yaml`:**

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eno2:
      dhcp4: no
      addresses:
        - 192.168.3.111/24
      gateway4: 192.168.3.1
      nameservers:
        addresses: [8.8.8.8, 192.168.3.200]
      routes:
        - to: 10.1.1.0/24
          via: 192.168.3.201
```

```bash
sudo netplan apply
```

---

## Uso en scripts

```bash
# Envío simple
echo "Mensaje" | mail -s "Asunto" telenecos9@gmail.com

# Envío multilínea
CUERPO=$(cat <<EOF
Linea 1
Linea 2
EOF
)
echo "$CUERPO" | mail -s "Asunto" telenecos9@gmail.com

# Verificar cola (debe estar vacía)
mailq
```

---

## Alertas en Wazuh

**`/var/ossec/etc/ossec.conf` en VM202:**

```xml
<global>
  <email_notification>yes</email_notification>
  <smtp_server>10.1.1.53</smtp_server>
  <email_from>alertas-wazuh@soc.local</email_from>
  <email_to>telenecos9@gmail.com</email_to>
</global>
```

---

## Troubleshooting

| Error | Causa | Solución |
|-------|-------|----------|
| `SMTPUTF8 is required` | Caracteres especiales en el mensaje | `postconf -e "smtputf8_enable = no"` en el nodo origen. Evitar `╔══`, `──`, `✓` en scripts |
| `Relay access denied` | IP del nodo no está en `mynetworks` de CT108 | Añadir la red a `mynetworks` en CT108 y hacer `postfix reload` |
| `Connection refused` al puerto 25 | Sin ruta de red, firewall bloqueando, o Postfix caído | Verificar: `telnet 10.1.1.53 25` → ruta → regla OpenWRT |
| Correo no llega a Gmail | Filtrado como spam | Revisar carpeta de spam en Gmail |
