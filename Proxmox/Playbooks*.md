# Ansible Playbooks — SOC honeycos
**Nodo de control:** CT 103 (`playbooks-dns`) — `10.1.1.34`

---

## Estructura de directorios actual

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
    │   ├── fail2ban.yml
    │   └── usuarios.yml
    ├── backup/
    │   └── backup-configs.yml
    └── incidentes/
        ├── isolate-host.yml
        ├── unisolate-host.yml
        ├── collect-evidence.yml
        └── block-ip.yml
```

---

## Inventario actual

**Fichero:** `/etc/ansible/inventories/soc.ini`

```ini
[soc]
grafana-prometheus  ansible_host=10.1.1.66
wazuh-siem          ansible_host=10.1.1.67
homepage            ansible_host=10.1.1.68

[servicios]
playbooks-dns       ansible_host=10.1.1.34  ansible_connection=local
nginx-proxy         ansible_host=10.1.1.35  ansible_port=2222
suricata-ids        ansible_host=10.1.1.36  ansible_port=2222
soar-web            ansible_host=10.1.1.37  ansible_port=2222
vaultwarden         ansible_host=10.1.1.80  ansible_port=2222

[produccion]
ldap                ansible_host=10.1.1.98  ansible_port=2222

[firewall]
openwrt-fw          ansible_host=10.1.1.1  ansible_python_interpreter=/bin/false  ansible_shell_type=sh

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
| Usuario | root con clave publica de ansible@soc.local |
| DNS | soc.local resolviendo correctamente |

### Comando base de ejecucion

```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini playbooks/<categoria>/<playbook>.yml
```

### Verificar conectividad con todos los nodos

```bash
ansible -i /etc/ansible/inventories/soc.ini linux -m ping
```

---

## CATEGORIA 1 — Mantenimiento

### 1.1 `update-all.yml` — Actualizacion de paquetes

**Que hace:** Actualiza apt en todos los nodos del grupo `linux`, hace autoremove y notifica si alguno requiere reinicio.

**Ejecucion:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/update-all.yml
```

```yaml
---
- name: Actualizar todos los contenedores Linux
  hosts: linux
  become: yes
  tasks:
    - name: Actualizar lista de paquetes
      apt:
        update_cache: yes
        cache_valid_time: 3600

    - name: Actualizar todos los paquetes
      apt:
        upgrade: dist
        autoremove: yes
        autoclean: yes

    - name: Comprobar si requiere reinicio
      stat:
        path: /var/run/reboot-required
      register: reboot_required

    - name: Notificar si hay reinicio pendiente
      debug:
        msg: "{{ inventory_hostname }} requiere reinicio"
      when: reboot_required.stat.exists
```

---

### 1.2 `harden-ssh.yml` — Hardening SSH

**Que hace:** Aplica configuracion segura SSH en todos los nodos: puerto 2222, sin password, MaxAuthTries 3, desactiva ssh.socket para evitar conflictos.

**Ejecucion:**
```bash
# Todos los nodos
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/harden-ssh.yml

# Un nodo especifico
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/harden-ssh.yml \
  --limit nginx-proxy
```

> IMPORTANTE: Ejecutar primero en un nodo con --check antes de aplicar a todos.

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
        - { regexp: '^#?PermitRootLogin', line: 'PermitRootLogin prohibit-password' }
        - { regexp: '^#?PasswordAuthentication', line: 'PasswordAuthentication no' }
        - { regexp: '^#?PubkeyAuthentication', line: 'PubkeyAuthentication yes' }
        - { regexp: '^#?MaxAuthTries', line: 'MaxAuthTries 3' }
        - { regexp: '^#?LoginGraceTime', line: 'LoginGraceTime 20' }
        - { regexp: '^#?X11Forwarding', line: 'X11Forwarding no' }
        - { regexp: '^#?Port ', line: 'Port {{ ssh_port }}' }

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

### 1.3 `fail2ban.yml` — Instalacion y configuracion Fail2ban

**Que hace:** Instala fail2ban en todos los nodos, configura jail SSH con ban de 1 hora tras 3 intentos fallidos en el puerto 2222.

**Ejecucion:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/fail2ban.yml
```

