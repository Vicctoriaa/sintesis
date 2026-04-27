# Ansible Playbooks — CT103

> Nodo de control Ansible del SOC. Centraliza la automatización de mantenimiento, backup y respuesta a incidentes. Se integra con Wazuh y Suricata para ejecutar playbooks de forma reactiva ante alertas.

**Nodo de control:** CT103 `playbooks-dns` — `10.1.1.34`

---

## Estructura de directorios

```
/etc/ansible/
├── inventories/
│   └── soc.ini
├── group_vars/
├── host_vars/
├── roles/
└── playbooks/
    ├── mantenimiento/
    │   ├── update-all.yml
    │   ├── harden-ssh.yml
    │   └── fail2ban.yml
    ├── backup/
    │   └── backup-configs.yml
    ├── seguridad/
    │   └── usuarios.yml
    └── incidentes/
        ├── isolate-host.yml
        ├── unisolate-host.yml
        ├── collect-evidence.yml
        └── block-ip.yml
```

---

## Inventario — `/etc/ansible/inventories/soc.ini`

```ini
[soc]
grafana-prometheus  ansible_host=10.1.1.66  ansible_port=2222
wazuh-siem          ansible_host=10.1.1.67  ansible_port=2222
homepage            ansible_host=10.1.1.68  ansible_port=2222
honeypot-dashboard  ansible_host=10.1.1.69  ansible_port=2222

[servicios]
playbooks-dns       ansible_host=10.1.1.34  ansible_connection=local
nginx-proxy         ansible_host=10.1.1.35  ansible_port=2222
suricata-ids        ansible_host=10.1.1.36  ansible_port=2222
soar-web            ansible_host=10.1.1.37  ansible_port=2222
correo              ansible_host=10.1.1.53  ansible_port=2222
vaultwarden         ansible_host=10.1.1.80  ansible_port=2222

[produccion]
ldap                ansible_host=10.1.1.98  ansible_port=2222

[firewall]
openwrt-fw          ansible_host=10.1.1.1  ansible_python_interpreter=/bin/false  ansible_shell_type=sh

[honey]
honeypot  ansible_host=10.1.1.130  ansible_port=2222

[linux:children]
soc
servicios
produccion

[all:vars]
ansible_user=root
ansible_python_interpreter=/usr/bin/python3
ansible_port=2222
```

---

## Requisitos

| Requisito | Detalle |
|-----------|---------|
| Ansible | 2.10.17 instalado en CT103 |
| Python | 3.x en todos los nodos |
| SSH | Puerto 2222, acceso por clave desde CT103 |
| Usuario | root con clave pública de ansible@soc.local (`id_ed25519`) |
| DNS | soc.local resolviendo correctamente |
| Honeypot | ProxyJump via honeycos (192.168.3.200) — ver sección SSH |

### Comando base de ejecución

```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini playbooks/<categoria>/<playbook>.yml
```

### Verificar conectividad con todos los nodos

```bash
ansible -i /etc/ansible/inventories/soc.ini linux -m ping
```

---

## CATEGORÍA 1 — Mantenimiento

### 1.1 `update-all.yml` — Actualización de paquetes

**Qué hace:** Actualiza apt en los nodos objetivo. En modo reactivo actúa solo sobre el host afectado. En modo manual actúa sobre todo el grupo `linux`. Detecta paquetes pendientes antes de actualizar y registra el resultado en `soc-remediation.log`.

**Ejecución manual (todos los nodos):**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/update-all.yml
```

**Ejecución reactiva (nodo específico):**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/update-all.yml \
  -e target_hosts=<hostname>
```

**Disparador automático:** Wazuh rules 19101, 19102, 19104 (paquetes desactualizados / CVEs)

