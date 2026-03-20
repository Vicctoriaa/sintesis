# Ansible Playbooks — SOC Proxmox
**Nodo de control:** CT 103 (`playbooks-dns`) — `10.1.1.34`  
**Dominio:** `soc.local`  
**Fecha:** Marzo 2026

---

## Estructura de directorios recomendada

```
/etc/ansible/
├── ansible.cfg
├── inventory/
│   ├── hosts.yml
│   └── group_vars/
│       ├── all.yml
│       ├── vlan20.yml
│       └── vlan30.yml
└── playbooks/
    ├── mantenimiento/
    │   ├── update-all.yml
    │   ├── harden-ssh.yml
    │   ├── fail2ban.yml
    │   └── usuarios.yml
    ├── seguridad/
    │   ├── suricata-rules.yml
    │   ├── logs-rotation.yml
    │   └── iocs-sync.yml
    ├── despliegue/
    │   ├── deploy-grafana.yml
    │   ├── deploy-prometheus.yml
    │   ├── deploy-nginx.yml
    │   ├── deploy-suricata.yml
    │   └── deploy-bind9.yml
    ├── backup/
    │   ├── backup-configs.yml
    │   └── restore-configs.yml
    └── incidentes/
        ├── isolate-host.yml
        ├── collect-evidence.yml
        └── block-ip.yml
```

---

## Requisitos previos globales

| Requisito | Detalle |
|-----------|---------|
| Ansible | >= 2.14 instalado en CT 103 |
| Python | >= 3.9 en todos los contenedores objetivo |
| SSH | Acceso por clave desde CT 103 a todos los CTs |
| Usuario | Usuario `ansible` con sudo sin contraseña en cada CT |
| Resolución DNS | `soc.local` resolviendo correctamente (ya configurado) |

### Instalación de Ansible en CT 103
```bash
apt update
apt install ansible python3-pip -y
ansible --version
```

### Configuración de acceso SSH sin contraseña
```bash
# En CT 103 — generar clave
ssh-keygen -t ed25519 -C "ansible@soc.local" -f ~/.ssh/ansible_key

# Copiar clave a cada contenedor
ssh-copy-id -i ~/.ssh/ansible_key.pub root@10.1.1.35  # nginx
ssh-copy-id -i ~/.ssh/ansible_key.pub root@10.1.1.36  # suricata
ssh-copy-id -i ~/.ssh/ansible_key.pub root@10.1.1.37  # soar
ssh-copy-id -i ~/.ssh/ansible_key.pub root@10.1.1.66  # grafana
```

### Inventario (`/etc/ansible/inventory/hosts.yml`)
```yaml
all:
  children:
    vlan20:
      hosts:
        nginx.soc.local:
          ansible_host: 10.1.1.35
        suricata.soc.local:
          ansible_host: 10.1.1.36
        soar.soc.local:
          ansible_host: 10.1.1.37
    vlan30:
      hosts:
        grafana.soc.local:
          ansible_host: 10.1.1.66
    dns:
      hosts:
        dns.soc.local:
          ansible_host: 10.1.1.34
          ansible_connection: local
```

---

## CATEGORÍA 1 — Mantenimiento y Hardening

### 1.1 `update-all.yml` — Actualización de todos los contenedores

**Qué hace:**
Actualiza los paquetes de todos los contenedores Debian del inventario, realiza `apt autoremove` y opcionalmente reinicia los servicios afectados.

**Requiere:**
- Acceso SSH con sudo a todos los contenedores
- Conexión a internet desde cada CT

