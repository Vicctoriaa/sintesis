# Sistema de Backups — SOC honeycos

## Arquitectura general

```
honeycos (192.168.3.200)          honeycos-bk (192.168.3.111)
┌─────────────────────┐           ┌─────────────────────────────┐
│  /var/lib/vz/dump/  │  rsync    │  /backups/proxmox/          │
│  vzdump-lxc-*.zst   │ ───────►  │  ├── 2026-03-27/            │
│  vzdump-qemu-*.zst  │           │  │   └── vzdump-*.zst        │
└─────────────────────┘           │  └── archives/              │
                                  │      └── 2026-03-26.tar.gz  │
                                  └─────────────────────────────┘
```

**Flujo semanal (domingos):**
1. 02:00 — `backup-all.sh` genera los backups en Proxmox
2. 05:00 — `rsync-backups.sh` envía los últimos backups al servidor remoto
3. 06:00 — `organizar-backups.sh` organiza y comprime en honeycos-bk

---

## Scripts

### 1. backup-all.sh
**Ubicación:** `/root/victor/backup-all.sh`
**Host:** honeycos (Proxmox)
**Función:** Genera backups de todos los CTs y VMs con `vzdump`

```bash
#!/bin/bash
# ============================================================
#  SOC honeycos — Backup completo de CTs y VMs
# ============================================================
SEP="──────────────────────────────────────────────"
LOG="/var/log/backup-soc-$(date +%Y%m%d-%H%M%S).log"

H() { echo; echo "╔══ $1" | tee -a $LOG; echo "$SEP" | tee -a $LOG; }
OK() { echo "  ✓ $1" | tee -a $LOG; }
ERR() { echo "  ✗ ERROR: $1" | tee -a $LOG; }

H "Backup SOC — $(date)"

# CTs — modo suspend (loop disks no soportan snapshot)
for VMID in 100 101 103 104 105 106 200; do
    STATUS=$(pct status $VMID 2>/dev/null | awk '{print $2}')
    if [ "$STATUS" = "running" ] || [ "$STATUS" = "stopped" ]; then
        echo | tee -a $LOG
        echo "  → Backup CT$VMID..." | tee -a $LOG
        vzdump $VMID --storage local --mode suspend --compress zstd 2>&1 | tee -a $LOG
        [ ${PIPESTATUS[0]} -eq 0 ] && OK "CT$VMID completado" || ERR "CT$VMID falló"
    else
        ERR "CT$VMID no encontrado"
    fi
done

# VMs — modo snapshot
for VMID in 201 202; do
    STATUS=$(qm status $VMID 2>/dev/null | awk '{print $2}')
    if [ "$STATUS" = "running" ] || [ "$STATUS" = "stopped" ]; then
        echo | tee -a $LOG
        echo "  → Backup VM$VMID..." | tee -a $LOG
        vzdump $VMID --storage local --mode snapshot --compress zstd 2>&1 | tee -a $LOG
        [ ${PIPESTATUS[0]} -eq 0 ] && OK "VM$VMID completado" || ERR "VM$VMID falló"
    else
        ERR "VM$VMID no encontrado"
    fi
done

H "Backups completados — $(date)"
echo "  Log guardado en: $LOG"
```

**Máquinas incluidas:**

| VMID | Tipo | Nombre | Modo backup |
|------|------|--------|-------------|
| 100 | LXC | LDAP | suspend |
| 101 | LXC | Grafana-Prometheus | suspend |
| 103 | LXC | playbooks-dns | suspend |
| 104 | LXC | Soar-web | suspend |
| 105 | LXC | nginx-proxy | suspend |
| 106 | LXC | suricata-ids | suspend |
| 200 | LXC | vpn-server | suspend |
| 201 | QEMU | openwrt-fw | snapshot |
| 202 | QEMU | wazuh-siem | snapshot |

**Notas:**
- Los CTs usan modo `suspend` porque los discos loop no soportan snapshot
- Las VMs usan modo `snapshot` para backup en caliente sin parada
- Los backups se guardan en `/var/lib/vz/dump/` comprimidos con zstd
- Los logs se guardan en `/var/log/backup-soc-YYYYMMDD-HHMMSS.log`

---