```yaml
---
- name: Actualizar contenedores Linux (reactivo o manual)
  hosts: "{{ target_hosts | default('linux') }}"
  become: yes
  serial: 1

  tasks:
    - name: Verificar conectividad
      ping:

    - name: Detectar paquetes pendientes de actualizacion
      shell: apt list --upgradable 2>/dev/null | grep -v "^Listing"
      register: upgrades
      changed_when: false
      failed_when: false

    - name: Actualizar lista de paquetes
      apt:
        update_cache: yes
        cache_valid_time: 0
      when: upgrades.stdout != ""

    - name: Actualizar todos los paquetes
      apt:
        upgrade: dist
        autoremove: yes
        autoclean: yes
      when: upgrades.stdout != ""

    - name: Revalidar estado tras parcheo
      shell: apt list --upgradable 2>/dev/null | grep -v "^Listing"
      register: upgrades_after
      changed_when: false
      failed_when: false

    - name: Comprobar si requiere reinicio
      stat:
        path: /var/run/reboot-required
      register: reboot_required

    - name: Notificar si hay reinicio pendiente
      debug:
        msg: "{{ inventory_hostname }} requiere reinicio tras parcheo"
      when: reboot_required.stat.exists

    - name: Registrar parcheo aplicado en SOC log
      lineinfile:
        path: /var/log/soc-remediation.log
        line: "{{ ansible_date_time.iso8601 }} - PATCHING DONE: {{ inventory_hostname }} — sistema actualizado"
        create: yes
      delegate_to: playbooks-dns
      when: upgrades.stdout != ""

    - name: Registrar reinicio pendiente en SOC log
      lineinfile:
        path: /var/log/soc-remediation.log
        line: "{{ ansible_date_time.iso8601 }} - REBOOT REQUIRED: {{ inventory_hostname }}"
        create: yes
      delegate_to: playbooks-dns
      when: reboot_required.stat.exists

    - name: Registrar sistema ya actualizado
      lineinfile:
        path: /var/log/soc-remediation.log
        line: "{{ ansible_date_time.iso8601 }} - PATCHING SKIP: {{ inventory_hostname }} — sin paquetes pendientes"
        create: yes
      delegate_to: playbooks-dns
      when: upgrades.stdout == ""
```

---

### 1.2 `harden-ssh.yml` — Hardening SSH

**Qué hace:** Aplica configuración segura SSH en todos los nodos: puerto 2222, sin password, MaxAuthTries 3, desactiva ssh.socket para evitar conflictos.

> NOTA: Esta configuración ya está aplicada en toda la infraestructura. Usar este playbook solo al incorporar nodos nuevos, no como respuesta reactiva automática.

**Ejecución:**
```bash
# Todos los nodos
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/harden-ssh.yml

# Un nodo específico
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/harden-ssh.yml \
  --limit nginx-proxy
```

> IMPORTANTE: Ejecutar primero en un nodo con `--check` antes de aplicar a todos.

```yaml
---
- name: Hardening SSH en todos los contenedores
  hosts: linux
  become: yes
  vars:
    ssh_port: 2222
  tasks:
    - name: Configurar sshd_config
      lineinfile:
        path: /etc/ssh/sshd_config
        regexp: "{{ item.regexp }}"
        line: "{{ item.line }}"
        state: present
      loop:
        - { regexp: '^#?PermitRootLogin',        line: 'PermitRootLogin prohibit-password' }
        - { regexp: '^#?PasswordAuthentication', line: 'PasswordAuthentication no' }
        - { regexp: '^#?PubkeyAuthentication',   line: 'PubkeyAuthentication yes' }
        - { regexp: '^#?MaxAuthTries',           line: 'MaxAuthTries 3' }
        - { regexp: '^#?LoginGraceTime',         line: 'LoginGraceTime 20' }
        - { regexp: '^#?X11Forwarding',          line: 'X11Forwarding no' }
        - { regexp: '^#?Port ',                  line: 'Port {{ ssh_port }}' }

    - name: Desactivar ssh.socket para evitar conflicto con el puerto
      systemd:
        name: ssh.socket
        state: stopped
        enabled: no
      ignore_errors: yes

    - name: Asegurar que sshd esta habilitado como servicio
      systemd:
        name: ssh
        enabled: yes

    - name: Reiniciar SSH
      service:
        name: ssh
        state: restarted
```

---

### 1.3 `fail2ban.yml` — Instalación y configuración Fail2ban

**Qué hace:** Instala fail2ban en los nodos objetivo, configura jail SSH con ban de 1 hora tras 3 intentos fallidos en el puerto 2222. En modo reactivo actúa solo sobre el host afectado. Verifica el estado del jail al final y registra en `soc-remediation.log`.

**Ejecución manual (todos los nodos):**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/fail2ban.yml
```

**Ejecución reactiva (nodo específico):**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/fail2ban.yml \
  -e target_hosts=<hostname>
```

