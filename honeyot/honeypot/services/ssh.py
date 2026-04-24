"""
services/ssh.py — Servicio SSH falso (paramiko)
Puerto 22 · Honeypot VM203

Mejoras v2:
  - Soporte de pipes (|), redirecciones (>), encadenamiento (&&, ;)
  - Historial largo y realista (~120 entradas)
  - Delay artificial de respuesta por comando (anti-scanner fingerprinting)
  - Hostname consistente con config.yaml en todos los contextos
  - Más comandos: wget, curl, crontab, df, free, last, who, find, tar
  - Captura enriquecida: username + password en login_attempt
"""

import asyncio
import random
import socket
import textwrap
import threading
import time
from typing import Optional

import paramiko

from core.logger import get_logger
from core.alerts import BruteForceDetector


# ---------------------------------------------------------------------------
# Filesystem falso
# ---------------------------------------------------------------------------

FAKE_FS = {
    "/": ["bin", "boot", "dev", "etc", "home", "lib", "opt", "proc",
          "root", "run", "srv", "sys", "tmp", "usr", "var"],
    "/root": [".bash_history", ".bashrc", ".profile", ".ssh",
              "backup.sh", "notes.txt", "deploy.sh"],
    "/root/.ssh": ["authorized_keys", "id_rsa", "id_rsa.pub", "known_hosts"],
    "/etc": ["passwd", "shadow", "hostname", "hosts", "fstab",
             "crontab", "ssh", "apt", "nginx", "mysql", "cron.d"],
    "/etc/nginx": ["nginx.conf", "sites-enabled", "sites-available"],
    "/etc/cron.d": ["backup", "cleanup"],
    "/var/log": ["auth.log", "syslog", "kern.log", "dpkg.log",
                 "nginx", "mysql", "fail2ban.log"],
    "/var/log/nginx": ["access.log", "error.log"],
    "/var/www": ["html"],
    "/var/www/html": ["index.html", "wp-config.php", ".htaccess"],
    "/tmp": ["sess_abc123", "tmpfile_deploy"],
    "/opt": ["honeypot", "backup"],
    "/home": ["ubuntu", "deploy"],
    "/home/ubuntu": [".bashrc", ".profile", ".bash_history"],
    "/home/deploy": [".bashrc", ".ssh"],
}

# ---------------------------------------------------------------------------
# Historial largo y realista
# ---------------------------------------------------------------------------