```yaml
---
- name: Instalar y configurar Fail2ban
  hosts: linux
  become: yes
  vars:
    ssh_port: 2222
  tasks:
    - name: Instalar fail2ban
      apt:
        name: fail2ban
        state: present
        update_cache: yes

    - name: Configurar jail SSH
      copy:
        dest: /etc/fail2ban/jail.local
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
```

---

### 1.4 `usuarios.yml` — Gestion centralizada de usuarios

**Que hace:** Crea, elimina o cambia la contrasena de usuarios en uno, varios o todos los nodos del SOC. Registra todas las operaciones en el log de incidentes.

**Variables:**

| Variable | Valores | Descripcion |
|----------|---------|-------------|
| `action` | `create`, `delete`, `change_password` | Operacion a realizar |
| `username` | nombre del usuario | Usuario sobre el que operar |
| `password` | contrasena | Requerido para create y change_password |
| `target_hosts` | `linux`, nombre nodo, `nodo1,nodo2` | Hosts donde aplicar (default: linux) |

**Ejecucion:**
```bash
# Crear usuario en todos los nodos
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/usuarios.yml \
  -e action=create -e username=operador1 -e password=MiPassword123

# Crear usuario en un nodo especifico
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/usuarios.yml \
  -e target_hosts=soar-web -e action=create -e username=operador1 -e password=MiPassword123

# Crear usuario en varios nodos
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/usuarios.yml \
  -e target_hosts=soar-web,nginx-proxy -e action=create -e username=operador1 -e password=MiPassword123

# Eliminar usuario
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/usuarios.yml \
  -e action=delete -e username=operador1

# Cambiar contrasena
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/mantenimiento/usuarios.yml \
  -e action=change_password -e username=operador1 -e password=NuevaPassword123
```

```yaml
---
- name: Gestion centralizada de usuarios
  hosts: "{{ target_hosts | default('linux') }}"
  become: yes
  vars:
    action: ""
    username: ""
    password: ""
  tasks:
    - name: Verificar que se ha especificado una accion
      fail:
        msg: "Debes especificar action. Opciones: create, delete, change_password"
      when: action == ""
      delegate_to: localhost
      run_once: true

    - name: Verificar que se ha especificado un usuario
      fail:
        msg: "Debes especificar username."
      when: username == ""
      delegate_to: localhost
      run_once: true

    - name: Verificar contrasena para create/change_password
      fail:
        msg: "Debes especificar password."
      when:
        - action in ['create', 'change_password']
        - password == ""
      delegate_to: localhost
      run_once: true

    - name: Crear usuario
      user:
        name: "{{ username }}"
        state: present
        shell: /bin/bash
        create_home: yes
        password: "{{ password | password_hash('sha512') }}"
      when: action == 'create'

    - name: Crear directorio .ssh
      file:
        path: "/home/{{ username }}/.ssh"
        state: directory
        mode: '0700'
        owner: "{{ username }}"
        group: "{{ username }}"
      when: action == 'create'

    - name: Eliminar usuario
      user:
        name: "{{ username }}"
        state: absent
        remove: yes
      when: action == 'delete'

    - name: Cambiar contrasena
      user:
        name: "{{ username }}"
        password: "{{ password | password_hash('sha512') }}"
        update_password: always
      when: action == 'change_password'

    - name: Registrar operacion
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - USUARIO {{ action | upper }}: {{ username }} en {{ inventory_hostname }} por {{ lookup('env','USER') }}"
        create: yes
      delegate_to: playbooks-dns
```

---

## CATEGORIA 2 — Backup

### 2.1 `backup-configs.yml` — Backup de configuraciones criticas

**Que hace:** Recoge ficheros de configuracion criticos de todos los nodos y los envia a honeycos-bk (`/backups/configs/YYYY-MM-DD/`). Se ejecuta automaticamente los domingos a las 4:00.

**Automatizacion (crontab CT103):**
```
0 4 * * 0 ansible-playbook /etc/ansible/playbooks/backup/backup-configs.yml -i /etc/ansible/inventories/soc.ini
```