**Disparador automático:** Wazuh rules 5710, 5712, 5716, 5720, 5763 (brute force SSH)

```yaml
---
- name: Instalar y configurar Fail2ban (reactivo o manual)
  hosts: "{{ target_hosts | default('linux') }}"
  become: yes
  serial: 1

  vars:
    ssh_port: 2222

  tasks:
    - name: Verificar conectividad
      ping:

    - name: Instalar fail2ban si no esta presente
      apt:
        name: fail2ban
        state: present
        update_cache: yes

    - name: Configurar jail SSH
      copy:
        dest: /etc/fail2ban/jail.local
        backup: yes
        content: |
          [DEFAULT]
          bantime  = 3600
          findtime = 600
          maxretry = 3
          backend  = systemd

          [sshd]
          enabled  = true
          port     = {{ ssh_port }}
          logpath  = %(sshd_log)s

    - name: Habilitar y arrancar fail2ban
      service:
        name: fail2ban
        state: started
        enabled: yes

    - name: Reiniciar fail2ban para aplicar configuracion
      service:
        name: fail2ban
        state: restarted

    - name: Verificar estado del jail SSH
      command: fail2ban-client status sshd
      register: jail_status
      changed_when: false
      failed_when: false

    - name: Mostrar estado del jail
      debug:
        msg: "{{ jail_status.stdout }}"
      when: jail_status.rc == 0

    - name: Registrar activacion en SOC log
      lineinfile:
        path: /var/log/soc-remediation.log
        line: "{{ ansible_date_time.iso8601 }} - FAIL2BAN ACTIVE: {{ inventory_hostname }} — SSH jail activo puerto {{ ssh_port }}"
        create: yes
      delegate_to: playbooks-dns
```

---

## CATEGORÍA 2 — Backup

### 2.1 `backup-configs.yml` — Backup de configuraciones críticas

**Qué hace:** Recoge ficheros de configuración críticos de todos los nodos y los envía a honeycos-bk (`/backups/configs/`). En modo manual (cron dominical) usa la fecha como sufijo. En modo reactivo (alerta FIM) usa fecha+hora para no sobreescribir el backup programado.

**Automatización (crontab CT103):**
```
0 4 * * 0 ansible-playbook /etc/ansible/playbooks/backup/backup-configs.yml -i /etc/ansible/inventories/soc.ini
```

**Ejecución manual:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/backup/backup-configs.yml
```

**Ejecución reactiva (nodo específico):**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/backup/backup-configs.yml \
  -e target_hosts=<hostname>
```

**Disparador automático:** Wazuh rules 550, 551, 552, 553, 554 (FIM — modificación de fichero crítico)

**Ficheros que recoge por nodo:**

| Categoría | Ficheros |
|-----------|---------|
| SSH y seguridad | `/etc/ssh/sshd_config`, `/etc/fail2ban/jail.local` |
| Ansible (CT103) | Todos los playbooks, inventario |
| DNS (CT103) | `named.conf.*`, zonas `db.soc.local`, `db.10.1.1` |
| Nginx (CT105) | `nginx.conf`, virtual hosts |
| Suricata (CT106) | `suricata.yaml`, `local.rules` |
| Prometheus (CT101) | `prometheus.yml` |
| Grafana (CT101) | `docker-compose.yml` |
| Homepage (CT107) | `docker-compose.yml`, configs |
| Vaultwarden (CT102) | `docker-compose.yml` |
| Wazuh (VM202) | `ossec.conf`, `honeypot_rules.xml`, `local_decoder.xml` |
| Postfix (CT108) | `main.cf`, `sasl_passwd` |

---

## CATEGORÍA 3 — Respuesta a Incidentes

### 3.1 `usuarios.yml` — Gestión centralizada de usuarios

**Qué hace:** Crea, elimina o cambia la contraseña de usuarios en uno, varios o todos los nodos del SOC. Registra todas las operaciones en el log de incidentes.

> NOTA: Este playbook es exclusivamente manual. No está automatizado.

**Variables:**

| Variable | Valores | Descripción |
|----------|---------|-------------|
| `action` | `create`, `delete`, `change_password` | Operación a realizar |
| `username` | nombre del usuario | Usuario sobre el que operar |
| `password` | contraseña | Requerido para `create` y `change_password` |
| `target_hosts` | `linux`, nombre nodo, `nodo1,nodo2` | Hosts donde aplicar (default: `linux`) |