FAKE_HISTORY = """\
    1  apt update && apt upgrade -y
    2  apt install -y nginx mysql-server php8.1-fpm
    3  systemctl enable nginx mysql
    4  systemctl start nginx mysql
    5  mysql_secure_installation
    6  mysql -u root -p
    7  vim /etc/mysql/mysql.conf.d/mysqld.cnf
    8  systemctl restart mysql
    9  adduser deploy
   10  usermod -aG sudo deploy
   11  su - deploy
   12  mkdir -p /var/www/html
   13  chown -R deploy:www-data /var/www/html
   14  chmod 2750 /var/www/html
   15  vim /etc/nginx/sites-available/default
   16  nginx -t
   17  systemctl reload nginx
   18  certbot --nginx -d honeypot.soc.local
   19  ls /etc/letsencrypt/live/
   20  crontab -e
   21  cat /etc/cron.d/backup
   22  vim /root/backup.sh
   23  chmod +x /root/backup.sh
   24  bash /root/backup.sh
   25  df -h
   26  du -sh /var/www/html
   27  free -m
   28  top
   29  ps aux | grep nginx
   30  ps aux | grep mysql
   31  netstat -tlnp
   32  ss -tlnp
   33  ufw status
   34  ufw allow 80
   35  ufw allow 443
   36  ufw allow 22
   37  ufw enable
   38  tail -f /var/log/nginx/access.log
   39  tail -f /var/log/auth.log
   40  grep "Failed password" /var/log/auth.log | tail -20
   41  grep "Accepted password" /var/log/auth.log
   42  cat /var/log/fail2ban.log | tail -30
   43  fail2ban-client status sshd
   44  vim /etc/fail2ban/jail.local
   45  systemctl restart fail2ban
   46  whoami
   47  id
   48  hostname
   49  uname -a
   50  uptime
   51  w
   52  last -n 20
   53  who
   54  cat /etc/passwd | grep -v nologin
   55  cat /etc/shadow
   56  ls -la /root
   57  ls -la /home
   58  find /var/www -name "*.php" -mtime -1
   59  find /tmp -type f
   60  find / -perm -4000 2>/dev/null
   61  env
   62  export DB_PASSWORD=Sup3rS3cr3t!
   63  mysql -u dbadmin -p production
   64  mysqldump -u dbadmin -p production > /tmp/prod_backup.sql
   65  gzip /tmp/prod_backup.sql
   66  scp /tmp/prod_backup.sql.gz backup@10.1.1.50:/backups/
   67  rm /tmp/prod_backup.sql.gz
   68  cd /var/www/html
   69  ls -la
   70  cat wp-config.php
   71  vim wp-config.php
   72  php -l wp-config.php
   73  curl -I http://localhost
   74  curl -sk https://localhost | head -20
   75  wget -q http://192.168.1.112/health -O /dev/null
   76  ip a
   77  ip route
   78  cat /etc/hosts
   79  cat /etc/resolv.conf
   80  ping -c 3 10.1.1.1
   81  traceroute 8.8.8.8
   82  nmap -sV -p 22,80,443 localhost
   83  ss -s
   84  iftop -i eth0
   85  iostat
   86  vmstat 1 5
   87  lscpu
   88  cat /proc/meminfo | head -10
   89  cat /proc/cpuinfo | grep "model name" | head -1
   90  dmesg | tail -20
   91  journalctl -u nginx --since "1 hour ago"
   92  journalctl -u mysql -n 50
   93  systemctl list-units --state=failed
   94  timedatectl
   95  date
   96  ntpq -p
   97  dpkg -l | grep -E "nginx|mysql|php"
   98  apt list --installed 2>/dev/null | wc -l
   99  cat /etc/apt/sources.list
  100  tar -czf /tmp/etc_backup.tar.gz /etc/nginx /etc/mysql
  101  ls -lh /tmp/etc_backup.tar.gz
  102  rm /tmp/etc_backup.tar.gz
  103  history | grep mysql
  104  history | grep password
  105  cat /root/notes.txt
  106  vim /root/notes.txt
  107  cat /root/deploy.sh
  108  bash /root/deploy.sh
  109  git -C /var/www/html status
  110  git -C /var/www/html pull origin main
  111  git -C /var/www/html log --oneline -10
  112  ls /var/log/nginx/
  113  tail -100 /var/log/nginx/error.log
  114  grep "404" /var/log/nginx/access.log | wc -l
  115  grep "500" /var/log/nginx/access.log | tail -5
  116  cat /etc/nginx/nginx.conf | grep worker
  117  nginx -T | grep -i timeout
  118  systemctl status nginx mysql fail2ban
  119  reboot
  120  exit
""".strip()

# ---------------------------------------------------------------------------
# Respuestas base
# ---------------------------------------------------------------------------

