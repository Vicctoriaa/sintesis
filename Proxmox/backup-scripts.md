# Scripts de Backup — SOC honeycos


## 1. Visión general

> El sistema de backup está diseñado en dos fases separadas y ejecutadas en máquinas distintas. El primer script genera y exporta los backups desde el nodo Proxmox principal; el segundo los recibe, organiza y rota en la máquina de almacenamiento dedicada. Las alertas por correo permiten supervisar el resultado sin necesidad de acceder manualmente a los sistemas.

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

> El script puede lanzarse manualmente para pruebas o verificaciones puntuales, o dejarse programado en cron para ejecución automática cada domingo a las 2:00 AM, hora de baja actividad para minimizar el impacto en los servicios.

```bash
# Manual
bash /root/victor/backup-sync.sh

# Cron (domingos 2:00)
0 2 * * 0 /bin/bash /root/victor/backup-sync.sh
```

### Funcionamiento

**Paso 1 — Backup CTs (modo suspend)**

> `vzdump` con modo `suspend` pausa brevemente el contenedor durante el backup para garantizar la consistencia de los datos, evitando que queden escrituras a medias. Se usa compresión `zstd` por su buen equilibrio entre velocidad y ratio de compresión.

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

> Las VMs usan el modo `snapshot` en lugar de `suspend`: se crea una instantánea del disco en caliente sin detener la máquina virtual, lo que permite hacer el backup sin interrumpir el servicio. Es el método adecuado para VMs con mayor criticidad o tiempo de parada inaceptable.

| VM | Servicio |
|----|---------|
| 201 | OpenWRT |
| 202 | Wazuh SIEM |
| 203 | Honeypot |

**Paso 3 — Rsync a honeycos-bk**

> Una vez generados los ficheros de backup en el directorio local de Proxmox, se transfieren a la máquina de almacenamiento mediante `rsync` sobre SSH. Solo se envían los ficheros generados en esa ejecución, organizados bajo una carpeta con la fecha del día (`YYYY-MM-DD`), lo que facilita la localización y rotación posterior.

Los ficheros generados en esa ejecución se sincronizan a `honeycos-bk:/backups/proxmox/YYYY-MM-DD/` via rsync sobre SSH.

**Paso 4 — Alerta por correo**

> El resumen por correo permite saber de un vistazo si el backup dominical completó correctamente sin tener que revisar logs manualmente. El asunto cambia según el resultado para facilitar el filtrado en el cliente de correo.

Al finalizar envía un email con el resumen completo:
- Asunto `[SOC] Backup OK - YYYY-MM-DD` si todo fue bien
- Asunto `[SOC] Backup FAILED - YYYY-MM-DD` si hubo algún fallo

### Variables configurables

> Estas variables centralizan toda la configuración del script. Modificándolas se puede adaptar el script a otro entorno sin tocar la lógica interna.

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

> Se programa 4 horas después de `backup-sync.sh` para asegurar que la transferencia rsync ha terminado antes de que empiece la organización. El usuario `backupuser` es un usuario sin privilegios dedicado exclusivamente a la gestión de backups, siguiendo el principio de mínimo privilegio.

```bash
# Manual
bash /home/backupuser/organizar-backups.sh

# Cron (domingos 6:00)
0 6 * * 0 /bin/bash /home/backupuser/organizar-backups.sh
```

### Política de retención

> Esta política equilibra accesibilidad y ahorro de espacio: los backups recientes se mantienen sin comprimir para poder restaurar rápidamente si fuera necesario, mientras que los más antiguos se comprimen para ocupar menos espacio. El límite de 5 archives garantiza disponer de historial de más de un mes sin consumo excesivo de disco.

| Tipo | Limite | Ubicación |
|------|--------|-----------|
| Carpetas sin comprimir | 3 días | `/backups/proxmox/YYYY-MM-DD/` |
| Archives comprimidos | 5 archives | `/backups/proxmox/archives/` |

Los backups más recientes se mantienen sin comprimir para acceso rápido. Los más antiguos se comprimen en `.tar.gz` y se mueven a `archives/`. Cuando hay más de 5 archives se eliminan los más antiguos.

