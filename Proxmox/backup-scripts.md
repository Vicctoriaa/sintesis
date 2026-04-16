# Scripts de Backup — SOC honeycos


## 1. Visión general

El sistema de backup del SOC consta de dos scripts que trabajan en cadena:

| Script | Máquina | Función |
|--------|---------|---------|
| `backup-sync.sh` | honeycos (192.168.3.200) | Genera backups de CTs/VMs y los sincroniza a honeycos-bk |
| `organizar-backups.sh` | honeycos-bk (192.168.3.111) | Comprime, rota y limpia los backups recibidos |

Ambos scripts envían alertas por correo al finalizar via CT108 (Postfix relay).

---

## 2. backup-sync.sh

### Ubicación
```
/root/victor/backup-sync.sh
```

### Ejecución
```bash
# Manual
bash /root/victor/backup-sync.sh

# Cron (domingos 2:00)
0 2 * * 0 /bin/bash /root/victor/backup-sync.sh
```

### Funcionamiento

**Paso 1 — Backup CTs (modo suspend)**

Hace backup de los siguientes CTs usando `vzdump` con compresión zstd:

| CT | Servicio |
|----|---------|
| 100 | LDAP |
| 101 | Grafana-Prometheus |
| 102 | Vaultwarden |
| 103 | DNS-Ansible |
| 104 | SOAR |
| 105 | Nginx |
| 106 | Suricata |
| 107 | Homepage |
| 108 | Correo |
| 200 | VPN |

**Paso 2 — Backup VMs (modo snapshot)**

| VM | Servicio |
|----|---------|
| 201 | OpenWRT |
| 202 | Wazuh SIEM |
| 203 | Honeypot |

**Paso 3 — Rsync a honeycos-bk**

Los ficheros generados en esa ejecución se sincronizan a `honeycos-bk:/backups/proxmox/YYYY-MM-DD/` via rsync sobre SSH.

**Paso 4 — Alerta por correo**

Al finalizar envía un email con el resumen completo:
- Asunto `[SOC] Backup OK - YYYY-MM-DD` si todo fue bien
- Asunto `[SOC] Backup FAILED - YYYY-MM-DD` si hubo algún fallo

### Variables configurables

```bash
BACKUP_DIR="/var/lib/vz/dump"      # Directorio local de backups Proxmox
REMOTE_USER="backupuser"            # Usuario SSH en honeycos-bk
REMOTE_HOST="192.168.3.111"        # IP de honeycos-bk
REMOTE_BASE="/backups/proxmox"     # Directorio base en honeycos-bk
EMAIL="telenecos9@gmail.com"       # Destinatario de alertas
```

### Log
```
/var/log/backup-sync-soc-YYYYMMDD-HHMMSS.log
```

---

## 3. organizar-backups.sh

### Ubicación
```
/home/backupuser/organizar-backups.sh
```

### Ejecución
```bash
# Manual
bash /home/backupuser/organizar-backups.sh

# Cron (domingos 6:00)
0 6 * * 0 /bin/bash /home/backupuser/organizar-backups.sh
```

### Política de retención

| Tipo | Limite | Ubicación |
|------|--------|-----------|
| Carpetas sin comprimir | 3 días | `/backups/proxmox/YYYY-MM-DD/` |
| Archives comprimidos | 5 archives | `/backups/proxmox/archives/` |

Los backups más recientes se mantienen sin comprimir para acceso rápido. Los más antiguos se comprimen en `.tar.gz` y se mueven a `archives/`. Cuando hay más de 5 archives se eliminan los más antiguos.

### Funcionamiento

**Parte 1 — Comprimir carpetas antiguas**

- Detecta todas las carpetas `YYYY-MM-DD` en `/backups/proxmox/`
- Comprime a `archives/` todas las que superen los 3 más recientes
- Si el archive ya existe, elimina solo la carpeta sin volver a comprimir

**Parte 2 — Limpieza de retención**

- Si quedan más de 3 carpetas sin comprimir → elimina las más antiguas
- Si hay más de 5 archives → elimina los más antiguos

**Parte 3 — Alerta por correo**

Al finalizar envía un email con:
- Estado (OK / FAILED)
- Listado de carpetas sin comprimir con tamaño
- Listado de archives con tamaño
- Espacio en disco
- Log completo de la ejecución

### Variables configurables

```bash
BACKUP_DIR="/backups/proxmox"          # Directorio de backups
ARCHIVE_DIR="/backups/proxmox/archives" # Directorio de archives
MAX_DIAS=3                              # Dias maximos sin comprimir
MAX_ARCHIVES=5                          # Archives maximos a conservar
EMAIL="telenecos9@gmail.com"           # Destinatario de alertas
```

### Log
```
/home/backupuser/organizar-backups-YYYYMMDD-HHMMSS.log
```

---

## 4. Estructura de directorios en honeycos-bk

```
/backups/proxmox/
├── 2026-04-14/          # Dia reciente (sin comprimir)
│   ├── vzdump-lxc-100-...zst
│   └── vzdump-qemu-202-...zst
├── 2026-04-15/          # Dia reciente (sin comprimir)
├── 2026-04-16/          # Dia reciente (sin comprimir)
└── archives/
    ├── 2026-04-01.tar.gz   # Backup comprimido (mas antiguo)
    ├── 2026-04-07.tar.gz
    ├── 2026-04-08.tar.gz
    ├── 2026-04-09.tar.gz
    └── 2026-04-10.tar.gz   # Backup comprimido (mas reciente)
```

---

## 5. Crontabs

### honeycos (Proxmox)

```bash
# Ver crontab
crontab -l

# Entrada esperada
0 2 * * 0 /bin/bash /root/victor/backup-sync.sh
```

### honeycos-bk

```bash
# Ver crontab
crontab -l

# Entrada esperada
0 6 * * 0 /bin/bash /home/backupuser/organizar-backups.sh
```

---

## 6. Flujo completo dominical

```
Dom 02:00 - honeycos ejecuta backup-sync.sh
            |
            |- vzdump CT100...CT200 (suspend)
            |- vzdump VM201...VM203 (snapshot)
            |- rsync -> honeycos-bk:/backups/proxmox/YYYY-MM-DD/
            |- email [SOC] Backup OK/FAILED

Dom 06:00 - honeycos-bk ejecuta organizar-backups.sh
            |
            |- comprime carpetas > 3 dias -> archives/
            |- elimina carpetas sobrantes
            |- elimina archives sobrantes (max 5)
            |- email [SOC] Organizacion Backups OK/FAILED
```

---

## 7. Troubleshooting

### El backup falla para un CT/VM específico

```bash
# Verificar estado del CT/VM
pct status 101
qm status 202

# Ejecutar backup manual de un CT
vzdump 101 --storage local --mode suspend --compress zstd

# Ver log del ultimo backup
ls -lt /var/log/backup-sync-soc-*.log | head -1
tail -50 /var/log/backup-sync-soc-YYYYMMDD-HHMMSS.log
```

### El rsync falla

```bash
# Verificar conectividad con honeycos-bk
ssh backupuser@192.168.3.111

# Verificar espacio en honeycos-bk
df -h /backups/
```

### El email no llega

```bash
# Verificar postfix en honeycos
postfix status
mailq

# Verificar log en CT108
tail -20 /var/log/syslog
```

### El script de organización no comprime

```bash
# Verificar espacio libre en honeycos-bk
df -h /backups/

# Ejecutar manualmente
bash /home/backupuser/organizar-backups.sh
```

---

*Documentacion actualizada 2026-04-16*