# Se completan dinámicamente con el hostname real desde cfg
FAKE_RESPONSES_TEMPLATE = {
    "whoami": "root",
    "id": "uid=0(root) gid=0(root) groups=0(root)",
    "uname": "Linux {hostname} 5.15.0-91-generic #101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux",
    "uname -a": "Linux {hostname} 5.15.0-91-generic #101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux",
    "pwd": "/root",
    "uptime": " 14:33:48 up 47 days,  3:12,  1 user,  load average: 0.08, 0.03, 0.01",
    "w": (
        " 14:33:48 up 47 days,  3:12,  1 user,  load average: 0.08, 0.03, 0.01\n"
        "USER     TTY      FROM             LOGIN@   IDLE JCPU   PCPU WHAT\n"
        "root     pts/0    10.0.0.100       14:30    0.00s  0.01s  0.00s -bash"
    ),
    "who": "root     pts/0        2026-04-14 09:21 (10.0.0.100)",
    "last -n 20": textwrap.dedent("""\
        root     pts/0        10.0.0.100       Mon Apr 14 09:21   still logged in
        root     pts/0        10.0.0.100       Sun Apr 13 22:15 - 23:01  (00:46)
        root     pts/0        185.220.101.42   Sun Apr 13 18:33 - 18:34  (00:00)
        deploy   pts/1        10.1.1.34        Sat Apr 12 11:00 - 12:30  (01:30)
        root     pts/0        10.0.0.100       Sat Apr 12 09:00 - 10:15  (01:15)
        reboot   system boot  5.15.0-91-generic Fri Apr 11 09:21
        wtmp begins Fri Apr 11 09:21:00 2026"""),
    "ifconfig": textwrap.dedent("""\
        eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
                inet 192.168.1.111  netmask 255.255.255.224  broadcast 192.168.1.127
                inet6 fe80::216:3eff:fe12:ab34  prefixlen 64  scopeid 0x20<link>
                ether 02:16:3e:12:ab:34  txqueuelen 1000  (Ethernet)
                RX packets 184392  bytes 24859210 (23.7 MiB)
                TX packets 98123   bytes 13021847 (12.4 MiB)

        lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536
                inet 127.0.0.1  netmask 255.0.0.0
                loop  txqueuelen 1000  (Local Loopback)"""),
    "ip a": textwrap.dedent("""\
        1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN
            link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
            inet 127.0.0.1/8 scope host lo
        2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP
            link/ether 02:16:3e:12:ab:34 brd ff:ff:ff:ff:ff:ff
            inet 192.168.1.111/27 brd 192.168.1.127 scope global eth0"""),
    "ip route": textwrap.dedent("""\
        default via 192.168.1.1 dev eth0 proto dhcp src 192.168.1.111 metric 100
        192.168.1.96/27 dev eth0 proto kernel scope link src 192.168.1.111"""),
    "cat /etc/passwd": textwrap.dedent("""\
        root:x:0:0:root:/root:/bin/bash
        daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
        bin:x:2:2:bin:/bin:/usr/sbin/nologin
        www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
        mysql:x:112:118:MySQL Server,,,:/nonexistent:/bin/false
        deploy:x:1001:1001::/home/deploy:/bin/bash
        ubuntu:x:1000:1000:Ubuntu:/home/ubuntu:/bin/bash"""),
    "cat /etc/shadow": "cat: /etc/shadow: Permission denied",
    "cat /etc/hostname": "{hostname}",
    "cat /etc/hosts": textwrap.dedent("""\
        127.0.0.1   localhost
        127.0.1.1   {hostname}
        192.168.1.111  {hostname} honeypot.soc.local
        192.168.1.112  dashboard dashboard.soc.local"""),
    "cat /etc/resolv.conf": textwrap.dedent("""\
        nameserver 192.168.1.1
        nameserver 8.8.8.8
        search soc.local"""),
    "history": FAKE_HISTORY,
    "env": textwrap.dedent("""\
        SHELL=/bin/bash
        TERM=xterm-256color
        USER=root
        PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        HOME=/root
        LOGNAME=root
        DB_PASSWORD=Sup3rS3cr3t!
        DB_HOST=10.1.1.98
        DB_USER=dbadmin
        MYSQL_PWD=Sup3rS3cr3t!"""),
    "cat /proc/version": "Linux version 5.15.0-91-generic (buildd@lcy02-amd64-059) (gcc (Ubuntu 11.4.0-1ubuntu1~22.04) 11.4.0, GNU ld (GNU Binutils for Ubuntu) 2.38) #101-Ubuntu SMP Tue Nov 14 13:30:08 UTC 2023",
    "ps aux": textwrap.dedent("""\
        USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
        root           1  0.0  0.1 168604 11240 ?        Ss   09:21   0:03 /sbin/init
        root         345  0.0  0.0  72304  6140 ?        Ss   09:21   0:00 /usr/sbin/sshd -D
        root         892  0.0  0.1 238916 14520 ?        Ssl  09:21   0:01 /usr/sbin/rsyslogd -n
        mysql        934  0.0  1.2 1842180 102400 ?      Sl   09:21   0:08 /usr/sbin/mysqld
        www-data    1123  0.0  0.3 204860 28200 ?        S    09:21   0:01 /usr/sbin/nginx: worker
        root        1120  0.0  0.1 204860 12100 ?        Ss   09:21   0:00 /usr/sbin/nginx: master
        root        4521  0.0  0.0  18388  5040 pts/0    Ss   14:30   0:00 -bash"""),
    "netstat -tlnp": textwrap.dedent("""\
        Active Internet connections (only servers)
        Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name
        tcp        0      0 0.0.0.0:22              0.0.0.0:*               LISTEN      345/sshd
        tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN      1120/nginx
        tcp        0      0 0.0.0.0:443             0.0.0.0:*               LISTEN      1120/nginx
        tcp        0      0 0.0.0.0:3306            0.0.0.0:*               LISTEN      934/mysqld
        tcp        0      0 127.0.0.1:6379          0.0.0.0:*               LISTEN      1456/redis-server"""),
    "ss -tlnp": textwrap.dedent("""\
        State    Recv-Q  Send-Q  Local Address:Port  Peer Address:Port  Process
        LISTEN   0       128     0.0.0.0:22          0.0.0.0:*          users:(("sshd",pid=345,fd=3))
        LISTEN   0       511     0.0.0.0:80          0.0.0.0:*          users:(("nginx",pid=1120,fd=6))
        LISTEN   0       511     0.0.0.0:443         0.0.0.0:*          users:(("nginx",pid=1120,fd=7))
        LISTEN   0       70      127.0.0.1:3306      0.0.0.0:*          users:(("mysqld",pid=934,fd=21))"""),
    "df -h": textwrap.dedent("""\
        Filesystem      Size  Used Avail Use% Mounted on
        /dev/sda1        40G   12G   26G  32% /
        tmpfs           985M     0  985M   0% /dev/shm
        /dev/sda2       100G   38G   57G  40% /var/lib/mysql"""),
    "free -m": textwrap.dedent("""\
                       total        used        free      shared  buff/cache   available
        Mem:            1969         832         234          18         902         962
        Swap:           2047         128        1919"""),
    "lscpu": textwrap.dedent("""\
        Architecture:                    x86_64
        CPU op-mode(s):                  32-bit, 64-bit
        CPU(s):                          2
        Model name:                      Intel(R) Xeon(R) CPU E5-2676 v3 @ 2.40GHz
        CPU MHz:                         2400.000"""),
    "date": "Thu Apr 23 14:33:48 CEST 2026",
    "timedatectl": textwrap.dedent("""\
               Local time: Thu 2026-04-23 14:33:48 CEST
           Universal time: Thu 2026-04-23 12:33:48 UTC
                 RTC time: Thu 2026-04-23 12:33:48
                Time zone: Europe/Madrid (CEST, +0200)
        NTP synchronized: yes"""),
    "cat /root/notes.txt": textwrap.dedent("""\
        TODO:
        - rotate DB credentials (see env vars) ← URGENTE
        - check backup script (cron falla los domingos)
        - update SSL cert before 2026-06-01
        - revisar accesos sospechosos en auth.log (IPs asiáticas)
        creds backup server: admin / B@ckup2026!
        mysql root: root / Sup3rS3cr3t!"""),
    "cat /root/backup.sh": textwrap.dedent("""\
        #!/bin/bash
        # Daily backup script
        DB_USER=dbadmin
        DB_PASS=Sup3rS3cr3t!
        DEST=/var/backups
        DATE=$(date +%Y%m%d)
        mysqldump -u$DB_USER -p$DB_PASS production > $DEST/prod_$DATE.sql
        tar -czf $DEST/www_$DATE.tar.gz /var/www/html
        echo "Backup done: $DATE" >> /var/log/backup.log"""),
    "cat /root/deploy.sh": textwrap.dedent("""\
        #!/bin/bash
        set -e
        echo "[deploy] pulling latest..."
        git -C /var/www/html pull origin main
        systemctl reload nginx
        echo "[deploy] done" """),
    "cat /root/.ssh/authorized_keys": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDECOY_KEY_HONEYPOT root@workstation",
    "cat /var/log/auth.log": textwrap.dedent("""\
        Apr 23 14:30:01 {hostname} sshd[4521]: Accepted password for root from 10.0.0.100 port 52341 ssh2
        Apr 23 12:11:33 {hostname} sshd[3891]: Failed password for root from 185.220.101.42 port 44201 ssh2
        Apr 23 12:11:35 {hostname} sshd[3891]: Failed password for admin from 185.220.101.42 port 44201 ssh2
        Apr 23 12:11:37 {hostname} sshd[3891]: Failed password for ubuntu from 185.220.101.42 port 44201 ssh2
        Apr 23 09:00:12 {hostname} sudo: deploy : TTY=pts/1 ; PWD=/var/www/html ; USER=root ; COMMAND=/usr/bin/systemctl reload nginx"""),
    "crontab -l": textwrap.dedent("""\
        # m h  dom mon dow   command
        0 2 * * * /root/backup.sh >> /var/log/backup.log 2>&1
        */5 * * * * /usr/lib/update-notifier/apt-check --print-upgrades 2>/dev/null
        0 4 * * 0 certbot renew --quiet"""),
    "cat /etc/crontab": textwrap.dedent("""\
        SHELL=/bin/sh
        PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
        17 *    * * *   root    cd / && run-parts --report /etc/cron.hourly
        25 6    * * *   root    test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
        47 6    * * 7   root    test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )"""),
    "ufw status": textwrap.dedent("""\
        Status: active
        To                         Action      From
        --                         ------      ----
        22/tcp                     ALLOW       Anywhere
        80/tcp                     ALLOW       Anywhere
        443/tcp                    ALLOW       Anywhere"""),
    "cat /var/www/html/wp-config.php": textwrap.dedent("""\
        <?php
        define('DB_NAME', 'wordpress_prod');
        define('DB_USER', 'wp_user');
        define('DB_PASSWORD', 'WP_DB_P@ss2024!');
        define('DB_HOST', '10.1.1.98');
        define('AUTH_KEY', 'decoy-key-honeypot-alpha');
        $table_prefix = 'wp_';"""),
}