**Ejecución:**
```bash
# Crear usuario en todos los nodos
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/usuarios.yml \
  -e action=create -e username=operador1 -e password=MiPassword123

# Crear usuario en un nodo específico
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/usuarios.yml \
  -e target_hosts=soar-web -e action=create -e username=operador1 -e password=MiPassword123

# Eliminar usuario
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/usuarios.yml \
  -e action=delete -e username=operador1

# Cambiar contraseña
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/usuarios.yml \
  -e action=change_password -e username=operador1 -e password=NuevaPassword123
```

---

## CATEGORÍA 4 — Respuesta a Incidentes

### 4.1 `isolate-host.yml` — Aislamiento de VLAN

**Qué hace:** Ante un incidente, añade una regla REJECT en OpenWRT para bloquear todo el tráfico de una VLAN. Registra el aislamiento en el log de incidentes.

**Disparador automático:** Wazuh rule 100508 (evento crítico honeypot) / Suricata sev=1 desde IP interna / Suricata ET SCAN desde VLAN interna

**Ejecución manual:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/incidentes/isolate-host.yml \
  -e target_vlan=vlan20
```

> ATENCIÓN: Solo ejecutar en caso de incidente real. Corta todas las comunicaciones de la VLAN especificada.

**VLANs disponibles:** `vlan10` (DMZ), `vlan20` (Servicios), `vlan30` (SOC), `vlan40` (Producción), `vlan50` (Honeypot)

```yaml
---
- name: Aislar VLAN comprometida en OpenWRT
  hosts: localhost
  vars:
    target_vlan: ""
    openwrt_host: "10.1.1.1"
    openwrt_port: "2222"
  tasks:
    - name: Verificar que se ha especificado una VLAN
      fail:
        msg: "Debes especificar target_vlan. Ejemplo: -e target_vlan=vlan20"
      when: target_vlan == ""

    - name: Añadir regla REJECT para la VLAN en OpenWRT
      command: >
        ssh -p {{ openwrt_port }} root@{{ openwrt_host }}
        "uci add firewall rule;
         uci set firewall.@rule[-1].name='ISOLATE-{{ target_vlan }}';
         uci set firewall.@rule[-1].src='{{ target_vlan }}';
         uci set firewall.@rule[-1].dest='*';
         uci set firewall.@rule[-1].target='REJECT';
         uci commit firewall;
         service firewall restart"

    - name: Verificar que la regla se creó correctamente
      command: >
        ssh -p {{ openwrt_port }} root@{{ openwrt_host }}
        "uci show firewall | grep ISOLATE-{{ target_vlan }}"
      register: verify_rule

    - name: Mostrar resultado de verificación
      debug:
        msg: "Regla creada: {{ verify_rule.stdout }}"

    - name: Registrar el aislamiento
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - AISLAMIENTO: {{ target_vlan }} bloqueada"
        create: yes
```

---

### 4.2 `unisolate-host.yml` — Desaislamiento de VLAN

**Qué hace:** Elimina la regla REJECT creada por `isolate-host.yml` para restaurar la conectividad de una VLAN tras resolver el incidente.

> IMPORTANTE: Este playbook es exclusivamente manual. Requiere validación del analista SOC antes de ejecutar.

**Ejecución:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/incidentes/unisolate-host.yml \
  -e target_vlan=vlan20
```

---

### 4.3 `collect-evidence.yml` — Recolección de evidencias forenses

**Qué hace:** Recoge evidencias forenses de un nodo comprometido: procesos, conexiones, usuarios, logs, crontabs, rutas, servicios activos. Genera hashes SHA256 para cadena de custodia y envía todo a honeycos-bk.

**Disparador automático:** Encadenado tras `isolate-host.yml` (5s de espera) / Wazuh rule 100503 (comando SSH en honeypot) / Wazuh rule 100507 (brute force honeypot) / Wazuh rule 100508 (evento crítico honeypot)

**Ejecución:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/incidentes/collect-evidence.yml \
  -e target_host=soar-web
