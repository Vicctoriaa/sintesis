# Ansible Playbooks — SOC honeycos
**Nodo de control:** CT 103 (`playbooks-dns`) — `10.1.1.34`
**Dominio:** `soc.local`
**Fecha:** Abril 2026

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