# Comandos que simplemente devuelven vacío o mensaje mínimo
_EMPTY_CMDS = {"clear", "reset", "stty"}

# ---------------------------------------------------------------------------
# Tab completion
# ---------------------------------------------------------------------------

_TAB_FILES = {
    "/root":        [".bash_history", ".bashrc", ".profile", ".ssh", "backup.sh", "notes.txt", "deploy.sh"],
    "/root/.ssh":   ["authorized_keys", "id_rsa", "id_rsa.pub", "known_hosts"],
    "/etc":         ["passwd", "shadow", "hostname", "hosts", "fstab", "crontab", "nginx", "mysql", "ssh"],
    "/var/log":     ["auth.log", "syslog", "kern.log", "dpkg.log", "nginx", "fail2ban.log"],
    "/tmp":         ["sess_abc123"],
    "/var/www/html":["index.html", "wp-config.php", ".htaccess"],
    "/home/deploy": [".bashrc", ".ssh"],
}

_COMMANDS = [
    "cat", "ls", "cd", "pwd", "whoami", "id", "hostname", "uname",
    "ifconfig", "ip", "ps", "netstat", "ss", "env", "history", "w",
    "uptime", "exit", "logout", "wget", "curl", "df", "free", "last",
    "who", "date", "ufw", "find", "tar", "grep", "crontab", "top",
    "timedatectl", "lscpu", "dmesg", "journalctl", "systemctl",
]