### Funcionamiento

**Parte 1 — Comprimir carpetas antiguas**

> El script ordena las carpetas por fecha y comprime todas excepto las 3 más recientes. Si el archivo `.tar.gz` ya existe (por ejemplo, por una ejecución anterior fallida a medias), elimina la carpeta directamente sin recomprimir para evitar duplicados y trabajo innecesario.

- Detecta todas las carpetas `YYYY-MM-DD` en `/backups/proxmox/`
- Comprime a `archives/` todas las que superen los 3 más recientes
- Si el archive ya existe, elimina solo la carpeta sin volver a comprimir

**Parte 2 — Limpieza de retención**

> Una vez completada la compresión, se aplican los límites configurados. Primero se revisan las carpetas sin comprimir y luego los archives, eliminando siempre los más antiguos para respetar los máximos definidos en las variables.

- Si quedan más de 3 carpetas sin comprimir → elimina las más antiguas
- Si hay más de 5 archives → elimina los más antiguos

**Parte 3 — Alerta por correo**

> El informe incluye el estado de los directorios y el espacio disponible, lo que permite detectar de forma proactiva si el disco se está llenando o si la rotación no está funcionando como se espera.

Al finalizar envía un email con:
- Estado (OK / FAILED)
- Listado de carpetas sin comprimir con tamaño
- Listado de archives con tamaño
- Espacio en disco
- Log completo de la ejecución

### Variables configurables

> Al igual que en el primer script, toda la configuración está centralizada para facilitar el mantenimiento y la adaptación a otros entornos.

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

> Esta estructura refleja el estado típico de `honeycos-bk` en un domingo después de que ambos scripts han ejecutado correctamente. Las tres carpetas sin comprimir corresponden a las últimas semanas; los archives contienen el historial comprimido de semanas anteriores.

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

> Los crontabs están definidos en el usuario `root` de honeycos y en el usuario `backupuser` de honeycos-bk respectivamente. Se puede verificar en cualquier momento que las entradas están correctamente configuradas con `crontab -l`.

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

> Este diagrama resume la cadena de eventos completa cada domingo. El desfase de 4 horas entre los dos scripts garantiza que el rsync haya terminado antes de que empiece la organización, evitando condiciones de carrera.

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

> Esta sección recoge los comandos necesarios para diagnosticar y resolver los problemas más comunes. En todos los casos, revisar el log de la ejecución fallida es el primer paso recomendado antes de actuar.

### El backup falla para un CT/VM específico

> Un CT o VM puede estar en estado incorrecto (parado, bloqueado, en error) o el almacenamiento local puede haberse quedado sin espacio. Verificar el estado del recurso antes de lanzar un backup manual ayuda a descartar estas causas.

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

> Los fallos de rsync suelen deberse a problemas de conectividad SSH, permisos incorrectos del usuario `backupuser` o falta de espacio en el destino. Verificar que la conexión SSH funciona manualmente descarta la mayoría de problemas de autenticación o red.

```bash
# Verificar conectividad con honeycos-bk
ssh backupuser@192.168.3.111

# Verificar espacio en honeycos-bk
df -h /backups/
```

### El email no llega

> El correo se envía a través del relay Postfix del CT108. Si el email no llega, hay que verificar que Postfix está activo y que no hay mensajes encolados (lo que indicaría un problema de entrega hacia el servidor SMTP externo).

```bash
# Verificar postfix en honeycos
postfix status
mailq

# Verificar log en CT108
tail -20 /var/log/syslog
```

### El script de organización no comprime

> Si el script no comprime las carpetas, lo más habitual es que no haya espacio suficiente en disco para crear los `.tar.gz`. También se puede ejecutar manualmente para ver la salida en tiempo real y detectar el error exacto.

```bash
# Verificar espacio libre en honeycos-bk
df -h /backups/

# Ejecutar manualmente
bash /home/backupuser/organizar-backups.sh
```

---

*Documentacion actualizada 2026-04-16*
