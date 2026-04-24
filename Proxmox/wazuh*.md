# Wazuh SIEM — SOC honeycos

> Wazuh es el núcleo del SIEM del laboratorio. Corre en una VM dedicada (VM202) con tres componentes integrados: el indexer (base de datos OpenSearch donde se almacenan los eventos), el manager (recibe y procesa los logs de los agentes) y el dashboard (interfaz web de visualización y análisis). Los agentes instalados en cada CT envían sus logs al manager en tiempo real.

---

## Arquitectura

> El manager centraliza todos los eventos de seguridad del laboratorio. Cada CT tiene un agente Wazuh que recoge logs locales (syslog, auth.log, eve.json de Suricata, etc.) y los envía al manager por el puerto 1514. El indexer los almacena y el dashboard los hace consultables. El acceso externo al dashboard pasa por la regla PREROUTING del host Proxmox (sin pasar por Nginx).

```
honeycos (Proxmox)
└── VM 202 — wazuh-siem (10.1.1.67 / VLAN30)
    ├── wazuh-indexer   :9200   (OpenSearch)
    ├── wazuh-manager   :1514 :1515
    ├── wazuh-dashboard :443
    └── filebeat

Agentes conectados:
├── CT100 — LDAP          (10.1.1.98  / VLAN40)
├── CT101 — Grafana       (10.1.1.66  / VLAN30)
├── CT103 — DNS           (10.1.1.34  / VLAN20)
├── CT104 — SOAR          (10.1.1.37  / VLAN20)
├── CT105 — Nginx         (10.1.1.35  / VLAN20)
├── CT106 — Suricata      (10.1.1.36  / VLAN20)
└── VM203 — Honeypot      (10.1.1.130 / VLAN50)
```

**Acceso al dashboard:** `https://192.168.3.200` (via PREROUTING → 10.1.1.67:443)

---

## VM 202 — wazuh-siem

> VM con recursos generosos comparada con los LXC del laboratorio. Wazuh (especialmente el indexer OpenSearch) es exigente en memoria y disco: 6 GB de RAM y 50 GB de disco son el mínimo recomendado para un entorno de laboratorio con varios agentes. Usa el DNS interno (CT103) para resolución de nombres.

| Campo | Valor |
|-------|-------|
| VMID | 202 |
| Nombre | wazuh-siem |
| OS | Debian GNU/Linux 12 (Bookworm) |
| RAM | 6 GB |
| Disco | 50 GB |
| IP | 10.1.1.67/27 |
| Gateway | 10.1.1.65 |
| DNS | 10.1.1.34 |
| VLAN | 30 — SOC |
| Versión Wazuh | 4.14.4 |

---

## Instalación

### Requisitos previos

> Actualización del sistema y `curl`, necesario para descargar el instalador oficial de Wazuh.

```bash
apt update && apt upgrade -y
apt install -y curl
```

### Descarga del instalador

> Wazuh proporciona un script de instalación all-in-one que gestiona automáticamente la instalación y configuración de los tres componentes (indexer, manager, dashboard) y la generación de certificados TLS entre ellos.

```bash
curl -sO https://packages.wazuh.com/4.11/wazuh-install.sh
curl -sO https://packages.wazuh.com/4.11/config.yml
```

### Configuración del nodo (config.yml)

> Define la topología del despliegue. Al ser una instalación all-in-one, los tres componentes (indexer, server/manager y dashboard) apuntan a la misma IP. En despliegues distribuidos cada componente iría en una IP diferente.

```yaml
nodes:
  indexer:
    - name: node-1
      ip: "10.1.1.67"
  server:
    - name: wazuh-1
      ip: "10.1.1.67"
  dashboard:
    - name: dashboard
      ip: "10.1.1.67"
```

### Instalación all-in-one

> El flag `-a` indica instalación all-in-one. El output se guarda en un log por si hay que revisar errores. El instalador genera certificados TLS, configura OpenSearch y deja todos los servicios activos al terminar.

```bash
bash wazuh-install.sh -a 2>&1 | tee /root/wazuh-install.log
```