def _tab_complete(current: str) -> Optional[str]:
    parts = current.split(" ", 1)
    cmd = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if not arg and " " not in current:
        matches = [c for c in _COMMANDS if c.startswith(current)]
        return (matches[0] + " ") if len(matches) == 1 else None

    if "/" in arg:
        slash = arg.rfind("/")
        dirpath = arg[:slash] or "/"
        prefix = arg[slash + 1:]
    else:
        dirpath = "/root"
        prefix = arg

    files = _TAB_FILES.get(dirpath, [])
    matches = [f for f in files if f.startswith(prefix)]
    if len(matches) == 1:
        completed_arg = (dirpath.rstrip("/") + "/" + matches[0]) if "/" in arg else matches[0]
        return cmd + " " + completed_arg
    return None


# ---------------------------------------------------------------------------
# Motor de comandos
# ---------------------------------------------------------------------------

def _resolve_responses(hostname: str) -> dict:
    """Aplica el hostname real a las respuestas que lo usan."""
    resolved = {}
    for k, v in FAKE_RESPONSES_TEMPLATE.items():
        key = k.replace("{hostname}", hostname)
        val = v.replace("{hostname}", hostname) if isinstance(v, str) else v
        resolved[key] = val
    return resolved


def _fake_ls(path: str = "/root", flags: str = "") -> str:
    files = FAKE_FS.get(path, FAKE_FS.get("/", []))
    if "-l" in flags or "-la" in flags or "-al" in flags:
        lines = []
        for f in files:
            hidden = f.startswith(".")
            mode = "drwxr-xr-x" if f in FAKE_FS else "-rw-r--r--"
            if f in ("backup.sh", "deploy.sh"):
                mode = "-rwxr-xr-x"
            if hidden:
                mode = "-rw-------"
            lines.append(f"{mode}  1 root root  4096 Apr 14 09:21 {f}")
        return "total " + str(len(files) * 4) + "\n" + "\n".join(lines)
    return "  ".join(files)