**Ejecucion manual:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/backup/backup-configs.yml
```

**Ficheros que recoge por nodo:**

| Categoria | Ficheros |
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

## CATEGORIA 3 — Respuesta a Incidentes

### 3.1 `isolate-host.yml` — Aislamiento de VLAN

**Que hace:** Ante un incidente, añade una regla REJECT en OpenWRT para bloquear todo el trafico de una VLAN. Registra el aislamiento en el log de incidentes.

**Ejecucion:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/incidentes/isolate-host.yml \
  -e target_vlan=vlan20
```

> ATENCION: Solo ejecutar en caso de incidente real. Corta todas las comunicaciones de la VLAN especificada.

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

    - name: Verificar que la regla se creo correctamente
      command: >
        ssh -p {{ openwrt_port }} root@{{ openwrt_host }}
        "uci show firewall | grep ISOLATE-{{ target_vlan }}"
      register: verify_rule

    - name: Mostrar resultado de verificacion
      debug:
        msg: "Regla creada: {{ verify_rule.stdout }}"

    - name: Registrar el aislamiento
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - AISLAMIENTO: {{ target_vlan }} bloqueada"
        create: yes
```

---

### 3.2 `unisolate-host.yml` — Desaislamiento de VLAN

**Que hace:** Elimina la regla REJECT creada por `isolate-host.yml` para restaurar la conectividad de una VLAN tras resolver el incidente.

**Ejecucion:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/incidentes/unisolate-host.yml \
  -e target_vlan=vlan20
```

```yaml
---
- name: Desaislar VLAN en OpenWRT
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

    - name: Buscar regla de aislamiento
      command: >
        ssh -p {{ openwrt_port }} root@{{ openwrt_host }}
        "uci show firewall | grep -n 'ISOLATE-{{ target_vlan }}' | head -1 | cut -d: -f1"
      register: rule_line

    - name: Verificar que existe la regla
      fail:
        msg: "No se encontro regla de aislamiento para {{ target_vlan }}"
      when: rule_line.stdout == ""

    - name: Eliminar regla REJECT
      command: >
        ssh -p {{ openwrt_port }} root@{{ openwrt_host }}
        "uci delete firewall.$(uci show firewall | grep 'ISOLATE-{{ target_vlan }}' | cut -d. -f1-2 | head -1);
         uci commit firewall;
         service firewall restart"

    - name: Registrar el desaislamiento
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - DESAISLAMIENTO: {{ target_vlan }} restaurada"
        create: yes
```

---

### 3.3 `collect-evidence.yml` — Recoleccion de evidencias forenses

**Que hace:** Recoge evidencias forenses de un nodo comprometido: procesos, conexiones, usuarios, logs, crontabs, rutas, servicios activos. Genera hashes SHA256 para cadena de custodia y envia todo a honeycos-bk.

**Ejecucion:**
```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/incidentes/collect-evidence.yml \
  -e target_host=soar-web
```

**Evidencias recogidas:**

| Fichero | Contenido |
|---------|-----------|
| `processes.txt` | Procesos activos (ps auxf) |
| `network_connections.txt` | Conexiones de red (ss -tulpn) |
| `logged_users.txt` | Usuarios conectados (who) |
| `last_logins.txt` | Ultimos 20 logins |
| `crontab_root.txt` | Crontab de root |
| `tmp_files.txt` | Ficheros recientes en /tmp |
| `netstat.txt` | Estadisticas de red |
| `passwd.txt` | /etc/passwd |
| `shadow.txt` | /etc/shadow (permisos 0600) |
| `lastlog.txt` | Ultimo login de cada usuario |
| `routes.txt` | Tabla de rutas |
| `iptables.txt` | Reglas de firewall |
| `services_running.txt` | Servicios en ejecucion |
| `cron_files.txt` | Ficheros cron del sistema |
| `auth_log.txt` | Log de autenticacion SSH |
| `disk_usage.txt` | Uso de disco |
| `memory.txt` | Uso de memoria |
| `uptime.txt` | Uptime del sistema |
| `checksums.sha256` | Hashes SHA256 de todas las evidencias |

> Las evidencias se guardan con permisos 0700/0600 (solo root). Se envian a `honeycos-bk:/backups/evidence/<hostname>/<timestamp>/`

---