```yaml
---
- name: Actualizar todos los contenedores
  hosts: all
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

**Ejecución:**
```bash
ansible-playbook playbooks/mantenimiento/update-all.yml
```

---

### 1.2 `harden-ssh.yml` — Hardening de SSH

**Qué hace:**
Aplica configuración segura de SSH en todos los contenedores: deshabilita login de root, fuerza autenticación por clave, cambia el puerto por defecto, limita intentos de conexión y deshabilita protocolos débiles.

**Requiere:**
- Claves SSH ya distribuidas antes de ejecutar
- Acceso root temporal para aplicar el cambio

```yaml
---
- name: Hardening SSH en todos los contenedores
  hosts: all
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
        - { regexp: '^#?PermitRootLogin', line: 'PermitRootLogin no' }
        - { regexp: '^#?PasswordAuthentication', line: 'PasswordAuthentication no' }
        - { regexp: '^#?PubkeyAuthentication', line: 'PubkeyAuthentication yes' }
        - { regexp: '^#?MaxAuthTries', line: 'MaxAuthTries 3' }
        - { regexp: '^#?LoginGraceTime', line: 'LoginGraceTime 20' }
        - { regexp: '^#?X11Forwarding', line: 'X11Forwarding no' }
        - { regexp: '^#?Port ', line: 'Port {{ ssh_port }}' }

    - name: Reiniciar SSH
      service:
        name: ssh
        state: restarted
```

**Ejecución:**
```bash
ansible-playbook playbooks/mantenimiento/harden-ssh.yml
```

> ⚠️ Ejecutar primero en un solo host para validar antes de aplicar a todos.

---

### 1.3 `fail2ban.yml` — Instalación y configuración de Fail2ban

**Qué hace:**
Instala fail2ban en todos los contenedores, configura jail para SSH con ban de 1 hora tras 3 intentos fallidos, y habilita notificaciones de ban en el log.

**Requiere:**
- `apt` disponible en los contenedores objetivo
- Servicio SSH activo

```yaml
---
- name: Instalar y configurar Fail2ban
  hosts: all
  become: yes
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
          port     = ssh
          logpath  = %(sshd_log)s

    - name: Habilitar y arrancar fail2ban
      service:
        name: fail2ban
        state: started
        enabled: yes
```

**Ejecución:**
```bash
ansible-playbook playbooks/mantenimiento/fail2ban.yml
```

---

### 1.4 `usuarios.yml` — Gestión centralizada de usuarios

**Qué hace:**
Crea usuarios del equipo SOC en todos los contenedores, distribuye claves SSH públicas, configura sudoers y elimina usuarios que ya no deben tener acceso.

**Requiere:**
- Claves SSH públicas de cada usuario definidas en `group_vars/all.yml`
- Lista de usuarios a crear/eliminar

```yaml
---
- name: Gestión centralizada de usuarios SOC
  hosts: all
  become: yes
  vars:
    soc_users:
      - name: analyst01
        groups: sudo
        ssh_key: "ssh-ed25519 AAAA... analyst01@soc"
      - name: analyst02
        groups: sudo
        ssh_key: "ssh-ed25519 AAAA... analyst02@soc"
    users_to_remove:
      - exanalyst
  tasks:
    - name: Crear usuarios SOC
      user:
        name: "{{ item.name }}"
        groups: "{{ item.groups }}"
        shell: /bin/bash
        create_home: yes
      loop: "{{ soc_users }}"

    - name: Distribuir claves SSH
      authorized_key:
        user: "{{ item.name }}"
        key: "{{ item.ssh_key }}"
        state: present
      loop: "{{ soc_users }}"

    - name: Eliminar usuarios revocados
      user:
        name: "{{ item }}"
        state: absent
        remove: yes
      loop: "{{ users_to_remove }}"
```

**Ejecución:**
```bash
ansible-playbook playbooks/mantenimiento/usuarios.yml
```

---

## CATEGORÍA 2 — Seguridad y Detección

### 2.1 `suricata-rules.yml` — Actualización de reglas Suricata

**Qué hace:**
Ejecuta `suricata-update` en CT 106, habilita el ruleset `et/open` de Emerging Threats, recarga Suricata sin interrumpir la captura y verifica que el servicio sigue activo.

**Requiere:**
- Suricata instalado en `suricata.soc.local`
- Acceso a internet desde CT 106
- `suricata-update` instalado

```yaml
---
- name: Actualizar reglas de Suricata
  hosts: suricata.soc.local
  become: yes
  tasks:
    - name: Ejecutar suricata-update
      command: suricata-update
      register: update_result

    - name: Mostrar resultado
      debug:
        var: update_result.stdout_lines

    - name: Recargar reglas en caliente
      command: suricatasc -c reload-rules
      ignore_errors: yes

    - name: Verificar que Suricata sigue activo
      service:
        name: suricata
        state: started