### Actualización a 4.14.4

> Actualización de los paquetes manteniendo la configuración existente. Al responder `N` a las preguntas de configuración se conservan los ficheros actuales (`ossec.conf`, reglas personalizadas, etc.) sin sobrescribirlos con los valores por defecto del paquete nuevo.

```bash
apt update
apt install -y wazuh-manager wazuh-indexer wazuh-dashboard
# Responder N a las preguntas de configuración para conservar los ficheros actuales
```

---

## Servicios

> Los cuatro servicios deben estar activos simultáneamente para que Wazuh funcione correctamente. Si el indexer cae, el manager no puede almacenar eventos aunque los siga recibiendo. Filebeat es el encargado de transportar los logs procesados por el manager hacia el indexer.

| Servicio | Puerto | Descripción |
|---------|--------|-------------|
| wazuh-indexer | 9200 | Base de datos OpenSearch |
| wazuh-manager | 1514 | Comunicación con agentes |
| wazuh-manager | 1515 | Enrollment de agentes |
| wazuh-dashboard | 443 | Interfaz web |
| filebeat | — | Envío de logs al indexer |

```bash
systemctl status wazuh-manager wazuh-indexer wazuh-dashboard filebeat --no-pager
```

---

## Configuración del dashboard

### Fichero principal

> Configuración del dashboard Wazuh (basado en OpenSearch Dashboards). Escucha en todas las interfaces (`0.0.0.0`) en el puerto 443 con TLS habilitado, usando los certificados generados durante la instalación. `multitenancy` deshabilitado simplifica la gestión en un entorno de laboratorio con un único usuario.

`/etc/wazuh-dashboard/opensearch_dashboards.yml`

```yaml
server.host: 0.0.0.0
server.port: 443
opensearch.hosts: https://127.0.0.1:9200
opensearch.ssl.verificationMode: certificate
opensearch_security.multitenancy.enabled: false
opensearch_security.readonly_mode.roles: ["kibana_read_only"]
server.ssl.enabled: true
server.ssl.key: "/etc/wazuh-dashboard/certs/wazuh-dashboard-key.pem"
server.ssl.certificate: "/etc/wazuh-dashboard/certs/wazuh-dashboard.pem"
opensearch.ssl.certificateAuthorities: ["/etc/wazuh-dashboard/certs/root-ca.pem"]
uiSettings.overrides.defaultRoute: /app/wz-home
opensearch_security.cookie.secure: true
```

---

## Gestión de contraseñas

> Wazuh incluye una herramienta propia para cambiar contraseñas de los usuarios del indexer (OpenSearch). No se deben cambiar directamente en la base de datos; hay que usar este script para que también actualice las referencias en los ficheros de configuración de los otros componentes.

```bash
# Cambiar contraseña de un usuario específico
bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/wazuh-passwords-tool.sh \
  -u USUARIO -p NuevaPassword.123

# Cambiar todas las contraseñas
bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/wazuh-passwords-tool.sh -a
```

---

## Exposición del dashboard al exterior

> Reglas iptables en el host Proxmox que redirigen el tráfico HTTPS externo directamente a Wazuh, sin pasar por el Nginx del CT105. Wazuh gestiona su propio TLS, por lo que un proxy adicional complicaría la cadena de certificados. `MASQUERADE` es necesario para que el tráfico de retorno funcione correctamente.

```bash
iptables -t nat -A PREROUTING -i vmbr0 -p tcp --dport 443 -j DNAT --to-destination 10.1.1.67:443
iptables -t nat -A OUTPUT -p tcp -d 192.168.3.200 --dport 443 -j DNAT --to-destination 10.1.1.67:443
iptables -t nat -A POSTROUTING -d 10.1.1.67 -p tcp --dport 443 -j MASQUERADE
netfilter-persistent save
```

---

## Instalación de agentes

> Proceso estándar para añadir un nuevo CT al SIEM. Las variables de entorno `WAZUH_MANAGER` y `WAZUH_AGENT_NAME` preconfiguran el agente durante la instalación, evitando editar `ossec.conf` manualmente. El agente contacta al manager por el puerto 1515 para el enrollment inicial y luego usa el 1514 para el envío continuo de eventos.