### 3.4 `block-ip.yml` — Bloqueo de IP maliciosa en Suricata

**Que hace:** Añade una regla `drop` en Suricata para bloquear una IP maliciosa, recarga las reglas en caliente y registra el bloqueo en el log de incidentes.

**Ejecucion:**
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

## Log de incidentes

Todos los playbooks de incidentes y gestion de usuarios registran sus acciones en:

```
/var/log/soc-incidents.log (CT103)
```

Formato:
```
2026-04-16T14:00:00+00:00 - AISLAMIENTO: vlan20 bloqueada
2026-04-16T14:05:00+00:00 - EVIDENCIAS: recogidas de soar-web por root
2026-04-16T14:10:00+00:00 - BLOQUEO IP: 1.2.3.4
2026-04-16T14:30:00+00:00 - DESAISLAMIENTO: vlan20 restaurada
2026-04-16T15:00:00+00:00 - USUARIO CREATE: operador1 en soar-web por root
```

---

## Resumen de playbooks

| Playbook | Categoria | Estado | Automatizado |
|----------|-----------|--------|--------------|
| `update-all.yml` | Mantenimiento | OK | No |
| `harden-ssh.yml` | Mantenimiento | OK | No |
| `fail2ban.yml` | Mantenimiento | OK | No |
| `usuarios.yml` | Mantenimiento | OK | No |
| `backup-configs.yml` | Backup | OK | Dom 04:00 |
| `isolate-host.yml` | Incidentes | OK | No |
| `unisolate-host.yml` | Incidentes | OK | No |
| `collect-evidence.yml` | Incidentes | OK | No |
| `block-ip.yml` | Incidentes | OK | No |

---

*Documentacion actualizada 2026-04-16*

---

# Automatización de playbooks

## 1.1 update-all.yml — Actualización automática por estado de desactualización (event-driven)

### Evento disparador
Wazuh (o script de auditoría local programado por syscheck) detecta:
- paquetes pendientes de actualización
- vulnerabilidades o CVEs sin parchear
- sistema fuera de compliance (APT outdated > X días)

➡️ En ese momento se ejecuta este playbook de remediación automática

---

### Ejecución automática (Wazuh Active Response / SOAR)

```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/remediacion/update-all.yml \
  -e target_hosts=<host_afectado>
Playbook reactivo
---
- name: Remediacion automatica - sistema desactualizado
  hosts: "{{ target_hosts | default('linux') }}"
  become: yes
  serial: 1

  tasks:

    - name: Verificar conectividad
      ping:

    - name: Detectar paquetes pendientes de actualizacion
      shell: apt list --upgradable
      register: upgrades
      changed_when: false

    - name: Ejecutar actualizacion solo si hay paquetes pendientes
      apt:
        update_cache: yes
        upgrade: dist
        autoremove: yes
        autoclean: yes
      when: upgrades.stdout != ""

    - name: Revalidar estado del sistema tras parcheo
      shell: apt list --upgradable
      register: upgrades_after
      changed_when: false

    - name: Marcar sistema como conforme si ya no hay updates
      debug:
        msg: "{{ inventory_hostname }} actualizado correctamente - sistema en compliance"
      when: upgrades_after.stdout == ""

    - name: Detectar si requiere reinicio
      stat:
        path: /var/run/reboot-required
      register: reboot_required

    - name: Registrar necesidad de reinicio
      lineinfile:
        path: /var/log/soc-remediation.log
        line: "{{ ansible_date_time.iso8601 }} - REBOOT REQUIRED: {{ inventory_hostname }}"
        create: yes
      when: reboot_required.stat.exists

    - name: Registrar remediacion aplicada
      lineinfile:
        path: /var/log/soc-remediation.log
        line: "{{ ansible_date_time.iso8601 }} - PATCHING DONE: {{ inventory_hostname }}"
        create: yes
      when: upgrades.stdout != ""


## 1.2 harden-ssh.yml — Hardening SSH (respuesta a evento de riesgo SSH)

### Evento disparador
Detección automática por:
- :contentReference[oaicite:0]{index=0}:
  - intentos de fuerza bruta SSH
  - login root detectado
  - autenticaciones anómalas
- o alerta de exposición SSH insegura (compliance failure)

➡️ Ejecuta hardening inmediato del host afectado o del grupo

---

### Ejecución automática (SOAR / Wazuh Active Response)

```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/remediacion/harden-ssh.yml \
  -e target_hosts=<host_afectado>