```

**Ejecución:**
```bash
ansible-playbook playbooks/seguridad/suricata-rules.yml
```

**Automatización con cron:**
```bash
echo "0 3 * * * root ansible-playbook /etc/ansible/playbooks/seguridad/suricata-rules.yml" > /etc/cron.d/suricata-update
```

---

### 2.2 `logs-rotation.yml` — Rotación y compresión de logs

**Qué hace:**
Configura logrotate en todos los contenedores para los logs de Suricata, Nginx, Bind9 y servicios SOC. Comprime logs mayores de 7 días y elimina logs con más de 30 días.

**Requiere:**
- `logrotate` disponible (viene por defecto en Debian)

```yaml
---
- name: Configurar rotación de logs
  hosts: all
  become: yes
  tasks:
    - name: Configurar logrotate global
      copy:
        dest: /etc/logrotate.d/soc
        content: |
          /var/log/suricata/*.log {
              daily
              rotate 30
              compress
              delaycompress
              missingok
              notifempty
              postrotate
                  systemctl reload suricata 2>/dev/null || true
              endscript
          }
          /var/log/nginx/*.log {
              daily
              rotate 30
              compress
              delaycompress
              missingok
              notifempty
              postrotate
                  systemctl reload nginx 2>/dev/null || true
              endscript
          }
```

**Ejecución:**
```bash
ansible-playbook playbooks/seguridad/logs-rotation.yml
```

---

### 2.3 `iocs-sync.yml` — Sincronización de IOCs con el SIEM

**Qué hace:**
Descarga listas de IOCs (IPs maliciosas, dominios, hashes) desde fuentes públicas (AbuseIPDB, Threat Fox, etc.), las formatea para Suricata y las sincroniza con el SIEM.

**Requiere:**
- SIEM operativo (pendiente de despliegue)
- API key de AbuseIPDB (gratuita)
- `python3-requests` en CT 106

> ⏳ **Pendiente** — implementar cuando el SIEM esté desplegado.

---

## CATEGORÍA 3 — Despliegue de Servicios

### 3.1 `deploy-grafana.yml` — Despliegue de Grafana + Prometheus

**Qué hace:**
Despliega Grafana y Prometheus en CT 101 desde cero: instala paquetes, configura datasources, importa dashboards base para el SOC y configura alertas.

**Requiere:**
- CT 101 con Debian 12
- Acceso a internet para descargar paquetes
- Al menos 512 MB RAM

```yaml
---
- name: Desplegar Grafana y Prometheus
  hosts: grafana.soc.local
  become: yes
  tasks:
    - name: Añadir repo Grafana
      apt_repository:
        repo: "deb https://packages.grafana.com/oss/deb stable main"
        state: present

    - name: Instalar Grafana y Prometheus
      apt:
        name:
          - grafana
          - prometheus
        state: present
        update_cache: yes

    - name: Configurar Prometheus scrape
      copy:
        dest: /etc/prometheus/prometheus.yml
        content: |
          global:
            scrape_interval: 15s
          scrape_configs:
            - job_name: 'soc-nodes'
              static_configs:
                - targets:
                  - 'suricata.soc.local:9100'
                  - 'nginx.soc.local:9100'
                  - 'soar.soc.local:9100'

    - name: Iniciar servicios
      service:
        name: "{{ item }}"
        state: started
        enabled: yes
      loop:
        - grafana-server
        - prometheus
```

**Ejecución:**
```bash
ansible-playbook playbooks/despliegue/deploy-grafana.yml
```

---

### 3.2 `deploy-nginx.yml` — Despliegue de Nginx como reverse proxy

**Qué hace:**
Instala Nginx en CT 105, configura virtual hosts para exponer Grafana, SOAR y otros servicios internos bajo subdominios de `soc.local`, y configura cabeceras de seguridad.

**Requiere:**
- CT 105 con Debian 12
- Certificados SSL (autofirmados o Let's Encrypt interno)

```yaml
---
- name: Desplegar Nginx reverse proxy
  hosts: nginx.soc.local
  become: yes
  tasks:
    - name: Instalar Nginx
      apt:
        name: nginx
        state: present
        update_cache: yes

    - name: Configurar proxy para Grafana
      copy:
        dest: /etc/nginx/sites-available/grafana
        content: |
          server {
              listen 80;
              server_name grafana.soc.local;
              location / {
                  proxy_pass http://10.1.1.66:3000;
                  proxy_set_header Host $host;
                  proxy_set_header X-Real-IP $remote_addr;
              }
          }

    - name: Habilitar site
      file:
        src: /etc/nginx/sites-available/grafana
        dest: /etc/nginx/sites-enabled/grafana
        state: link

    - name: Reiniciar Nginx
      service:
        name: nginx
        state: restarted
        enabled: yes
```

**Ejecución:**
```bash
ansible-playbook playbooks/despliegue/deploy-nginx.yml
```

---

### 3.3 `deploy-suricata.yml` — Despliegue de Suricata IDS

**Qué hace:**
Instala Suricata 7.x en CT 106 desde el repositorio oficial OISF, configura `HOME_NET` con las subredes del SOC, activa las interfaces de captura `eth0` y `eth1`, habilita `et/open` y configura salida de alertas en formato JSON para el SIEM.

**Requiere:**
- CT 106 con Debian 12
- 2 interfaces de red (ya configuradas)
- Al menos 1 GB RAM

```yaml
---
- name: Desplegar Suricata IDS
  hosts: suricata.soc.local
  become: yes
  tasks:
    - name: Añadir repo OISF
      apt_repository:
        repo: "deb https://packages.oisf.net/suricata/7/debian bookworm main"
        state: present

    - name: Instalar Suricata
      apt:
        name: suricata
        state: present
        update_cache: yes

    - name: Configurar HOME_NET
      lineinfile:
        path: /etc/suricata/suricata.yaml
        regexp: 'HOME_NET:'
        line: '    HOME_NET: "[10.1.1.0/24]"'

    - name: Habilitar et/open y actualizar reglas
      command: "{{ item }}"
      loop:
        - suricata-update enable-source et/open
        - suricata-update

    - name: Iniciar Suricata
      service:
        name: suricata
        state: started
        enabled: yes
```

**Ejecución:**
```bash
ansible-playbook playbooks/despliegue/deploy-suricata.yml
```

---

### 3.4 `deploy-bind9.yml` — Despliegue de Bind9

**Qué hace:**
Instala Bind9 en CT 103, despliega la configuración de `named.conf.options`, crea las zonas `soc.local` y la zona inversa con todos los registros actuales, y deshabilita IPv6 para evitar errores de resolución.

**Requiere:**
- CT 103 con Debian 12
- Ficheros de zona en el repositorio de playbooks

```yaml
---
- name: Desplegar Bind9 DNS
  hosts: dns.soc.local
  become: yes
  tasks:
    - name: Instalar Bind9
      apt:
        name:
          - bind9
          - bind9utils
          - dnsutils
        state: present
        update_cache: yes

    - name: Desplegar named.conf.options
      copy:
        dest: /etc/bind/named.conf.options
        src: files/named.conf.options

    - name: Crear directorio de zonas
      file:
        path: /etc/bind/zones
        state: directory
        owner: bind

    - name: Desplegar zonas
      copy:
        dest: "/etc/bind/zones/{{ item }}"
        src: "files/{{ item }}"
      loop:
        - db.soc.local
        - db.10.1.1

    - name: Iniciar Bind9
      service:
        name: named
        state: started
        enabled: yes
```

**Ejecución:**
```bash
ansible-playbook playbooks/despliegue/deploy-bind9.yml
```

---

## CATEGORÍA 4 — Backup y Recuperación

### 4.1 `backup-configs.yml` — Backup de configuraciones críticas

**Qué hace:**
Recoge las configuraciones críticas de todos los servicios (Bind9, Suricata, Nginx, OpenWRT, Grafana dashboards) y las centraliza en CT 103 bajo `/opt/backups/` con fecha, comprimiéndolas en un tarball.

**Requiere:**
- Espacio suficiente en CT 103 (`/opt/backups/`)
- Acceso SSH a todos los contenedores

```yaml
---
- name: Backup de configuraciones SOC
  hosts: all
  become: yes
  vars:
    backup_date: "{{ ansible_date_time.date }}"
    backup_dest: "/opt/backups/{{ inventory_hostname }}/{{ backup_date }}"
  tasks:
    - name: Crear directorio de backup local
      file:
        path: "{{ backup_dest }}"
        state: directory
      delegate_to: dns.soc.local

    - name: Recoger configuraciones
      fetch:
        src: "{{ item }}"
        dest: "{{ backup_dest }}/"
        flat: no
        fail_on_missing: no
      loop:
        - /etc/nginx/
        - /etc/suricata/suricata.yaml
        - /etc/bind/
        - /etc/fail2ban/jail.local

    - name: Comprimir backup
      archive:
        path: "{{ backup_dest }}"
        dest: "{{ backup_dest }}.tar.gz"
        remove: yes
      delegate_to: dns.soc.local
```

**Ejecución:**
```bash
ansible-playbook playbooks/backup/backup-configs.yml
```

**Automatización:**
```bash
echo "0 2 * * 0 root ansible-playbook /etc/ansible/playbooks/backup/backup-configs.yml" > /etc/cron.d/soc-backup
```

---

### 4.2 `restore-configs.yml` — Restauración de configuraciones

**Qué hace:**
Restaura la configuración de un servicio concreto desde el backup más reciente disponible en CT 103, verifica la sintaxis antes de aplicar y reinicia el servicio.

**Requiere:**
- Backup previo realizado con `backup-configs.yml`
- Variable `target_host` y `backup_date` especificadas al ejecutar

```yaml
---
- name: Restaurar configuración desde backup
  hosts: "{{ target_host }}"
  become: yes
  vars:
    backup_src: "/opt/backups/{{ target_host }}/{{ backup_date }}.tar.gz"
  tasks:
    - name: Verificar que existe el backup
      stat:
        path: "{{ backup_src }}"
      register: backup_file
      delegate_to: dns.soc.local

    - name: Fallar si no existe el backup
      fail:
        msg: "No se encontró backup en {{ backup_src }}"
      when: not backup_file.stat.exists

    - name: Copiar y descomprimir backup
      unarchive:
        src: "{{ backup_src }}"
        dest: /tmp/restore/
        remote_src: no
```

**Ejecución:**
```bash
ansible-playbook playbooks/backup/restore-configs.yml \
  -e "target_host=suricata.soc.local backup_date=2026-03-20"
```

---

## CATEGORÍA 5 — Respuesta a Incidentes

### 5.1 `isolate-host.yml` — Aislamiento de contenedor comprometido

**Qué hace:**
Ante un incidente, elimina el forwarding de una VLAN en OpenWRT vía UCI, bloqueando todo el tráfico saliente del contenedor comprometido mientras se investiga. Mantiene acceso desde CT 103 para análisis forense.

**Requiere:**
- Acceso SSH a OpenWRT VM 201
- Variable `target_vlan` especificada al ejecutar

```yaml
---
- name: Aislar contenedor comprometido
  hosts: localhost
  vars:
    target_vlan: "vlan20"
  tasks:
    - name: Eliminar forwarding de la VLAN afectada
      command: >
        ssh root@192.168.3.201
        "uci delete firewall.@forwarding[$(uci show firewall | grep 'src={{ target_vlan }}' | grep -c .)];
         uci commit firewall;
         service firewall restart"

    - name: Registrar el aislamiento
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - AISLAMIENTO: {{ target_vlan }} bloqueada"
        create: yes
```

**Ejecución:**
```bash
ansible-playbook playbooks/incidentes/isolate-host.yml -e "target_vlan=vlan20"
```

---

### 5.2 `collect-evidence.yml` — Recolección de evidencias forenses

**Qué hace:**
Recoge evidencias básicas de un contenedor sospechoso: procesos activos, conexiones de red, usuarios logueados, últimos comandos ejecutados, crontabs, y logs recientes. Lo empaqueta todo con hash SHA256 para cadena de custodia.

**Requiere:**
- Acceso SSH al contenedor objetivo
- `procps`, `net-tools` instalados en el objetivo

```yaml
---
- name: Recolectar evidencias forenses
  hosts: "{{ target_host }}"
  become: yes
  vars:
    evidence_dir: "/opt/evidence/{{ inventory_hostname }}/{{ ansible_date_time.iso8601_basic }}"
  tasks:
    - name: Crear directorio de evidencias
      file:
        path: "{{ evidence_dir }}"
        state: directory
      delegate_to: dns.soc.local

    - name: Recoger procesos, conexiones y usuarios
      shell: "{{ item.cmd }} > {{ evidence_dir }}/{{ item.file }} 2>&1"
      loop:
        - { cmd: "ps auxf", file: "processes.txt" }
        - { cmd: "ss -tulpn", file: "network_connections.txt" }
        - { cmd: "who", file: "logged_users.txt" }
        - { cmd: "last -20", file: "last_logins.txt" }
        - { cmd: "crontab -l", file: "crontab_root.txt" }
        - { cmd: "find /tmp -type f -newer /proc/1", file: "tmp_files.txt" }
      delegate_to: "{{ inventory_hostname }}"
      ignore_errors: yes

    - name: Generar hashes SHA256
      shell: "sha256sum {{ evidence_dir }}/* > {{ evidence_dir }}/checksums.sha256"
      delegate_to: dns.soc.local
```

**Ejecución:**
```bash
ansible-playbook playbooks/incidentes/collect-evidence.yml -e "target_host=soar.soc.local"
```

---

### 5.3 `block-ip.yml` — Bloqueo de IP maliciosa en Suricata

**Qué hace:**
Añade una regla `drop` en Suricata para bloquear una IP maliciosa específica en todas las direcciones (entrada y salida), recarga las reglas en caliente y registra el bloqueo en el log de incidentes.

**Requiere:**
- Suricata operativo en CT 106
- Variable `malicious_ip` especificada al ejecutar

```yaml
---
- name: Bloquear IP maliciosa en Suricata
  hosts: suricata.soc.local
  become: yes
  vars:
    malicious_ip: ""
    rules_file: /etc/suricata/rules/local.rules
  tasks:
    - name: Añadir regla drop para la IP
      lineinfile:
        path: "{{ rules_file }}"
        line: >
          drop ip {{ malicious_ip }} any -> $HOME_NET any
          (msg:"SOC Block - Malicious IP {{ malicious_ip }}";
          sid:9000001; rev:1;)
        create: yes

    - name: Recargar reglas en caliente
      command: suricatasc -c reload-rules

    - name: Registrar bloqueo
      lineinfile:
        path: /var/log/soc-incidents.log
        line: "{{ ansible_date_time.iso8601 }} - BLOQUEO IP: {{ malicious_ip }}"
        create: yes
      delegate_to: dns.soc.local
```

**Ejecución:**
```bash
ansible-playbook playbooks/incidentes/block-ip.yml -e "malicious_ip=1.2.3.4"
```

---

## Orden de implementación recomendado

| Fase | Playbook | Prioridad |
|------|----------|-----------|
| 1 | Instalar Ansible en CT 103 | Inmediata |
| 2 | Distribuir claves SSH | Inmediata |
| 3 | `harden-ssh.yml` | Alta |
| 4 | `fail2ban.yml` | Alta |
| 5 | `update-all.yml` + cron | Alta |
| 6 | `suricata-rules.yml` + cron | Alta |
| 7 | `logs-rotation.yml` | Media |
| 8 | `usuarios.yml` | Media |
| 9 | `backup-configs.yml` + cron | Media |
| 10 | `deploy-*.yml` | Según necesidad |
| 11 | `isolate-host.yml` | Antes del primer incidente |
| 12 | `collect-evidence.yml` | Antes del primer incidente |
| 13 | `block-ip.yml` | Antes del primer incidente |
| 14 | `iocs-sync.yml` | Cuando SIEM esté operativo |