### 2. rsync-backups.sh
**Ubicación:** `/root/victor/rsync-backups.sh`
**Host:** honeycos (Proxmox)
**Función:** Envía el último backup de cada CT/VM al servidor remoto organizados por fecha

```bash
#!/bin/bash
# ============================================================
#  SOC honeycos — Rsync últimos backups a servidor remoto
# ============================================================

BACKUP_DIR="/var/lib/vz/dump"
REMOTE_USER="backupuser"
REMOTE_HOST="192.168.3.111"
REMOTE_BASE="/backups/proxmox"
FECHA=$(date +%Y-%m-%d)
REMOTE_DIR="${REMOTE_BASE}/${FECHA}/"
LOG="/var/log/rsync-soc-$(date +%Y%m%d-%H%M%S).log"

SEP="──────────────────────────────────────────────"
H() { echo; echo "╔══ $1" | tee -a $LOG; echo "$SEP" | tee -a $LOG; }
OK() { echo "  ✓ $1" | tee -a $LOG; }
ERR() { echo "  ✗ ERROR: $1" | tee -a $LOG; }

H "Rsync backups SOC — $(date)"
echo "  Destino: ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}" | tee -a $LOG

# Crear carpeta remota con la fecha de hoy
ssh ${REMOTE_USER}@${REMOTE_HOST} "mkdir -p ${REMOTE_DIR}"

# Obtener el último backup de cada CT/VM
for VMID in 100 101 103 104 105 106 200 201 202; do
    LATEST=$(ls -t $BACKUP_DIR/vzdump-*-${VMID}-*.zst 2>/dev/null | head -1)

    if [ -z "$LATEST" ]; then
        echo "  → VM/CT $VMID: sin backup encontrado, saltando" | tee -a $LOG
        continue
    fi

    LATEST_LOG="${LATEST%.zst}.log"

    echo "  → Enviando $VMID: $(basename $LATEST)" | tee -a $LOG

    rsync -avz --progress \
        "$LATEST" \
        $([ -f "$LATEST_LOG" ] && echo "$LATEST_LOG") \
        ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR} 2>&1 | tee -a $LOG

    [ ${PIPESTATUS[0]} -eq 0 ] && OK "VM/CT $VMID enviado" || ERR "VM/CT $VMID falló"
done

H "Rsync completado — $(date)"
echo "  Log guardado en: $LOG"
```

**Notas:**
- Solo envía el backup más reciente de cada máquina
- Crea automáticamente una carpeta con la fecha del día en el servidor remoto (`/backups/proxmox/YYYY-MM-DD/`)
- La autenticación SSH usa clave `ed25519` sin contraseña
- También envía el fichero `.log` de cada backup si existe
- Los logs se guardan en `/var/log/rsync-soc-YYYYMMDD-HHMMSS.log`

**Requisito previo — clave SSH:**
```bash
ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
ssh-copy-id backupuser@192.168.3.111
```

---

### 3. organizar-backups.sh
**Ubicación:** `/home/backupuser/organizar-backups.sh`
**Host:** honeycos-bk (192.168.3.111)
**Función:** Organiza los backups por fecha y comprime carpetas antiguas