```

**Evidencias recogidas:**

| Fichero | Contenido |
|---------|-----------|
| `processes.txt` | Procesos activos (`ps auxf`) |
| `network_connections.txt` | Conexiones de red (`ss -tulpn`) |
| `logged_users.txt` | Usuarios conectados (`who`) |
| `last_logins.txt` | Últimos 20 logins |
| `crontab_root.txt` | Crontab de root |
| `tmp_files.txt` | Ficheros recientes en `/tmp` |
| `netstat.txt` | Estadísticas de red |
| `passwd.txt` | `/etc/passwd` |
| `shadow.txt` | `/etc/shadow` (permisos 0600) |
| `auth_log.txt` | Log de autenticación SSH |
| `services_running.txt` | Servicios en ejecución |
| `checksums.sha256` | Hashes SHA256 de todas las evidencias |

> Las evidencias se guardan en `honeycos-bk:/backups/evidence/<hostname>/<timestamp>/`

---

### 4.4 `block-ip.yml` — Bloqueo de IP maliciosa en Suricata

**Qué hace:** Añade una regla `drop` en Suricata para bloquear una IP maliciosa, recarga las reglas en caliente y registra el bloqueo en el log de incidentes.

**Disparador automático:** Suricata sev=1 (cualquier firma crítica) / Suricata sev=2 C2 / Suricata exploit/shellcode / Wazuh rule 100507 (brute force honeypot) / Wazuh rule 100508 (evento crítico con src_ip)

**Ejecución:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/incidentes/block-ip.yml \
  -e malicious_ip=1.2.3.4
```

```yaml
---
- name: Bloquear IP maliciosa en Suricata
  hosts: suricata-ids
  become: yes
  vars:
    malicious_ip: ""
    rules_file: /etc/suricata/rules/local.rules
  tasks:
    - name: Verificar que se ha especificado una IP
      fail:
        msg: "Debes especificar malicious_ip. Ejemplo: -e malicious_ip=1.2.3.4"
      when: malicious_ip == ""

    - name: Añadir regla drop para la IP
      lineinfile:
        path: "{{ rules_file }}"
        line: 'drop ip {{ malicious_ip }} any -> $HOME_NET any (msg:"SOC Block - Malicious IP {{ malicious_ip }}"; sid:9000001; rev:1;)'
        create: yes

    - name: Recargar reglas en caliente
      command: suricatasc -c reload-rules

    - name: Registrar bloqueo
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - BLOQUEO IP: {{ malicious_ip }}"
        create: yes
      delegate_to: playbooks-dns
```

---

## Automatización de playbooks

### Arquitectura

```
Wazuh SIEM (VM202)                    Suricata IDS (CT106)
       |                                      |
       | active-response                      | eve-watcher.py
       | (rule match)                         | (tail eve.json)
       |                                      |
       +------------------+-------------------+
                          |
                          | SSH puerto 2222
                          v
                  CT103 playbooks-dns
                  /var/ossec/active-response/bin/soc-trigger.sh
                          |
              +-----------+-----------+
              |           |           |
        block-ip    isolate-host  collect-evidence
        fail2ban    update-all    backup-configs
```

### Componentes implementados

| Componente | Ubicación | Descripción |
|-----------|-----------|-------------|
| `soc-trigger.sh` | CT103 `/var/ossec/active-response/bin/` | Script bash ejecutado por Wazuh. Parsea el JSON del evento, decide el playbook y lo lanza |
| `eve-watcher.py` | CT106 `/opt/soc/` | Script Python que monitoriza `eve.json` en tiempo real y llama a CT103 via SSH |
| `eve-watcher.service` | CT106 `/etc/systemd/system/` | Servicio systemd que mantiene `eve-watcher.py` corriendo |
| Bloques `<active-response>` | VM202 `/var/ossec/etc/ossec.conf` | Configuración que indica a Wazuh que ejecute `soc-trigger.sh` en CT103 (agente 005) |

### Mapeo de reglas a playbooks

