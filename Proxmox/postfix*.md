# Alertas por Correo — SOC honeycos

> Sistema centralizado de alertas por correo electrónico para el laboratorio. En lugar de que cada nodo gestione su propio envío de correo, todos delegan en un servidor relay (CT108) que actúa como intermediario hacia Gmail. Esto simplifica la gestión de credenciales y centraliza el troubleshooting de correo en un único punto.

---

## 1. Arquitectura del sistema de correo

> El CT108 es el único nodo que conoce las credenciales de Gmail. El resto de nodos (Wazuh, honeycos, honeycos-bk) le envían el correo localmente por el puerto 25 usando Postfix en modo relay, sin necesitar credenciales propias. CT108 lo recibe y lo reenvía a Gmail con TLS y autenticación.

```
honeycos (192.168.3.200)         ---|
honeycos-bk (192.168.3.111)      ---|--> CT108 Postfix relay (10.1.1.53) --> Gmail (smtp.gmail.com:587)
wazuh-siem (10.1.1.67)           ---|
(cualquier nodo SOC)             ---|
```

---

## 2. CT108 — Servidor relay (Postfix)

> Postfix es el servidor de correo que actúa como relay central. Se configura para aceptar correos de la red interna y reenviarlos a Gmail usando autenticación SASL y cifrado TLS. El uso de una contraseña de aplicación de Google (en lugar de la contraseña normal) es obligatorio cuando la cuenta tiene 2FA activado.

### Datos del contenedor

> Contenedor ligero en la VLAN 20 (Servicios), junto al resto de infraestructura de soporte. Además de Postfix, corre `rsyslog` para centralizar logs del sistema.

| Campo | Valor |
|-------|-------|
| CT ID | 108 |
| Hostname | Correo |
| IP | 10.1.1.53/27 |
| VLAN | 20 — Servicios |
| OS | Debian 12 |
| Servicio | Postfix + rsyslog |

### Instalación de paquetes

> Los cuatro paquetes son necesarios: `postfix` es el servidor de correo, `mailutils` proporciona el comando `mail` para envíos desde scripts, `libsasl2-modules` permite la autenticación SMTP contra Gmail, y `ca-certificates` contiene los certificados raíz para validar el TLS de Google.

```bash
apt update
apt install postfix mailutils libsasl2-modules ca-certificates -y
```

> Durante la instalación seleccionar: **Tipo: Internet Site** y como nombre `wazuh-relay.local` (puede ser cualquier nombre).

### Configuración `/etc/postfix/main.cf`

> Fichero principal de configuración de Postfix. Los parámetros clave son `relayhost` (apunta a Gmail), los bloques `smtp_sasl_*` (autenticación), los bloques `smtp_tls_*` (cifrado obligatorio) y `mynetworks` (define qué IPs pueden usar este relay). La directiva `smtpd_relay_restrictions` impide que actúe como open relay aceptando correo de redes no autorizadas.

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

### Credenciales Gmail `/etc/postfix/sasl_passwd`

> Fichero que contiene las credenciales para autenticarse contra Gmail. Tras crearlo o modificarlo hay que ejecutar `postmap /etc/postfix/sasl_passwd` para compilarlo en formato `.db` que Postfix puede leer, y `chmod 600` para que solo root tenga acceso.

```
[smtp.gmail.com]:587 usuario@gmail.com:PASSWORD_APP
```

> La contraseña debe ser una **contraseña de aplicación** de Google (no la contraseña normal de Gmail). Se genera en: Cuenta Google → Seguridad → Verificación en dos pasos → Contraseñas de aplicación.

```bash
postmap /etc/postfix/sasl_passwd
chmod 600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db
systemctl restart postfix
```

### Comandos de gestión CT108

> Referencia rápida para operar el servidor relay. `mailq` / `postqueue -p` muestran correos que están esperando ser enviados. `postsuper -d ALL` limpia la cola, útil si hay correos atascados que bloquean envíos nuevos.

```bash
# Estado del servicio
postfix status
systemctl status postfix

# Recargar configuracion
postfix reload

# Ver cola de correo
mailq

# Vaciar cola
postsuper -d ALL

# Ver logs
tail -f /var/log/syslog | grep postfix

# Probar envio desde CT108
echo "Test" | mail -s "Test CT108" destino@gmail.com
```

---

