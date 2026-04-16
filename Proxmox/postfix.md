# Alertas por Correo — SOC honeycos

## 1. Arquitectura del sistema de correo

```
honeycos (192.168.3.200)         ---|
honeycos-bk (192.168.3.111)      ---|--> CT108 Postfix relay (10.1.1.53) --> Gmail (smtp.gmail.com:587)
wazuh-siem (10.1.1.67)           ---|
(cualquier nodo SOC)             ---|
```

El CT108 actúa como servidor de correo relay centralizado. Todos los nodos del SOC le envían sus alertas y CT108 las reenvía a Gmail usando una cuenta de aplicación.

---

## 2. CT108 — Servidor relay (Postfix)

# Guía completa: Postfix como Relay SMTP con Gmail (con comandos explicados)

## Objetivo

Configurar Postfix para enviar correos usando Gmail como relay SMTP, incluyendo todos los comandos necesarios y su explicación. El envío se realiza mediante `sendmail` (backend de Postfix).

---

# 1. Instalación de paquetes

```bash
apt update

Actualiza la lista de paquetes del sistema.

apt install postfix mailutils libsasl2-modules ca-certificates -y

Instala:

postfix: servidor de correo
mailutils: utilidades de correo (opcional, no imprescindible si usas sendmail)
libsasl2-modules: autenticación SMTP (necesario para Gmail)
ca-certificates: certificados TLS

Durante la instalación:

Tipo: Internet Site
Nombre: wazuh-relay.local (puede ser cualquiera)
2. Configuración de Postfix
nano /etc/postfix/main.cf

Edita el archivo principal de configuración.

Contenido:

myhostname = wazuh-relay.local
myorigin = /etc/mailname
mydestination = localhost, localhost.localdomain, localhost

relayhost = [smtp.gmail.com]:587

smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
smtp_sasl_security_options = noanonymous

smtp_use_tls = yes
smtp_tls_CAfile = /etc/ssl/certs/ca-certificates.crt
smtp_tls_security_level = encrypt
smtp_sasl_tls_security_options = noanonymous

mynetworks = 127.0.0.0/8, 10.1.1.0/27

inet_interfaces = all
inet_protocols = ipv4

Explicación:

relayhost: servidor SMTP de Gmail
smtp_sasl_auth_enable: activa autenticación
smtp_use_tls: usa cifrado TLS
mynetworks: redes que pueden usar el servidor
3. Crear contraseña de aplicación en Gmail

Para usar Gmail necesitas una contraseña especial.

Pasos:

Ir a:
https://myaccount.google.com/security
Activar:
Verificación en dos pasos (2FA)
Entrar en:
Contraseñas de aplicaciones
Crear nueva:
App: Correo
Dispositivo: Postfix
Obtendrás algo como:
abcd efgh ijkl mnop

Usar sin espacios:

abcdefghijklmnop
4. Configurar credenciales en Postfix
nano /etc/postfix/sasl_passwd

Contenido:

[smtp.gmail.com]:587 TUEMAIL@gmail.com:abcdefghijklmnop
5. Aplicar configuración
postmap /etc/postfix/sasl_passwd

Convierte el archivo en formato que Postfix puede usar (.db).

chmod 600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db

Protege las credenciales (solo root puede leerlas).

6. Reiniciar Postfix
systemctl restart postfix

Aplica todos los cambios.

7. Envío de correo (sendmail)
echo "Test correo" | sendmail -v tuemail@gmail.com

Explicación:

sendmail: interfaz estándar que usa Postfix para enviar correo
-v: modo verbose (muestra el proceso de envío)
8. Ver logs
journalctl -u postfix -f

Muestra lo que hace Postfix en tiempo real.

9. Comandos de diagnóstico
postqueue -p

Muestra correos en cola.

postconf

Muestra toda la configuración activa.

systemctl status postfix

Verifica el estado del servicio.

Seguridad básica
No usar contraseña normal de Gmail
Usar contraseña de aplicación
No exponer el puerto SMTP a internet
Limitar mynetworks
Resultado esperado
Correos enviados sin errores
Logs muestran status=sent
Emails recibidos correctamente
Resumen

Con estos pasos:

Postfix queda instalado
Se conecta a Gmail
sendmail utiliza Postfix como backend
El sistema puede enviar correos desde scripts y servicios

### Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 108 |
| Hostname | Correo |
| IP | 10.1.1.53/27 |
| VLAN | 20 — Servicios |
| OS | Debian 12 |
| Servicio | Postfix + rsyslog |

### Configuracion `/etc/postfix/main.cf`

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

```
[smtp.gmail.com]:587 usuario@gmail.com:PASSWORD_APP
```

> La contrasena debe ser una **contrasena de aplicacion** de Google (no la contrasena normal de Gmail). Se genera en: Cuenta Google -> Seguridad -> Verificacion en dos pasos -> Contrasenas de aplicacion.

### Comandos de gestion CT108

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

Para que cualquier nodo del SOC pueda enviar correo a traves de CT108 hay que seguir estos pasos:

### Paso 1 — Instalar paquetes

```bash
apt install -y postfix mailutils
```

Durante la instalacion seleccionar **"Internet Site"** y como hostname el nombre del nodo (ej: `wazuh-siem.soc.local`).

### Paso 2 — Configurar relay hacia CT108

```bash
postconf -e "relayhost = [10.1.1.53]:25"
postconf -e "inet_interfaces = loopback-only"
postconf -e "inet_protocols = ipv4"
postconf -e "smtputf8_enable = no"
postfix reload
```

> **IMPORTANTE:** `smtputf8_enable = no` es necesario para evitar errores de compatibilidad con CT108. Sin esto el correo rebota con el error `SMTPUTF8 is required, but was not offered`.

### Paso 3 — Verificar conectividad con CT108

```bash
telnet 10.1.1.53 25
```

Debe responder:
```
Connected to 10.1.1.53.
220 wazuh-relay.local ESMTP Postfix
```

Si no conecta, revisar las reglas de OpenWRT (ver seccion 5).

### Paso 4 — Probar envio

```bash
echo "Test desde $(hostname)" | mail -s "[SOC] Test correo" telenecos9@gmail.com
```

### Paso 5 — Verificar en CT108

```bash
tail -20 /var/log/syslog | grep postfix
```

Debe aparecer `status=sent`.

---

## 4. Nodos configurados

| Nodo | IP | Estado |
|------|----|--------|
| CT108 Correo | 10.1.1.53 | Servidor relay |
| VM202 wazuh-siem | 10.1.1.67 | Configurado — envia alertas Wazuh |
| honeycos | 192.168.3.200 | Configurado — envia alertas backup-sync |
| honeycos-bk | 192.168.3.111 | Configurado — envia alertas organizar-backups |

---

## 5. Reglas OpenWRT necesarias

Para que un nodo pueda llegar a CT108 (10.1.1.53:25) puede ser necesario abrir una regla en OpenWRT segun la VLAN de origen.

### Nodos en VLAN20 (10.1.1.32/27)
Ya tienen acceso directo a CT108 — misma VLAN. No necesitan regla.

### Nodos en otras VLANs (VLAN30, VLAN40, VLAN50)
Necesitan forwarding inter-VLAN. Verificar que existe forwarding hacia VLAN20 en OpenWRT:

```bash
uci show firewall | grep forwarding
```

### Nodos en red de gestion (192.168.3.0/24)
honeycos y honeycos-bk estan en la red de gestion. Necesitan regla especifica:

```bash
# Ejemplo para honeycos (192.168.3.200)
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