```bash
# Añadir repositorio
apt install -y gnupg curl
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --no-default-keyring \
  --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import
chmod 644 /usr/share/keyrings/wazuh.gpg
echo 'deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main' \
  > /etc/apt/sources.list.d/wazuh.list
apt update

# Instalar agente
WAZUH_MANAGER='10.1.1.67' WAZUH_AGENT_NAME='nombre-agente' apt install -y wazuh-agent

# Activar y arrancar
systemctl daemon-reload
systemctl enable wazuh-agent
systemctl start wazuh-agent
```

---

## Agentes desplegados

> Estado actual de todos los agentes Wazuh en el laboratorio. Todos están en estado `active`, lo que significa que están enviando heartbeats y eventos al manager. El agente del Honeypot (007) fue el último en añadirse.

| ID | Nombre | IP | VLAN | OS | Estado |
|----|--------|-----|------|----|--------|
| 001 | soar-web | 10.1.1.37 | 20 | Debian 11 | active |
| 002 | nginx-proxy | 10.1.1.35 | 20 | Debian 12 | active |
| 003 | suricata-ids | 10.1.1.36 | 20 | Debian 12 | active |
| 004 | grafana-prometheus | 10.1.1.66 | 30 | Debian 11 | active |
| 005 | playbooks-dns | 10.1.1.34 | 20 | Debian 11 | active |
| 006 | ldap | 10.1.1.98 | 40 | Ubuntu 22.04 | active |
| 007 | honeypot | 10.1.1.130 | 50 | Debian 12 | active ✅ |

---

## Reglas personalizadas

### Honeypot (100500-100508)

> Las reglas de Wazuh definen cómo clasificar y priorizar los eventos. El nivel determina la gravedad (1-15) y si se envía alerta por correo (por defecto a partir de nivel 12 o si está explícitamente configurado). Estas reglas están en el rango 100000+ reservado para reglas personalizadas de usuario, evitando conflictos con las reglas built-in de Wazuh. La regla base (100500) detecta cualquier evento del honeypot; el resto hereda de ella usando `if_sid`.

**Fichero:** `/var/ossec/etc/rules/honeypot_rules.xml`

```xml
<group name="honeypot,">

  <rule id="100500" level="3">
    <decoded_as>json</decoded_as>
    <match>"hostname": "honeypot"</match>
    <description>Honeypot: evento detectado</description>
    <group>honeypot,</group>
  </rule>

  <rule id="100501" level="5">
    <if_sid>100500</if_sid>
    <match>"action": "connection"</match>
    <description>Honeypot: conexion detectada</description>
    <group>honeypot,connection,</group>
  </rule>

  <rule id="100502" level="8">
    <if_sid>100500</if_sid>
    <match>"action": "login_attempt"</match>
    <description>Honeypot: intento de login</description>
    <group>honeypot,authentication_failed,</group>
  </rule>

  <rule id="100503" level="10">
    <if_sid>100500</if_sid>
    <match>"action": "command"</match>
    <description>Honeypot: comando ejecutado SSH</description>
    <group>honeypot,ssh,command,</group>
  </rule>

  <rule id="100504" level="5">
    <if_sid>100500</if_sid>
    <match>"action": "request"</match>
    <description>Honeypot: request HTTP/HTTPS</description>
    <group>honeypot,http,</group>
  </rule>

  <rule id="100505" level="10">
    <if_sid>100504</if_sid>
    <match>"path": "/.env"</match>
    <description>Honeypot: acceso a ruta sensible</description>
    <group>honeypot,http,suspicious,</group>
  </rule>

  <rule id="100506" level="8">
    <if_sid>100500</if_sid>
    <match>"action": "file_access"</match>
    <description>Honeypot: acceso a fichero</description>
    <group>honeypot,file_access,</group>
  </rule>

  <rule id="100507" level="14">
    <if_sid>100500</if_sid>
    <match>"action": "brute_force"</match>
    <description>Honeypot: BRUTE FORCE detectado</description>
    <group>honeypot,brute_force,authentication_failures,</group>
  </rule>

  <rule id="100508" level="12">
    <if_sid>100500</if_sid>
    <match>"level": "ERROR"</match>
    <description>Honeypot: evento critico</description>
    <group>honeypot,high_severity,</group>
  </rule>

</group>
```