def _handle_pipe(parts: list, responses: dict) -> str:
    """Ejecuta la parte izquierda y aplica filtros de la derecha."""
    left_out = _handle_single(parts[0].strip(), responses)
    for right in parts[1:]:
        right = right.strip()
        lines = left_out.splitlines()

        if right.startswith("grep "):
            pattern = right[5:].strip().strip('"').strip("'")
            # Soportar -v
            invert = False
            if pattern.startswith("-v "):
                invert = True
                pattern = pattern[3:].strip().strip('"').strip("'")
            matches = [l for l in lines if (pattern.lower() in l.lower()) != invert]
            left_out = "\n".join(matches)

        elif right.startswith("wc -l"):
            left_out = str(len([l for l in lines if l]))

        elif right.startswith("head"):
            n = 10
            parts2 = right.split()
            if len(parts2) > 1 and parts2[1].startswith("-"):
                try:
                    n = int(parts2[1][1:])
                except ValueError:
                    pass
            left_out = "\n".join(lines[:n])

        elif right.startswith("tail"):
            n = 10
            parts2 = right.split()
            if len(parts2) > 1 and parts2[1].startswith("-"):
                try:
                    n = int(parts2[1][1:])
                except ValueError:
                    pass
            left_out = "\n".join(lines[-n:])

        elif right.startswith("sort"):
            left_out = "\n".join(sorted(lines))

        elif right.startswith("uniq"):
            seen, out = set(), []
            for l in lines:
                if l not in seen:
                    seen.add(l)
                    out.append(l)
            left_out = "\n".join(out)

        elif right.startswith("awk"):
            # Soportar awk '{print $N}' básico
            import re
            m = re.search(r"print \$(\d+)", right)
            if m:
                idx = int(m.group(1)) - 1
                out = []
                for l in lines:
                    parts3 = l.split()
                    out.append(parts3[idx] if idx < len(parts3) else "")
                left_out = "\n".join(out)

        elif right.startswith("cut"):
            # cut -d: -f1  etc
            import re
            delim = ":"
            field = 1
            dm = re.search(r"-d(\S+)", right)
            fm = re.search(r"-f(\d+)", right)
            if dm:
                delim = dm.group(1).strip("'\"")
            if fm:
                field = int(fm.group(1))
            out = []
            for l in lines:
                parts3 = l.split(delim)
                out.append(parts3[field - 1] if field - 1 < len(parts3) else "")
            left_out = "\n".join(out)

        elif right == "cat":
            pass  # cat en pipe no hace nada extra

    return left_out


def _handle_single(cmd: str, responses: dict) -> str:
    """Procesa un comando simple (sin pipes)."""
    cmd = cmd.strip()
    if not cmd:
        return ""

    if cmd in _EMPTY_CMDS:
        return ""

    # Redirecciones — ejecutar pero ignorar la redirección
    for op in (">", ">>", "2>", "&>"):
        if op in cmd:
            cmd = cmd.split(op)[0].strip()

    # ls
    if cmd.startswith("ls"):
        parts = cmd.split()
        flags = ""
        path = "/root"
        for p in parts[1:]:
            if p.startswith("-"):
                flags = p
            else:
                path = p
        return _fake_ls(path, flags)

    # cd — no output
    if cmd.startswith("cd"):
        return ""

    # hostname
    if cmd == "hostname":
        return responses.get("cat /etc/hostname", "ubuntu-server")

    # Coincidencia exacta
    if cmd in responses:
        return responses[cmd]

    # cat <fichero>
    if cmd.startswith("cat "):
        target = cmd.strip()
        if target in responses:
            return responses[target]
        # buscar por nombre de fichero
        for key, val in responses.items():
            if key.startswith("cat ") and key.split("/")[-1] == target.split("/")[-1]:
                return val
        fname = cmd[4:].strip()
        return f"cat: {fname}: No such file or directory"

    # tail -f (simular espera breve)
    if cmd.startswith("tail -f"):
        return "(tail: archivo vacío o sin nuevas entradas)"

    # find
    if cmd.startswith("find"):
        if "/tmp" in cmd:
            return "/tmp/sess_abc123\n/tmp/tmpfile_deploy"
        if "*.php" in cmd:
            return "/var/www/html/wp-config.php\n/var/www/html/index.php"
        if "-perm -4000" in cmd or "suid" in cmd.lower():
            return "/usr/bin/sudo\n/usr/bin/passwd\n/usr/bin/su"
        return ""

    # wget / curl — simular éxito o error
    if cmd.startswith("wget") or cmd.startswith("curl"):
        if "192.168.1.112" in cmd or "localhost" in cmd or "127.0.0.1" in cmd:
            return "HTTP/1.1 200 OK"
        return "curl: (6) Could not resolve host"

    # grep directo (sin pipe)
    if cmd.startswith("grep"):
        return ""

    # systemctl status
    if cmd.startswith("systemctl status"):
        svc = cmd.split()[-1]
        return (
            f"● {svc}.service - {svc.capitalize()} Service\n"
            f"     Loaded: loaded (/etc/systemd/system/{svc}.service; enabled)\n"
            f"     Active: active (running) since Thu 2026-04-23 09:21:00 CEST; 5h 12min ago\n"
            f"   Main PID: 1234 ({svc})"
        )

    # exit / logout
    if cmd in ("exit", "logout", "quit"):
        return "__EXIT__"

    # Comando no reconocido
    base_cmd = cmd.split()[0]
    return f"-bash: {base_cmd}: command not found"