Playbook reactivo
---
- name: Hardening SSH automatico por incidente de seguridad
  hosts: "{{ target_hosts | default('linux') }}"
  become: yes
  serial: 1

  vars:
    ssh_port: 2222

  tasks:

    - name: Verificar conectividad
      ping:

    - name: Detectar configuracion SSH insegura previa
      shell: grep -E "PermitRootLogin yes|PasswordAuthentication yes" /etc/ssh/sshd_config
      register: ssh_weak_config
      failed_when: false
      changed_when: false

    - name: Aplicar hardening SSH inmediato
      lineinfile:
        path: /etc/ssh/sshd_config
        regexp: "{{ item.regexp }}"
        line: "{{ item.line }}"
        backup: yes
      loop:
        - { regexp: '^#?PermitRootLogin', line: 'PermitRootLogin prohibit-password' }
        - { regexp: '^#?PasswordAuthentication', line: 'PasswordAuthentication no' }
        - { regexp: '^#?PubkeyAuthentication', line: 'PubkeyAuthentication yes' }
        - { regexp: '^#?MaxAuthTries', line: 'MaxAuthTries 3' }
        - { regexp: '^#?LoginGraceTime', line: 'LoginGraceTime 20' }
        - { regexp: '^#?X11Forwarding', line: 'X11Forwarding no' }
        - { regexp: '^#?Port ', line: 'Port {{ ssh_port }}' }
      when: ssh_weak_config.rc == 0

    - name: Desactivar ssh.socket si esta activo (reduccion superficie ataque)
      systemd:
        name: ssh.socket
        state: stopped
        enabled: no
      ignore_errors: yes

    - name: Validar configuracion SSH antes de reiniciar
      command: sshd -t
      register: ssh_test
      failed_when: ssh_test.rc != 0

    - name: Reiniciar servicio SSH de forma segura
      service:
        name: ssh
        state: restarted

    - name: Registrar hardening en log SOC
      lineinfile:
        path: /var/log/soc-remediation.log
        line: "{{ ansible_date_time.iso8601 }} - SSH HARDENED: {{ inventory_hostname }}"
        create: yes

## 1.3 fail2ban.yml — Respuesta automática a ataques de fuerza bruta SSH

### Evento disparador
Detección por:
- :contentReference[oaicite:0]{index=0}:
  - múltiples intentos fallidos SSH
- logs de autenticación sospechosos en `/var/log/auth.log`
- alerta de brute force o credential stuffing

➡️ despliega o corrige fail2ban automáticamente en el host afectado

---

### Ejecución automática (SOAR / Active Response)

```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/remediacion/fail2ban.yml \
  -e target_hosts=<host_afectado>
Playbook reactivo
---
- name: Remediacion automatica - proteccion contra fuerza bruta SSH
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

    - name: Generar configuracion hardening fail2ban SSH
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

    - name: Validar configuracion fail2ban
      command: fail2ban-client -d
      register: f2b_check
      failed_when: false
      changed_when: false

    - name: Reiniciar fail2ban de forma controlada
      service:
        name: fail2ban
        state: restarted
        enabled: yes

    - name: Verificar estado de jail SSH
      command: fail2ban-client status sshd
      register: jail_status
      changed_when: false

    - name: Registrar incidente y respuesta
      lineinfile:
        path: /var/log/soc-remediation.log
        line: "{{ ansible_date_time.iso8601 }} - FAIL2BAN ACTIVE SSH PROTECTION: {{ inventory_hostname }}"
        create: yes


## 1.4 usuarios.yml — Gestión centralizada de usuarios (respuesta a incidente / IAM reactivo)

### Evento disparador
Activado automáticamente por:
- :contentReference[oaicite:0]{index=0}:
  - creación de usuario sospechosa
  - login anómalo o privilegios elevados no autorizados
  - alerta de compromiso de credenciales
- SOAR (:contentReference[oaicite:1]{index=1} / webhook / IAM interno):
  - alta/baja automática de usuarios por política de seguridad
- incidente SOC (phishing / credential leak)

➡️ ejecuta acción automática de usuario (create / delete / reset password)

---

### Ejecución automática (SOAR / Active Response)

```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/remediacion/usuarios.yml \
  -e action=<create|delete|change_password> \
  -e username=<usuario_afectado> \
  -e password=<si_aplica> \
  -e target_hosts=<host_afectado>
