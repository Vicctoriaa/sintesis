# Wazuh SIEM — VM202

> SIEM principal del laboratorio SOC. Centraliza la recepción, correlación y visualización de eventos de seguridad de todos los nodos. Integrado con el sistema de automatización Ansible para ejecutar playbooks de respuesta ante alertas críticas.

---

## Arquitectura

```
honeycos (Proxmox)
└── VM202 — wazuh-siem (10.1.1.67 / VLAN30)
    ├── wazuh-indexer   :9200   (OpenSearch)
    ├── wazuh-manager   :1514 :1515
    ├── wazuh-dashboard :443
    └── filebeat

Agentes conectados:
├── CT100 — LDAP               (10.1.1.98  / VLAN40)
├── CT101 — Grafana            (10.1.1.66  / VLAN30)
├── CT103 — DNS / Ansible      (10.1.1.34  / VLAN20)  ← ejecutor playbooks
├── CT104 — SOAR               (10.1.1.37  / VLAN20)
├── CT105 — Nginx              (10.1.1.35  / VLAN20)
├── CT106 — Suricata           (10.1.1.36  / VLAN20)
├── CT109 — honeypot-dashboard (10.1.1.69  / VLAN30)
└── VM203 — Honeypot           (10.1.1.130 / VLAN50)
```

**Acceso al dashboard:** `https://192.168.3.200` (via PREROUTING → `10.1.1.67:443`)

---

## Datos de la VM

| Campo | Valor |
|-------|-------|
| VMID | 202 |
| Nombre | `wazuh-siem` |
| OS | Debian 12 Bookworm |
| RAM | 6 GB |
| Disco | 50 GB |
| IP | `10.1.1.67/27` |
| Gateway | `10.1.1.65` |
| DNS | `10.1.1.34` |
| VLAN | 30 — SOC |
| Versión Wazuh | 4.14.4 |

---

## Servicios

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

**`/etc/wazuh-dashboard/opensearch_dashboards.yml`:**

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

```bash
# Cambiar contraseña de un usuario
bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/wazuh-passwords-tool.sh \
  -u USUARIO -p NuevaPassword.123

# Cambiar todas las contraseñas
bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/wazuh-passwords-tool.sh -a
```

---

## Exposición del dashboard

```bash
iptables -t nat -A PREROUTING -i vmbr0 -p tcp --dport 443 -j DNAT --to-destination 10.1.1.67:443
iptables -t nat -A OUTPUT -p tcp -d 192.168.3.200 --dport 443 -j DNAT --to-destination 10.1.1.67:443
iptables -t nat -A POSTROUTING -d 10.1.1.67 -p tcp --dport 443 -j MASQUERADE
netfilter-persistent save
```

---

## Instalación de agentes

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

| ID | Nombre | IP | VLAN | OS | Estado |
|----|--------|-----|------|----|--------|
| 001 | soar-web | `10.1.1.37` | 20 | Debian 11 | active |
| 002 | nginx-proxy | `10.1.1.35` | 20 | Debian 12 | active |
| 003 | suricata-ids | `10.1.1.36` | 20 | Debian 12 | active |
| 004 | grafana-prometheus | `10.1.1.66` | 30 | Debian 11 | active |
| 005 | playbooks-dns | `10.1.1.34` | 20 | Debian 11 | active ← ejecutor Ansible |
| 006 | ldap | `10.1.1.98` | 40 | Ubuntu 22.04 | active |
| 007 | honeypot | `10.1.1.130` | 50 | Debian 12 | active |
| 008 | honeypot-dashboard | `10.1.1.69` | 30 | Debian 12 | active |

---

## Reglas personalizadas

### Honeypot — `honeypot_rules.xml`

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

| ID | Nivel | Descripción | Mail | Active Response |
|----|-------|-------------|:----:|-----------------|
| 100500 | 3 | Evento genérico | — | — |
| 100501 | 5 | Conexión detectada | — | — |
| 100502 | 8 | Intento de login | — | — |
| 100503 | 10 | Comando SSH ejecutado | Si | `collect-evidence.yml` |
| 100504 | 5 | Request HTTP/HTTPS | — | — |
| 100505 | 10 | Acceso a ruta sensible | — | — |
| 100506 | 8 | Acceso a fichero | — | — |
| 100507 | 14 | Brute force detectado | Si | `block-ip.yml` + `collect-evidence.yml` |
| 100508 | 12 | Evento crítico (ERROR) | Si | `block-ip.yml` + `isolate-host.yml` + `collect-evidence.yml` |

---

### Suricata — `suricata_soc_rules.xml`

**Fichero:** `/var/ossec/etc/rules/suricata_soc_rules.xml`

Extienden las reglas nativas de Wazuh para Suricata (86601) subiendo el nivel de alerta según severidad del evento IDS.

```xml
<group name="ids,suricata,soc,">

  <!-- Severidad 1 (crítica) — nivel 12 — dispara email -->
  <rule id="100600" level="12">
    <if_sid>86601</if_sid>
    <field name="alert.severity">^1$</field>
    <description>Suricata: alerta CRITICA (sev=1) - $(alert.signature)</description>
    <group>suricata,high_severity,</group>
  </rule>

  <!-- Severidad 2 (alta) — nivel 10 -->
  <rule id="100601" level="10">
    <if_sid>86601</if_sid>
    <field name="alert.severity">^2$</field>
    <description>Suricata: alerta ALTA (sev=2) - $(alert.signature)</description>
    <group>suricata,medium_severity,</group>
  </rule>

</group>
```