def _handle_command(cmd: str, responses: dict) -> str:
    """Entrada principal: soporta pipes, &&, ; y encadenamiento."""
    cmd = cmd.strip()
    if not cmd:
        return ""

    # Pipes
    if "|" in cmd:
        parts = cmd.split("|")
        return _handle_pipe(parts, responses)

    # Encadenamiento con && o ;
    for sep in ("&&", ";"):
        if sep in cmd:
            parts = cmd.split(sep)
            outputs = []
            for part in parts:
                out = _handle_single(part.strip(), responses)
                if out == "__EXIT__":
                    return "__EXIT__"
                if out:
                    outputs.append(out)
            return "\n".join(outputs)

    return _handle_single(cmd, responses)


# ---------------------------------------------------------------------------
# Delays realistas por tipo de comando
# ---------------------------------------------------------------------------

_DELAY_MAP = {
    "apt": (1.5, 3.0),
    "mysql": (0.3, 0.8),
    "mysqldump": (0.8, 1.5),
    "find": (0.2, 0.6),
    "nmap": (2.0, 4.0),
    "ping": (0.5, 1.0),
    "wget": (0.3, 0.8),
    "curl": (0.2, 0.5),
    "systemctl": (0.1, 0.3),
    "journalctl": (0.1, 0.4),
    "tar": (0.3, 0.7),
    "grep": (0.05, 0.15),
}
_DEFAULT_DELAY = (0.02, 0.08)


def _get_delay(cmd: str) -> float:
    base_cmd = cmd.strip().split()[0] if cmd.strip() else ""
    lo, hi = _DELAY_MAP.get(base_cmd, _DEFAULT_DELAY)
    return random.uniform(lo, hi)


# ---------------------------------------------------------------------------
# Servidor SSH paramiko
# ---------------------------------------------------------------------------

class FakeSSHServer(paramiko.ServerInterface):
    def __init__(self, valid_credentials: list, detector: BruteForceDetector,
                 src_ip: str, cfg: dict):
        self._creds = {(c["username"], c["password"]) for c in valid_credentials}
        self._detector = detector
        self._src_ip = src_ip
        self._base = {
            "hostname": cfg["honeypot"]["hostname"],
            "environment": cfg["honeypot"]["environment"],
            "vlan": cfg["honeypot"]["vlan"],
            "host": cfg["honeypot"]["hostname"],
        }
        self.event = threading.Event()

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username: str, password: str):
        logger = get_logger()
        if (username, password) in self._creds:
            logger.info(
                "login_success",
                extra={**self._base, "service": "ssh", "action": "login_attempt",
                       "src_ip": self._src_ip, "username": username,
                       "password": password, "result": "success"},
            )
            return paramiko.AUTH_SUCCESSFUL
        logger.warning(
            "login_failed",
            extra={**self._base, "service": "ssh", "action": "login_attempt",
                   "src_ip": self._src_ip, "username": username,
                   "password": password, "result": "failed"},
        )
        self._detector.record("ssh", self._src_ip, username)
        return paramiko.AUTH_FAILED

    def check_auth_publickey(self, username, key):
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_pty_request(self, channel, term, width, height,
                                  pixelwidth, pixelheight, modes):
        return True

    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

    def check_channel_exec_request(self, channel, command):
        self.event.set()
        return True