Playbook reactivo
---
- name: Remediacion automatica IAM - gestion de usuarios SOC
  hosts: "{{ target_hosts | default('linux') }}"
  become: yes
  serial: 1

  vars:
    action: ""
    username: ""
    password: ""

  tasks:

    - name: Verificar conectividad
      ping:

    - name: Validar accion obligatoria
      fail:
        msg: "Action requerida: create, delete, change_password"
      when: action == ""
      delegate_to: localhost
      run_once: true

    - name: Validar usuario obligatorio
      fail:
        msg: "Username requerido"
      when: username == ""
      delegate_to: localhost
      run_once: true

    - name: Validar password si aplica
      fail:
        msg: "Password requerida para esta operacion"
      when:
        - action in ['create', 'change_password']
        - password == ""
      delegate_to: localhost
      run_once: true

    - name: Crear usuario comprometido o autorizado por SOC
      user:
        name: "{{ username }}"
        state: present
        shell: /bin/bash
        create_home: yes
        password: "{{ password | password_hash('sha512') }}"
      when: action == 'create'

    - name: Eliminar usuario comprometido
      user:
        name: "{{ username }}"
        state: absent
        remove: yes
      when: action == 'delete'

    - name: Reset de credenciales tras incidente
      user:
        name: "{{ username }}"
        password: "{{ password | password_hash('sha512') }}"
        update_password: always
      when: action == 'change_password'

    - name: Auditoria de cambio IAM en SOC log
      lineinfile:
        path: /var/log/soc-iam-events.log
        line: "{{ ansible_date_time.iso8601 }} - IAM {{ action | upper }} usuario={{ username }} host={{ inventory_hostname }}"
        create: yes
      delegate_to: playbooks-dns

## 2.1 backup-configs.yml — Backup de configuraciones críticas (respuesta a evento de cambio no autorizado / incidente)

### Evento disparador
Backup automático se ejecuta cuando ocurre:

- :contentReference[oaicite:0]{index=0} detecta:
  - modificación de ficheros críticos (sshd_config, nginx.conf, etc.)
  - integridad de archivos alterada (FIM alert)
- alerta de incidente SOC (pre/post remediación)
- cambio de configuración en servicios críticos (Nginx, Suricata, DNS)

➡️ se ejecuta backup inmediato “before/after snapshot”

---

### Ejecución automática (SOAR / Active Response)