## 6. Ruta estatica en honeycos-bk

honeycos-bk tiene su gateway en `192.168.3.1` (router de casa) y no tiene ruta hacia `10.1.1.0/24` por defecto. Se ha configurado una ruta estatica persistente via netplan:

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

## 7. Como usar el correo en scripts

### Envio simple

```bash
echo "Mensaje" | mail -s "Asunto" telenecos9@gmail.com
```

### Envio con cuerpo multilinea

```bash
CUERPO=$(cat <<EOF
Linea 1
Linea 2
Linea 3
EOF
)

echo "$CUERPO" | mail -s "Asunto" telenecos9@gmail.com
```

### Verificar que se envio

```bash
# Ver cola (debe estar vacia si se envio)
mailq

# Ver log en CT108
ssh root@10.1.1.53 -p 2222 "tail -10 /var/log/syslog | grep postfix"
```

---

## 8. Troubleshooting

### Error: SMTPUTF8 is required

El mensaje contiene caracteres UTF-8 y CT108 no los soporta.

```bash
# Solucion: deshabilitar SMTPUTF8 en el nodo origen
postconf -e "smtputf8_enable = no"
postfix reload
```

Evitar usar caracteres especiales en los scripts: `╔══`, `──`, `✓`, `✗`, `→`. Usar en su lugar `===`, `---`, `[OK]`, `[ERROR]`, `->`.

### Error: Relay access denied

CT108 no acepta correo del nodo porque su IP no esta en `mynetworks`.

```bash
# En CT108 - anadir la red del nodo
postconf -e "mynetworks = 127.0.0.0/8, 10.1.1.0/24, 192.168.3.0/24"
postfix reload
```

### Error: Connection refused al puerto 25

El nodo no puede llegar a CT108. Verificar:

1. Conectividad de red: `telnet 10.1.1.53 25`
2. Ruta estatica (si es nodo en 192.168.3.0/24): `ip route show | grep 10.1.1`
3. Regla en OpenWRT: `uci show firewall | grep postfix`

### El correo no aparece en Gmail

Buscar en la carpeta de spam. Gmail puede filtrar correos de servidores desconocidos.

---

## 9. Configuracion de alertas en Wazuh

Wazuh usa CT108 como relay para sus alertas. Configuracion en `/var/ossec/etc/ossec.conf` en VM202:

```xml
<global>
  <email_notification>yes</email_notification>
  <smtp_server>10.1.1.53</smtp_server>
  <email_from>alertas-wazuh@soc.local</email_from>
  <email_to>telenecos9@gmail.com</email_to>
</global>
```

---

*Documentacion actualizada 2026-04-16*