def _run_fake_shell(channel, src_ip: str, cfg: dict):
    logger = get_logger()
    hostname = cfg["honeypot"]["hostname"]
    responses = _resolve_responses(hostname)

    base = {
        "hostname": hostname,
        "environment": cfg["honeypot"]["environment"],
        "vlan": cfg["honeypot"]["vlan"],
        "host": hostname,
        "service": "ssh",
        "src_ip": src_ip,
    }

    # MOTD realista con hostname correcto
    channel.send(
        f"Welcome to Ubuntu 22.04.3 LTS (GNU/Linux 5.15.0-91-generic x86_64)\r\n\r\n"
        f" * Documentation:  https://help.ubuntu.com\r\n"
        f" * Management:     https://landscape.canonical.com\r\n\r\n"
        f"Last login: Mon Apr 14 09:21:33 2026 from 10.0.0.100\r\n"
        .encode()
    )

    prompt = f"root@{hostname}:~# ".encode()

    while True:
        channel.send(prompt)
        line = b""
        try:
            while True:
                ch = channel.recv(1)
                if not ch:
                    return

                if ch in (b"\r", b"\n"):
                    channel.send(b"\r\n")
                    break

                if ch in (b"\x03", b"\x04"):
                    channel.send(b"^C\r\n")
                    line = b""
                    break

                if ch in (b"\x7f", b"\x08"):
                    if line:
                        line = line[:-1]
                        channel.send(b"\x08 \x08")
                    continue

                if ch == b"\x09":
                    current = line.decode(errors="replace")
                    completed = _tab_complete(current)
                    if completed is not None:
                        channel.send(b"\r" + prompt + completed.encode() + b" ")
                        line = completed.encode()
                    continue

                if ch == b"\x1b":
                    try:
                        ch2 = channel.recv(1)
                        if ch2 == b"[":
                            channel.recv(1)
                    except Exception:
                        pass
                    continue

                channel.send(ch)
                line += ch

        except Exception:
            return

        cmd = line.decode(errors="replace").strip()
        if not cmd:
            continue

        logger.info(
            "command",
            extra={**base, "action": "command", "command": cmd},
        )

        # Delay artificial antes de responder
        delay = _get_delay(cmd)
        time.sleep(delay)

        response = _handle_command(cmd, responses)
        if response == "__EXIT__":
            channel.send(b"\r\nlogout\r\n")
            channel.close()
            return
        if response:
            normalized = response.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
            channel.send(("\r\n" + normalized + "\r\n").encode())
        else:
            channel.send(b"\r\n")


def _handle_client(client_sock: socket.socket, addr: tuple, cfg: dict,
                   detector: BruteForceDetector, host_key):
    logger = get_logger()
    src_ip, src_port = addr[0], addr[1]
    base = {
        "hostname": cfg["honeypot"]["hostname"],
        "environment": cfg["honeypot"]["environment"],
        "vlan": cfg["honeypot"]["vlan"],
        "host": cfg["honeypot"]["hostname"],
        "service": "ssh",
        "src_ip": src_ip,
        "src_port": src_port,
    }

    logger.info("connection", extra={**base, "action": "connection"})

    transport: Optional[paramiko.Transport] = None
    try:
        transport = paramiko.Transport(client_sock)
        transport.add_server_key(host_key)
        transport.local_version = cfg["services"]["ssh"]["banner"]

        server = FakeSSHServer(
            cfg["services"]["ssh"]["credentials"],
            detector, src_ip, cfg,
        )
        transport.start_server(server=server)

        channel = transport.accept(30)
        if channel is None:
            return

        server.event.wait(10)
        _run_fake_shell(channel, src_ip, cfg)

    except Exception as exc:
        logger.debug(
            "ssh_error",
            extra={**base, "action": "connection", "error": str(exc)},
        )
    finally:
        if transport:
            try:
                transport.close()
            except Exception:
                pass
        try:
            client_sock.close()
        except Exception:
            pass


async def start_ssh(cfg: dict, detector: BruteForceDetector):
    port = cfg["services"]["ssh"]["port"]
    logger = get_logger()

    import os as _os
    key_path = "/opt/honeypot/ssl/ssh_host_rsa_key"
    _os.makedirs(_os.path.dirname(key_path), exist_ok=True)
    if _os.path.exists(key_path):
        host_key = paramiko.RSAKey.from_private_key_file(key_path)
    else:
        host_key = paramiko.RSAKey.generate(2048)
        host_key.write_private_key_file(key_path)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    server_sock.bind(("0.0.0.0", port))
    server_sock.listen(100)
    server_sock.setblocking(False)

    logger.info(
        "service_started",
        extra={
            "hostname": cfg["honeypot"]["hostname"],
            "environment": cfg["honeypot"]["environment"],
            "vlan": cfg["honeypot"]["vlan"],
            "host": cfg["honeypot"]["hostname"],
            "service": "ssh",
            "action": "connection",
            "port": port,
        },
    )

    loop = asyncio.get_event_loop()
    while True:
        try:
            client_sock, addr = await loop.sock_accept(server_sock)
            t = threading.Thread(
                target=_handle_client,
                args=(client_sock, addr, cfg, detector, host_key),
                daemon=True,
            )
            t.start()
        except Exception as exc:
            logger.error("ssh_accept_error", extra={"error": str(exc)})
            await asyncio.sleep(1)