| Fuente | Regla / Condición | Playbook | Acción |
|--------|-------------------|----------|--------|
| Wazuh | 100507 — brute force honeypot (nivel 14) | `block-ip.yml` + `collect-evidence.yml` | Bloquea IP + recoge evidencia |
| Wazuh | 100508 — evento crítico honeypot (nivel 12) | `block-ip.yml` + `isolate-host.yml` + `collect-evidence.yml` | Bloquea IP + aisla vlan50 + recoge evidencia |
| Wazuh | 100503 — comando SSH honeypot (nivel 10) | `collect-evidence.yml` | Recoge evidencia del honeypot |
| Wazuh | 5710, 5712, 5716, 5720, 5763 — brute force SSH | `fail2ban.yml` | Refuerza fail2ban en el host afectado |
| Wazuh | 550, 551, 552, 553, 554 — FIM | `backup-configs.yml` | Backup inmediato del host con fichero modificado |
| Wazuh | 19101, 19102, 19104 — compliance | `update-all.yml` | Actualiza el host desactualizado |
| Suricata | sev=1 (crítica) src externa | `block-ip.yml` | Bloquea IP en Suricata |
| Suricata | sev=1 (crítica) src interna | `isolate-host.yml` | Aisla la VLAN del host comprometido |
| Suricata | sev=2 C2/malware src externa | `block-ip.yml` | Bloquea IP en Suricata |
| Suricata | sev=2 escaneo src interna | `isolate-host.yml` | Aisla la VLAN origen del escaneo |
| Suricata | exploit/shellcode cualquier sev | `block-ip.yml` | Bloquea IP en Suricata |

### Cooldown anti-flood (eve-watcher.py)

`eve-watcher.py` implementa un cooldown de 5 minutos por IP para evitar ejecutar el mismo playbook cientos de veces ante un flood de alertas de la misma fuente.

### Logs del sistema de automatización

| Fichero | Ubicación | Contenido |
|---------|-----------|-----------|
| `soc-trigger.log` | CT103 `/var/log/` | Log detallado de todas las ejecuciones del script Wazuh |
| `soc-eve-watcher.log` | CT106 `/var/log/` | Log detallado del watcher de Suricata |
| `soc-incidents.log` | CT103 `/var/log/` | Registro de acciones de incidentes (bloqueos, aislamientos, evidencias) |
| `soc-remediation.log` | CT103 `/var/log/` | Registro de acciones de remediación (parcheos, fail2ban, backups) |

### Playbooks manuales (no automatizados)

| Playbook | Motivo |
|----------|--------|
| `unisolate-host.yml` | Restaurar conectividad requiere validación humana |
| `usuarios.yml` | Gestión de usuarios requiere supervisión del analista |
| `harden-ssh.yml` | Configuración ya aplicada — solo para nodos nuevos |

---

## Log de incidentes

Todos los playbooks de incidentes registran sus acciones en:

```
/var/log/soc-incidents.log (CT103)
```

Formato:
```
2026-04-24T14:11:58Z - COLLECT EVIDENCE honeypot — comando SSH detectado desde 1.2.3.4 [rule=100503 agent=honeypot]
2026-04-24T14:19:09Z - BLOQUEO IP: 5.5.5.5
2026-04-24T14:20:19Z - EVE-WATCHER OK: BLOCK IP 5.5.5.5 (Suricata sev=1 'ET MALWARE Test C2 Traffic')
```

Los playbooks de remediación registran en:

```
/var/log/soc-remediation.log (CT103)
```

Formato:
```
2026-04-24T14:27:49Z - FAIL2BAN ACTIVE: soar-web — SSH jail activo puerto 2222
2026-04-24T14:28:37Z - PATCHING DONE: soar-web — sistema actualizado
```

---

## Resumen de playbooks

| Playbook | Categoría | Estado | Automatizado | Disparador |
|----------|-----------|--------|:---:|------------|
| `update-all.yml` | Mantenimiento | OK | Si | Wazuh 19101, 19102, 19104 |
| `harden-ssh.yml` | Mantenimiento | OK | No | Manual — solo nodos nuevos |
| `fail2ban.yml` | Mantenimiento | OK | Si | Wazuh 5710, 5712, 5716, 5720, 5763 |
| `usuarios.yml` | Seguridad | OK | No | Manual |
| `backup-configs.yml` | Backup | OK | Si | Dom 04:00 + Wazuh 550-554 |
| `isolate-host.yml` | Incidentes | OK | Si | Wazuh 100508 + Suricata sev=1 interno |
| `unisolate-host.yml` | Incidentes | OK | No | Manual — validación analista |
| `collect-evidence.yml` | Incidentes | OK | Si | Wazuh 100503, 100507, 100508 |
| `block-ip.yml` | Incidentes | OK | Si | Suricata sev=1/2 + Wazuh 100507, 100508 |