```bash
#!/bin/bash
# ============================================================
#  honeycos-bk — Organizar y comprimir backups por fecha
# ============================================================

BACKUP_DIR="/backups/proxmox"
ARCHIVE_DIR="/backups/proxmox/archives"
LOG="/home/backupuser/organizar-backups-$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$ARCHIVE_DIR"

SEP="──────────────────────────────────────────────"
H() { echo; echo "╔══ $1" | tee -a $LOG; echo "$SEP" | tee -a $LOG; }
OK() { echo "  ✓ $1" | tee -a $LOG; }
ERR() { echo "  ✗ ERROR: $1" | tee -a $LOG; }

H "Organización backups — $(date)"

# 1. Mover ficheros sueltos a su carpeta por fecha
echo "  → Organizando ficheros por fecha..." | tee -a $LOG
for FILE in $BACKUP_DIR/vzdump-*.zst; do
    [ -f "$FILE" ] || continue
    FECHA=$(basename "$FILE" | grep -oP '\d{4}_\d{2}_\d{2}' | head -1 | tr '_' '-')
    [ -z "$FECHA" ] && continue
    DESTDIR="$BACKUP_DIR/$FECHA"
    mkdir -p "$DESTDIR"
    mv "$FILE" "$DESTDIR/"
    echo "    $(basename $FILE) → $FECHA/" | tee -a $LOG
done

# 2. Comprimir carpetas de días anteriores (no el día de hoy)
HOY=$(date +%Y-%m-%d)
echo | tee -a $LOG
echo "  → Comprimiendo carpetas antiguas..." | tee -a $LOG

for DIR in $BACKUP_DIR/????-??-??; do
    [ -d "$DIR" ] || continue
    DIRNAME=$(basename "$DIR")
    [ "$DIRNAME" = "$HOY" ] && continue
    [ -f "$ARCHIVE_DIR/$DIRNAME.tar.gz" ] && continue

    echo "    Comprimiendo $DIRNAME..." | tee -a $LOG
    tar -czf "$ARCHIVE_DIR/$DIRNAME.tar.gz" -C "$BACKUP_DIR" "$DIRNAME" 2>&1 | tee -a $LOG

    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        rm -rf "$DIR"
        OK "$DIRNAME comprimido y carpeta eliminada"
    else
        ERR "$DIRNAME falló al comprimir"
    fi
done

H "Resumen de espacio"
df -h /backups/ | tee -a $LOG
du -sh $BACKUP_DIR/ | tee -a $LOG
du -sh $ARCHIVE_DIR/ 2>/dev/null | tee -a $LOG

H "Organización completada — $(date)"
echo "  Log: $LOG"
```

**Notas:**
- La carpeta del día actual nunca se comprime
- Las carpetas de días anteriores se comprimen en `archives/YYYY-MM-DD.tar.gz` y se eliminan
- Si ya existe el `.tar.gz` de un día, no lo vuelve a comprimir
- Los logs se guardan en `/home/backupuser/organizar-backups-YYYYMMDD-HHMMSS.log`

**Estructura resultante en honeycos-bk:**
```
/backups/proxmox/
├── 2026-03-27/                    ← día actual (sin comprimir)
│   ├── vzdump-lxc-100-....tar.zst
│   ├── vzdump-lxc-101-....tar.zst
│   └── ...
└── archives/                      ← días anteriores (comprimidos)
    ├── 2026-03-26.tar.gz
    └── 2026-03-25.tar.gz
```

---

## Automatización — Cron

### honeycos (Proxmox) — `/etc/cron.d/soc-backup`

```
# Backup completo domingos a las 2:00
0 2 * * 0 root /root/victor/backup-all.sh

# Rsync a servidor remoto domingos a las 5:00
0 5 * * 0 root /root/victor/rsync-backups.sh

# Organizar en servidor remoto domingos a las 6:00
0 6 * * 0 root ssh backupuser@192.168.3.111 '/home/backupuser/organizar-backups.sh'
```

### CT106 Suricata — `/etc/cron.d/suricata-update`

```
# Actualización reglas Suricata diaria a las 3:00
0 3 * * * root /usr/bin/suricata-update && kill -USR2 $(cat /run/suricata.pid)
```

---

## Espacio en disco

| Host | Filesystem | Tamaño | Usado | Libre |
|------|-----------|--------|-------|-------|
| honeycos | rpool (ZFS) | 460G | 12G | 448G |
| honeycos-bk | ubuntu-vg | 98G | 17G | 81G |

---

## Restauración

Para restaurar un backup en Proxmox:

```bash
# Restaurar CT
pct restore <VMID> /var/lib/vz/dump/vzdump-lxc-<VMID>-<fecha>.tar.zst --storage local

# Restaurar VM
qm restore <VMID> /var/lib/vz/dump/vzdump-qemu-<VMID>-<fecha>.vma.zst --storage local-zfs
```

Si el backup está en honeycos-bk, primero hay que extraerlo del archivo:

```bash
# En honeycos-bk
cd /backups/proxmox/archives/
tar -xzf 2026-03-26.tar.gz

# Luego copiar a honeycos con rsync
rsync -avz /backups/proxmox/2026-03-26/vzdump-lxc-101-*.tar.zst root@192.168.3.200:/var/lib/vz/dump/
```
