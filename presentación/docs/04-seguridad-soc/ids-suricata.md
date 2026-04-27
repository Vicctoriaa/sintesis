# Suricata IDS — CT106

> Motor de detección de intrusiones del laboratorio. Suricata analiza el tráfico de red en tiempo real aplicando reglas para detectar amenazas, y escribe los eventos en formato JSON (`eve.json`). Ese fichero es consumido por el agente Wazuh (que lo envía al SIEM) y por `eve-watcher.py` (que dispara playbooks Ansible de respuesta automática).

---

## Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 106 |
| Hostname | `suricata-ids` |
| OS | Debian 12 |
| Memoria | 1024 MB |
| Disco | 8 GB |
| Cores | 2 |
| Privilegiado | Sí |
| Bridge | `vmbr1` — VLAN 20 Servicios |
| IP | `10.1.1.36/27` |
| Gateway | `10.1.1.33` |

> Contenedor privilegiado con 2 cores porque Suricata necesita inspeccionar cada paquete de red en tiempo real. El modo privilegiado es necesario para acceder directamente a las interfaces de red del host.

---

## Integración con Wazuh

```
Suricata genera logs en eve.json
       ↓
Wazuh Agent los lee y envía al manager
       ↓
Wazuh Manager los muestra en dashboard
```

---

## Automatización — eve-watcher.py

`eve-watcher.py` monitoriza `eve.json` en tiempo real y, cuando detecta alertas de severidad alta, conecta via SSH a CT103 para ejecutar playbooks Ansible de respuesta automática.

```
Suricata genera alerta en eve.json
       ↓
eve-watcher.py detecta el evento (tail -f)
       ↓
SSH a CT103 (10.1.1.34:2222)
       ↓
ansible-playbook block-ip.yml / isolate-host.yml
```

### Lógica de clasificación de alertas

| Condición | Acción |
|-----------|--------|
| sev=1, src IP externa | `block-ip.yml -e malicious_ip=<src_ip>` |
| sev=1, src IP interna | `isolate-host.yml -e target_vlan=<vlan_origen>` |
| sev=2, firma C2/malware, src externa | `block-ip.yml -e malicious_ip=<src_ip>` |
| sev=2, firma scan/nmap, src interna | `isolate-host.yml -e target_vlan=<vlan_origen>` |
| firma exploit/shellcode cualquier sev | `block-ip.yml -e malicious_ip=<src_ip>` |

> Cooldown de 5 minutos por IP para evitar ejecuciones repetidas ante floods de alertas.

### Mapeo VLAN por subred

| Subred | VLAN OpenWRT |
|--------|-------------|
| `10.1.1.0/27` | vlan10 (DMZ) |
| `10.1.1.32/27` | vlan20 (Servicios) |
| `10.1.1.64/27` | vlan30 (SOC) |
| `10.1.1.96/27` | vlan40 (Producción) |
| `10.1.1.128/27` | vlan50 (Honeypot) |

---

## Reglas locales

**Fichero:** `/etc/suricata/rules/local.rules`

Las IPs bloqueadas por el SOC se añaden automáticamente via `block-ip.yml`:

```
drop ip <ip_maliciosa> any -> $HOME_NET any (msg:"SOC Block - Malicious IP <ip>"; sid:9000001; rev:1;)
```

```bash
# Recargar reglas en caliente sin reiniciar Suricata
suricatasc -c reload-rules

# Ver reglas activas
cat /etc/suricata/rules/local.rules

# Validar configuración
suricata -T -c /etc/suricata/suricata.yaml
```