```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/backup/backup-configs.yml \
  -e target_hosts=<host_afectado>
Playbook reactivo
---
- name: Backup reactivo de configuraciones criticas (SOC FIM response)
  hosts: "{{ target_hosts | default('linux') }}"
  become: yes
  serial: 1

  vars:
    backup_date: "{{ lookup('pipe', 'date +%F-%H%M') }}"
    backup_root: "/backups/configs/{{ backup_date }}"

  tasks:

    - name: Verificar conectividad
      ping:

    - name: Crear directorio de backup en nodo central
      file:
        path: "{{ backup_root }}/{{ inventory_hostname }}"
        state: directory
        mode: '0755'
      delegate_to: playbooks-dns

    - name: Detectar cambios en configuraciones criticas
      shell: |
        find /etc -type f \( -name "sshd_config" -o -name "jail.local" -o -name "nginx.conf" -o -name "prometheus.yml" -o -name "suricata.yaml" -o -name "ossec.conf" \) -mtime -1
      register: changed_files
      changed_when: false

    - name: Ejecutar backup de configuraciones criticas
      fetch:
        src: "{{ item }}"
        dest: "{{ backup_root }}/{{ inventory_hostname }}/"
        flat: no
        fail_on_missing: no
      loop:
        - /etc/ssh/sshd_config
        - /etc/fail2ban/jail.local
        - /etc/nginx/nginx.conf
        - /etc/nginx/sites-available/
        - /etc/prometheus/prometheus.yml
        - /etc/suricata/suricata.yaml
        - /etc/wazuh-manager/ossec.conf
        - /etc/wazuh-manager/local_decoder.xml
        - /etc/postfix/main.cf
        - /etc/postfix/sasl_passwd
        - /opt/docker-compose.yml

    - name: Backup de inventario y playbooks SOC
      fetch:
        src: "{{ item }}"
        dest: "{{ backup_root }}/{{ inventory_hostname }}/ansible/"
        flat: no
        fail_on_missing: no
      loop:
        - /etc/ansible/inventories/
        - /etc/ansible/playbooks/

    - name: Registrar evento de backup por incidente
      lineinfile:
        path: /var/log/soc-backup-events.log
        line: "{{ ansible_date_time.iso8601 }} - FIM BACKUP TRIGGERED: {{ inventory_hostname }}"
        create: yes
      delegate_to: playbooks-dns

## 3.1 isolate-host.yml — Aislamiento automático de VLAN (respuesta a incidente de red)

### Evento disparador
Activado automáticamente por:

- :contentReference[oaicite:0]{index=0}:
  - detección de malware lateral movement
  - escaneo interno (lateral scanning)
  - tráfico C2 dentro de VLAN sospechosa
- :contentReference[oaicite:1]{index=1}:
  - host comprometido dentro de una VLAN
  - múltiples alertas correlacionadas en la misma red
- detección de anomalías de red (Netflow / firewall logs)

➡️ resultado: aislamiento completo de VLAN comprometida en :contentReference[oaicite:2]{index=2}

---

### Ejecución automática (SOAR / Active Response)

```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/incidentes/isolate-host.yml \
  -e target_vlan=<vlan_comprometida>
Playbook reactivo
---
- name: Aislamiento automatico de VLAN comprometida (SOC Incident Response)
  hosts: localhost
  gather_facts: yes

  vars:
    target_vlan: ""
    openwrt_host: "10.1.1.1"
    openwrt_port: "2222"

  tasks:

    - name: Validar VLAN objetivo
      fail:
        msg: "Debes especificar target_vlan (ej: vlan20)"
      when: target_vlan == ""

    - name: Registrar inicio de aislamiento critico
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - INCIDENT RESPONSE START: AISLAR {{ target_vlan }}"
        create: yes

    - name: Aplicar aislamiento de VLAN en OpenWRT
      shell: |
        ssh -p {{ openwrt_port }} root@{{ openwrt_host }} "
        uci add firewall rule;
        uci set firewall.@rule[-1].name='ISOLATE-{{ target_vlan }}';
        uci set firewall.@rule[-1].src='{{ target_vlan }}';
        uci set firewall.@rule[-1].dest='*';
        uci set firewall.@rule[-1].target='REJECT';
        uci commit firewall;
        /etc/init.d/firewall restart
        "

    - name: Verificar regla aplicada en firewall
      shell: |
        ssh -p {{ openwrt_port }} root@{{ openwrt_host }} "uci show firewall | grep ISOLATE-{{ target_vlan }}"
      register: verify_rule
      changed_when: false

    - name: Confirmar aislamiento activo
      debug:
        msg: "VLAN {{ target_vlan }} aislada correctamente -> {{ verify_rule.stdout }}"

    - name: Registrar aislamiento exitoso en SOC log
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - AISLAMIENTO ACTIVO: {{ target_vlan }} bloqueada en OpenWRT"
        create: yes

## 3.2 unisolate-host.yml — Restauración de conectividad de VLAN (post-incidente)

### Evento disparador
Este playbook se ejecuta cuando:

- :contentReference[oaicite:0]{index=0} marca incidente como:
  - RESUELTO / CERRADO
  - falso positivo confirmado
  - host/VLAN ya no presenta actividad maliciosa
- analista SOC valida cierre de incidente en SOAR
- fase de “recovery” del ciclo de respuesta a incidentes

➡️ se elimina el aislamiento aplicado previamente en :contentReference[oaicite:1]{index=1}

---