| ID | Nivel | Descripción | Mail |
|----|-------|-------------|:----:|
| 100600 | 12 | Suricata alerta crítica (sev=1) | Si |
| 100601 | 10 | Suricata alerta alta (sev=2) | — |

> La regla 100601 no dispara email (umbral en nivel 12) pero queda registrada en el dashboard para correlación.

---

## Listas CDB

**Directorio:** `/var/ossec/etc/lists/malicious-ioc/`

| Fichero | Descripción |
|---------|-------------|
| `malware-hashes` | Hashes de malware conocido |
| `malicious-ip` | IPs maliciosas conocidas |
| `malicious-domains` | Dominios maliciosos conocidos |

> Creadas el 2026-04-13. Pendiente poblar con IOCs reales.

---

## Configuración email

**`/var/ossec/etc/ossec.conf`:**

| Parámetro | Valor |
|-----------|-------|
| email_notification | yes |
| smtp_server | `10.1.1.53` (CT108 Postfix) |
| email_from | `alertas-wazuh@soc.local` |
| email_to | `telenecos9@gmail.com` |
| email_maxperhour | 12 |
| email_alert_level | 12 |

### Alertas específicas por regla

```xml
<email_alerts>
  <email_to>telenecos9@gmail.com</email_to>
  <rule_id>100508</rule_id>
</email_alerts>

<email_alerts>
  <email_to>telenecos9@gmail.com</email_to>
  <rule_id>100503</rule_id>
</email_alerts>

<email_alerts>
  <email_to>telenecos9@gmail.com</email_to>
  <rule_id>100600</rule_id>
</email_alerts>
```

### Resumen de alertas por email

| Regla | Origen | Evento | Nivel | Trigger |
|-------|--------|--------|-------|---------|
| 100507 | Honeypot | Brute force | 14 | nivel ≥ 12 |
| 100508 | Honeypot | Evento crítico | 12 | nivel ≥ 12 + regla específica |
| 100503 | Honeypot | Comando SSH ejecutado | 10 | regla específica |
| 100600 | Suricata | Alerta crítica sev=1 | 12 | nivel ≥ 12 + regla específica |

---

## Active Response — soc-trigger.sh

### Arquitectura

```
Wazuh manager (VM202)
  regla dispara active-response
       ↓
  envía orden al agente 005 (CT103)
       ↓
  wazuh-execd ejecuta soc-trigger.sh
       ↓
  ansible-playbook en CT103
       ↓
  acción sobre el nodo afectado
```

### Configuración en `ossec.conf` (VM202)

```xml
<!-- Comando trigger -->
<command>
  <name>soc-trigger</name>
  <executable>soc-trigger.sh</executable>
  <timeout_allowed>no</timeout_allowed>
</command>

<!-- HONEYPOT — Brute force (rule 100507) -->
<active-response>
  <command>soc-trigger</command>
  <location>defined-agent</location>
  <agent_id>005</agent_id>
  <rules_id>100507</rules_id>
  <timeout>0</timeout>
</active-response>

<!-- HONEYPOT — Evento crítico (rule 100508) -->
<active-response>
  <command>soc-trigger</command>
  <location>defined-agent</location>
  <agent_id>005</agent_id>
  <rules_id>100508</rules_id>
  <timeout>0</timeout>
</active-response>

<!-- HONEYPOT — Comando SSH ejecutado (rule 100503) -->
<active-response>
  <command>soc-trigger</command>
  <location>defined-agent</location>
  <agent_id>005</agent_id>
  <rules_id>100503</rules_id>
  <timeout>0</timeout>
</active-response>

<!-- SSH — Brute force en cualquier nodo -->
<active-response>
  <command>soc-trigger</command>
  <location>defined-agent</location>
  <agent_id>005</agent_id>
  <rules_id>5710,5712,5716,5720,5763</rules_id>
  <timeout>0</timeout>
</active-response>

<!-- FIM — Modificación de fichero crítico -->
<active-response>
  <command>soc-trigger</command>
  <location>defined-agent</location>
  <agent_id>005</agent_id>
  <rules_id>550,551,552,553,554</rules_id>
  <timeout>0</timeout>
</active-response>

<!-- COMPLIANCE — Paquetes desactualizados -->
<active-response>
  <command>soc-trigger</command>
  <location>defined-agent</location>
  <agent_id>005</agent_id>
  <rules_id>19101,19102,19104</rules_id>
  <timeout>0</timeout>
</active-response>
```

### Script soc-trigger.sh (CT103)

**Ubicación:** `/var/ossec/active-response/bin/soc-trigger.sh`  
**Permisos:** `root:wazuh 750`

Recibe el evento Wazuh como JSON por stdin, extrae `rule.id`, `agent.name` y `data.srcip`, y decide qué playbook ejecutar:

| Rule ID | Playbook(s) ejecutado(s) |
|---------|--------------------------|
| 100507 | `block-ip.yml` + `collect-evidence.yml` (honeypot) |
| 100508 | `block-ip.yml` + `isolate-host.yml` (vlan50) + `collect-evidence.yml` |
| 100503 | `collect-evidence.yml` (honeypot) |
| 5710, 5712, 5716, 5720, 5763 | `fail2ban.yml` (host afectado) |
| 550, 551, 552, 553, 554 | `backup-configs.yml` (host afectado) |
| 19101, 19102, 19104 | `update-all.yml` (host afectado) |

**Log:** `/var/log/soc-trigger.log`