## 3. Configurar un nuevo nodo para enviar alertas

> Procedimiento estándar para integrar cualquier nodo del SOC con el relay de correo. En lugar de configurar credenciales de Gmail en cada nodo, se instala Postfix en modo relay local: el nodo envía el correo a CT108 (puerto 25) y CT108 se encarga del resto.

### Paso 1 — Instalar paquetes

```bash
apt install -y postfix mailutils
```

> Durante la instalación seleccionar **"Internet Site"** y como hostname el nombre del nodo (ej: `wazuh-siem.soc.local`).

### Paso 2 — Configurar relay hacia CT108

> Se configuran solo los parámetros necesarios usando `postconf -e` (edita `main.cf` en línea). `loopback-only` limita Postfix a escuchar únicamente en localhost, ya que este nodo no necesita recibir correo externo, solo enviarlo. `smtputf8_enable = no` es crítico: sin este parámetro los correos rebotan si el asunto o cuerpo contiene caracteres especiales.

```bash
postconf -e "relayhost = [10.1.1.53]:25"
postconf -e "inet_interfaces = loopback-only"
postconf -e "inet_protocols = ipv4"
postconf -e "smtputf8_enable = no"
postfix reload
```

> **IMPORTANTE:** `smtputf8_enable = no` es necesario para evitar errores de compatibilidad con CT108. Sin esto el correo rebota con el error `SMTPUTF8 is required, but was not offered`.

### Paso 3 — Verificar conectividad con CT108

> Comprueba que el nodo puede alcanzar CT108 por el puerto 25 antes de intentar enviar correo. Si no conecta, el problema es de red o de firewall (ver sección 5).

```bash
telnet 10.1.1.53 25
```

Debe responder:
```
Connected to 10.1.1.53.
220 wazuh-relay.local ESMTP Postfix
```

> Si no conecta, revisar las reglas de OpenWRT (ver sección 5).

### Paso 4 — Probar envío

```bash
echo "Test desde $(hostname)" | mail -s "[SOC] Test correo" telenecos9@gmail.com
```

### Paso 5 — Verificar en CT108

> El log de CT108 es la fuente definitiva para confirmar que el correo se ha enviado a Gmail. `status=sent` indica éxito; cualquier otro status indica un error que debe investigarse.

```bash
tail -20 /var/log/syslog | grep postfix
```

> Debe aparecer `status=sent`.

---

## 4. Nodos configurados

> Estado actual de todos los nodos que usan el relay de correo. Los nodos en `192.168.3.x` (red de gestión) requieren configuración adicional de rutas y firewall respecto a los nodos en la VLAN 20.

| Nodo | IP | Estado |
|------|----|--------|
| CT108 Correo | 10.1.1.53 | Servidor relay |
| VM202 wazuh-siem | 10.1.1.67 | Configurado — envía alertas Wazuh |
| honeycos | 192.168.3.200 | Configurado — envía alertas backup-sync |
| honeycos-bk | 192.168.3.111 | Configurado — envía alertas organizar-backups |

---

## 5. Reglas OpenWRT necesarias

> OpenWRT controla el tráfico entre VLANs. Los nodos en la VLAN 20 (misma subred que CT108) no necesitan ninguna regla especial. Los nodos en otras VLANs o en la red de gestión necesitan una regla de forwarding específica que permita el tráfico TCP al puerto 25 de CT108.

### Nodos en VLAN20 (10.1.1.32/27)

> Ya tienen acceso directo a CT108 — misma VLAN. No necesitan regla.

### Nodos en otras VLANs (VLAN30, VLAN40, VLAN50)

> Necesitan forwarding inter-VLAN. Verificar que existe forwarding hacia VLAN20 en OpenWRT:

```bash
uci show firewall | grep forwarding
```

### Nodos en red de gestión (192.168.3.0/24)