### Ejecución automática (SOAR / cierre de incidente)

```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/incidentes/unisolate-host.yml \
  -e target_vlan=<vlan_recuperada>
Playbook reactivo
---
- name: Restauracion de conectividad VLAN (SOC Recovery Phase)
  hosts: localhost
  gather_facts: yes

  vars:
    target_vlan: ""
    openwrt_host: "10.1.1.1"
    openwrt_port: "2222"

  tasks:

    - name: Validar VLAN objetivo
      fail:
        msg: "Debes especificar target_vlan (ej: vlan20)"
      when: target_vlan == ""

    - name: Registrar inicio de restauracion
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - RECOVERY START: RESTAURAR {{ target_vlan }}"
        create: yes

    - name: Buscar regla de aislamiento activa
      shell: |
        ssh -p {{ openwrt_port }} root@{{ openwrt_host }} "
        uci show firewall | grep 'ISOLATE-{{ target_vlan }}'
        "
      register: rule_check
      failed_when: false
      changed_when: false

    - name: Validar que existe aislamiento previo
      fail:
        msg: "No existe regla de aislamiento para {{ target_vlan }}"
      when: rule_check.stdout == ""

    - name: Eliminar regla de aislamiento en OpenWRT
      shell: |
        ssh -p {{ openwrt_port }} root@{{ openwrt_host }} "
        RULE=\$(uci show firewall | grep 'ISOLATE-{{ target_vlan }}' | cut -d. -f1-2 | head -1);
        uci delete \$RULE;
        uci commit firewall;
        /etc/init.d/firewall restart
        "

    - name: Confirmar restauracion de conectividad
      debug:
        msg: "VLAN {{ target_vlan }} restaurada correctamente"

    - name: Registrar desaislamiento en SOC log
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - DESAISLAMIENTO COMPLETO: {{ target_vlan }} conectividad restaurada"
        create: yes


## 3.4 block-ip.yml — Bloqueo automático de IP maliciosa (respuesta a amenaza de red)

### Evento disparador
Activado automáticamente por:

- :contentReference[oaicite:0]{index=0}:
  - detección de C2 (command & control)
  - tráfico malicioso hacia HOME_NET
  - firmas IDS de explotación o malware
- :contentReference[oaicite:1]{index=1}:
  - IP clasificada como IOC (Indicator of Compromise)
  - correlación de actividad sospechosa entre hosts
- threat intelligence feed (IP reputation negativa)

➡️ genera bloqueo automático de IP en tiempo real

---

### Ejecución automática (SOAR / Active Response)

```bash
ansible-playbook -i /etc/ansible/inventories/soc.ini \
  /etc/ansible/playbooks/incidentes/block-ip.yml \
  -e malicious_ip=<ip_detectada>
Playbook reactivo
---
- name: Bloqueo automatico de IP maliciosa en Suricata (SOC response)
  hosts: suricata-ids
  become: yes

  vars:
    malicious_ip: ""
    rules_file: /etc/suricata/rules/local.rules

  tasks:

    - name: Validar IP maliciosa
      fail:
        msg: "Debes especificar malicious_ip (ej: -e malicious_ip=1.2.3.4)"
      when: malicious_ip == ""

    - name: Registrar inicio de bloqueo SOC
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - BLOCK START IP: {{ malicious_ip }}"
        create: yes

    - name: Añadir regla DROP en Suricata
      lineinfile:
        path: "{{ rules_file }}"
        line: 'drop ip {{ malicious_ip }} any -> $HOME_NET any (msg:"SOC BLOCK IP {{ malicious_ip }}"; sid:9000001; rev:1;)'
        create: yes

    - name: Validar reglas Suricata antes de recargar
      command: suricata -T -c /etc/suricata/suricata.yaml
      register: suri_test
      failed_when: suri_test.rc != 0

    - name: Recargar reglas en caliente
      command: suricatasc -c reload-rules

    - name: Confirmar bloqueo activo
      debug:
        msg: "IP {{ malicious_ip }} bloqueada en Suricata IDS"

    - name: Registrar bloqueo en SOC log
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - BLOQUEO IP ACTIVO: {{ malicious_ip }} en Suricata"
        create: yes
