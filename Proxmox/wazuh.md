# Wazuh SIEM — SOC honeycos

## Arquitectura

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
└── CT106 — Suricata      (10.1.1.36  / VLAN20)
```

**Acceso al dashboard:** `https://192.168.3.200` (via PREROUTING → 10.1.1.67:443)

---

## VM 202 — wazuh-siem

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

```bash
apt update && apt upgrade -y
apt install -y curl
```

### Descarga del instalador

```bash
curl -sO https://packages.wazuh.com/4.11/wazuh-install.sh
curl -sO https://packages.wazuh.com/4.11/config.yml
```

### Configuración del nodo (config.yml)

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

```bash
bash wazuh-install.sh -a 2>&1 | tee /root/wazuh-install.log
```

El instalador instala y configura automáticamente todos los componentes: wazuh-indexer, wazuh-manager, wazuh-dashboard y filebeat. Al finalizar muestra las credenciales de acceso — guardarlas en lugar seguro.

### Actualización a 4.14.4

Tras la instalación inicial en 4.11.2 fue necesario actualizar a 4.14.4 para compatibilidad con los agentes:

```bash
apt update
apt install -y wazuh-manager wazuh-indexer wazuh-dashboard
# Responder N a las preguntas de configuración para conservar los ficheros actuales
```

---

## Servicios

| Servicio | Puerto | Descripción |
|---------|--------|-------------|
| wazuh-indexer | 9200 | Base de datos OpenSearch |
| wazuh-manager | 1514 | Comunicación con agentes |
| wazuh-manager | 1515 | Enrollment de agentes |
| wazuh-dashboard | 443 | Interfaz web |
| filebeat | — | Envío de logs al indexer |

### Verificar estado de servicios

```bash
systemctl status wazuh-manager wazuh-indexer wazuh-dashboard filebeat --no-pager
```

### Verificar salud del indexer

```bash
curl -sk -u admin:PASSWORD https://localhost:9200/_cluster/health | python3 -m json.tool
```

---

## Configuración del dashboard

### Fichero principal

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

### Credenciales del indexer (keystore)

Las credenciales de `kibanaserver` se almacenan en el keystore del dashboard:

```bash
# Ver entradas del keystore
/usr/share/wazuh-dashboard/bin/opensearch-dashboards-keystore list --allow-root

# Actualizar contraseña si es necesario
echo "nueva_password" | /usr/share/wazuh-dashboard/bin/opensearch-dashboards-keystore add opensearch.password --allow-root --stdin
```

### Configuración de la API (wazuh.yml)

`/usr/share/wazuh-dashboard/data/wazuh/config/wazuh.yml`

```yaml
hosts:
  - default:
      url: https://127.0.0.1
      port: 55000
      username: wazuh-wui
      password: "PASSWORD_WAZUH_WUI"
      run_as: false
```

---

## Gestión de contraseñas

Para cambiar contraseñas de usuarios del indexer usar el script oficial:

```bash
# Cambiar contraseña de un usuario específico
bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/wazuh-passwords-tool.sh \
  -u USUARIO -p NuevaPassword.123

# Cambiar todas las contraseñas
bash /usr/share/wazuh-indexer/plugins/opensearch-security/tools/wazuh-passwords-tool.sh -a
```

Requisitos de contraseña: entre 8 y 64 caracteres, con mayúsculas, minúsculas, números y al menos un símbolo de `.*+?-`.

---

## Exposición del dashboard al exterior

### Reglas iptables en el host Proxmox

```bash
# PREROUTING — tráfico externo al dashboard
iptables -t nat -A PREROUTING -i vmbr0 -p tcp --dport 443 -j DNAT --to-destination 10.1.1.67:443

# OUTPUT — tráfico desde el propio host
iptables -t nat -A OUTPUT -p tcp -d 192.168.3.200 --dport 443 -j DNAT --to-destination 10.1.1.67:443

# MASQUERADE — retorno correcto del tráfico
iptables -t nat -A POSTROUTING -d 10.1.1.67 -p tcp --dport 443 -j MASQUERADE

# Persistir
netfilter-persistent save
```

### Regla de firewall OpenWRT

La regla `Allow-Proxmox-Monitoring` (rule[9]) incluye los puertos necesarios:

```
22 53 80 443 1514 1515 3000 8080 9090 9100 9917 9119
```

Además se añadió forwarding `vlan40 → vlan30` para que CT100 (LDAP en VLAN40) pueda conectar con el manager en VLAN30.

---

## Instalación de agentes

### Comando de instalación (para CTs Debian/Ubuntu)

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

### Cambiar IP del manager en agentes existentes

```bash
sed -i 's/<address>.*<\/address>/<address>10.1.1.67<\/address>/' /var/ossec/etc/ossec.conf
systemctl restart wazuh-agent
```

---

## Agentes desplegados

| ID | Nombre | IP | VLAN | OS | Estado |
|----|--------|-----|------|----|--------|
| 001 | soar-web | 10.1.1.37 | 20 | Debian 11 | active |
| 002 | nginx-proxy | 10.1.1.35 | 20 | Debian 12 | active |
| 003 | suricata-ids | 10.1.1.36 | 20 | Debian 12 | active |
| 004 | grafana-prometheus | 10.1.1.66 | 30 | Debian 11 | active |
| 005 | playbooks-dns | 10.1.1.34 | 20 | Debian 11 | active |
| 006 | ldap | 10.1.1.98 | 40 | Ubuntu 22.04 | active |

---

## Registro DNS

Registro añadido en CT103 (Bind9):

```
wazuh    IN  A   10.1.1.67
```

Acceso interno: `https://wazuh.soc.local`

---

## Comandos útiles

```bash
# Ver agentes conectados desde el manager
/var/ossec/bin/agent_control -l

# Ver logs del manager
tail -f /var/ossec/logs/ossec.log

# Ver logs de un agente
tail -f /var/ossec/logs/ossec.log  # dentro del CT

# Reiniciar todos los servicios
systemctl restart wazuh-indexer wazuh-manager wazuh-dashboard filebeat

# Ver estado del cluster
curl -sk -u admin:PASSWORD https://localhost:9200/_cluster/health | python3 -m json.tool
```