> `honeycos` y `honeycos-bk` están en la red de gestión del laboratorio (fuera de las VLANs internas). Necesitan una regla explícita en OpenWRT que autorice su tráfico hacia CT108 porque por defecto el firewall bloquea conexiones desde la red WAN hacia hosts internos.

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
uci commit firewall
service firewall restart
```

### Reglas activas en OpenWRT

| Nombre | Origen | Destino | Puerto |
|--------|--------|---------|--------|
| honeycos-to-postfix | 192.168.3.200 | 10.1.1.53 | 25 |
| honeycos-bk-to-postfix | 192.168.3.111 | 10.1.1.53 | 25 |

---

## 6. Ruta estática en honeycos-bk

> `honeycos-bk` tiene como gateway predeterminado el router doméstico (`192.168.3.1`), que no conoce la red interna `10.1.1.0/24`. Sin una ruta estática, los paquetes destinados a CT108 nunca llegarían: el router doméstico no sabría hacia dónde enviarlos. La ruta estática indica que para llegar a `10.1.1.0/24` hay que pasar por `192.168.3.201` (honeycos), que sí tiene conectividad con la red interna.

**Fichero:** `/etc/netplan/00-installer-config.yaml`

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
        addresses:
          - 8.8.8.8
          - 192.168.3.200
      routes:
        - to: 10.1.1.0/24
          via: 192.168.3.201
```

Para aplicar cambios:
```bash
sudo netplan apply
```

---

## 7. Cómo usar el correo en scripts

> Ejemplos listos para usar en scripts de bash. El comando `mail` usa Postfix como backend, por lo que el correo pasa automáticamente por el relay a CT108. `mailq` permite verificar que no hay correos atascados en cola tras el envío.

### Envío simple

```bash
echo "Mensaje" | mail -s "Asunto" telenecos9@gmail.com
```

### Envío con cuerpo multilínea

```bash
CUERPO=$(cat <<EOF
Linea 1
Linea 2
Linea 3
EOF
)

echo "$CUERPO" | mail -s "Asunto" telenecos9@gmail.com
```

### Verificar que se envió

```bash
# Ver cola (debe estar vacía si se envió)
mailq

# Ver log en CT108
ssh root@10.1.1.53 -p 2222 "tail -10 /var/log/syslog | grep postfix"
```

---

## 8. Troubleshooting

> Errores más frecuentes y su solución. En todos los casos, el log de CT108 (`/var/log/syslog | grep postfix`) es el punto de partida para diagnosticar qué está fallando.

### Error: SMTPUTF8 is required

> El mensaje contiene caracteres especiales (UTF-8) y CT108 no tiene soporte UTF-8 habilitado en SMTP. La solución es deshabilitar SMTPUTF8 en el nodo origen y evitar usar caracteres especiales en los scripts.

```bash
postconf -e "smtputf8_enable = no"
postfix reload
```

> Evitar usar caracteres especiales en los scripts: `╔══`, `──`, `✓`, `✗`, `→`. Usar en su lugar `===`, `---`, `[OK]`, `[ERROR]`, `->`.

### Error: Relay access denied

> CT108 rechaza el correo porque la IP del nodo origen no está en `mynetworks`. Solución: añadir la red del nodo a la lista de redes permitidas en CT108.

```bash
# En CT108 - añadir la red del nodo
postconf -e "mynetworks = 127.0.0.0/8, 10.1.1.0/24, 192.168.3.0/24"
postfix reload
```

### Error: Connection refused al puerto 25

> El nodo no puede establecer conexión TCP con CT108. Hay tres causas posibles: falta de ruta de red, regla de firewall ausente en OpenWRT, o Postfix caído en CT108.

1. Conectividad de red: `telnet 10.1.1.53 25`
2. Ruta estática (si es nodo en 192.168.3.0/24): `ip route show | grep 10.1.1`
3. Regla en OpenWRT: `uci show firewall | grep postfix`

### El correo no aparece en Gmail

> Gmail puede clasificar correos de servidores desconocidos como spam. Revisar la carpeta de spam antes de seguir investigando.

> Buscar en la carpeta de spam. Gmail puede filtrar correos de servidores desconocidos.

---

## 9. Configuración de alertas en Wazuh

> Wazuh tiene soporte nativo para envío de alertas por correo. Se configura en `ossec.conf` apuntando a CT108 como servidor SMTP. Con esto, cualquier alerta que supere el nivel configurado en Wazuh se envía automáticamente al correo destino sin necesidad de scripts adicionales.

Configuración en `/var/ossec/etc/ossec.conf` en VM202:

```xml
<global>
  <email_notification>yes</email_notification>
  <smtp_server>10.1.1.53</smtp_server>
  <email_from>alertas-wazuh@soc.local</email_from>
  <email_to>telenecos9@gmail.com</email_to>
</global>
```

---

*Documentación actualizada 2026-04-16*