> Resumen de niveles y comportamiento de alertas. Solo el brute force (nivel 14) genera notificación por correo, ya que es el evento más crítico y accionable del honeypot.

| ID | Nivel | Descripcion | Mail |
|----|-------|-------------|------|
| 100500 | 3 | Evento genérico | No |
| 100501 | 5 | Conexión detectada | No |
| 100502 | 8 | Intento de login | No |
| 100503 | 10 | Comando SSH ejecutado | No |
| 100504 | 5 | Request HTTP/HTTPS | No |
| 100505 | 10 | Acceso a ruta sensible | No |
| 100506 | 8 | Acceso a fichero | No |
| 100507 | 14 | Brute force detectado | **Sí** |
| 100508 | 12 | Evento crítico (ERROR) | No |

---

## Listas CDB

> Las listas CDB (Constant Database) permiten a Wazuh hacer lookups rápidos contra conjuntos de IOCs (Indicators of Compromise): hashes de malware, IPs maliciosas y dominios. Cuando un evento contiene un valor que aparece en estas listas, Wazuh puede aplicar reglas específicas para generar alertas de alta severidad. Actualmente son placeholders pendientes de poblar con IOCs reales.

Directorio: `/var/ossec/etc/lists/malicious-ioc/`

| Fichero | Descripción |
|---------|-------------|
| malware-hashes | Hashes de malware conocido |
| malicious-ip | IPs maliciosas conocidas |
| malicious-domains | Dominios maliciosos conocidos |

> Listas creadas el 2026-04-13. Actualmente contienen entrada placeholder. Pendiente poblar con IOCs reales.

---

## Configuración email (ossec.conf)

> Wazuh envía alertas por correo usando CT108 como relay SMTP. El parámetro `email_notification: yes` activa el sistema de alertas. Por defecto, Wazuh envía correo para eventos a partir del nivel 12 (configurable con `email_alert_level`). El `email_from` no necesita ser una dirección real, solo es el remitente que aparecerá en el correo.

| Parámetro | Valor |
|-----------|-------|
| email_notification | yes |
| smtp_server | 10.1.1.53 (CT108 Postfix) |
| email_from | alertas-wazuh@soc.local |
| email_to | telenecos9@gmail.com |

---

## Registro DNS

> Wazuh tiene su propio registro A en el DNS interno, lo que permite acceder al dashboard usando `https://wazuh.soc.local` desde cualquier CT del laboratorio en lugar de tener que recordar la IP.

```
wazuh    IN  A   10.1.1.67
```

Acceso interno: `https://wazuh.soc.local`

---

## Comandos útiles

> Referencia rápida para las operaciones más habituales. `wazuh-logtest` es especialmente útil durante el desarrollo de reglas: permite enviar una línea de log de prueba y ver qué reglas y decoders la procesan, sin necesidad de generar el evento real. `wazuh-analysisd -t` valida la sintaxis de todas las reglas antes de reiniciar el manager.

```bash
# Ver agentes conectados
/var/ossec/bin/agent_control -l

# Testear reglas y decoders
/var/ossec/bin/wazuh-logtest

# Ver logs del manager
tail -f /var/ossec/logs/ossec.log

# Reiniciar todos los servicios
systemctl restart wazuh-indexer wazuh-manager wazuh-dashboard filebeat

# Verificar salud del indexer
curl -sk -u admin:PASSWORD https://localhost:9200/_cluster/health | python3 -m json.tool

# Verificar sintaxis de reglas
/var/ossec/bin/wazuh-analysisd -t 2>&1 | tail -20
```

---

*Wazuh actualizado 2026-04-13*
