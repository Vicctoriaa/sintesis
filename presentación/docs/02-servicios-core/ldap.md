# LDAP — CT100

> Servicio de directorio centralizado basado en OpenLDAP (`slapd`). Gestiona usuarios y grupos del entorno SOC, sirviendo como backend de autenticación unificado.

---

## Datos del contenedor

| Campo | Valor |
|-------|-------|
| CT ID | 100 |
| Hostname | `ldap` |
| OS | Debian 12 Bookworm |
| Memoria | 256 MB |
| Disco | 10 GB |
| Cores | 1 |
| Bridge | `vmbr1` — VLAN 40 Producción |
| IP | `10.1.1.98/27` |
| Gateway | `10.1.1.97` |

---

## Instalación

```bash
apt update && apt install slapd ldap-utils -y
```

### Configuración inicial

```bash
dpkg-reconfigure slapd
```

| Pregunta | Respuesta |
|----------|-----------|
| Omit OpenLDAP server configuration? | NO |
| DNS domain name | `soc.local` |
| Organization name | SOC honeycos |
| Administrator password | — |
| Database backend | MDB |
| Remove database when slapd is purged? | NO |
| Move old database? | YES |
| Allow LDAPv2? | NO |

> **DNS domain name** define el DN raíz del directorio: `soc.local` → `dc=soc,dc=local`. **MDB** es el backend moderno recomendado. **LDAPv2** se deshabilita por seguridad — es obsoleto y no cifra credenciales.

### Verificar instalación

```bash
sudo slapcat
# Debe mostrar la base DN: dc=soc,dc=local
```

---

## Estructura del directorio

### Crear OUs base

```ldif
dn: ou=usuarios,dc=soc,dc=local
objectClass: organizationalUnit
ou: usuarios

dn: ou=grupos,dc=soc,dc=local
objectClass: organizationalUnit
ou: grupos
```

```bash
sudo ldapadd -x -D "cn=admin,dc=soc,dc=local" -W -f estructura.ldif
```

---

## Gestión de usuarios

### Generar hash de contraseña

```bash
slappasswd -s mi_contraseña
```

### Crear usuario

```ldif
dn: uid=jperez,ou=usuarios,dc=soc,dc=local
objectClass: inetOrgPerson
objectClass: posixAccount
objectClass: shadowAccount
uid: jperez
cn: Jose
sn: Perez
uidNumber: 10001
gidNumber: 10001
homeDirectory: /home/jperez
loginShell: /bin/bash
userPassword: {SSHA}HASH_AQUI
```

```bash
sudo ldapadd -x -D "cn=admin,dc=soc,dc=local" -W -f usuario.ldif
```

> `uidNumber` / `gidNumber` deben ser únicos. `userPassword` acepta el hash generado con `slappasswd`.

### Script para generar hashes en lote

```bash
#!/bin/bash
for user in "jperez:Jose Perez" "nlopez:Nerea Lopez" "aconde:Alfredo Conde"; do
    uid="${user%%:*}"
    name="${user##*:}"
    echo ""
    echo "$name ($uid)"
    read -s -p " Contraseña: " pass
    echo ""
    echo " Hash: $(slappasswd -s "$pass")"
done
echo ""
echo "Copia cada hash en su userPassword dentro del LDIF correspondiente"
```

---

## Consultas

```bash
# Ver todo el árbol
ldapsearch -x -b "dc=soc,dc=local" -D "cn=admin,dc=soc,dc=local" -W

# Buscar un usuario concreto
ldapsearch -x -b "ou=usuarios,dc=soc,dc=local" "(uid=jperez)" -D "cn=admin,dc=soc,dc=local" -W
```

---

## LDAPS — TLS

```bash
sudo apt install ssl-cert
sudo adduser openldap ssl-cert
sudo systemctl restart slapd
```

> `adduser openldap ssl-cert` permite que el proceso `slapd` lea los certificados del sistema. Habilitar TLS es recomendado para cifrar credenciales en tránsito (puerto 636).

---

## Monitorización

| Servicio | Puerto | Estado |
|---------|--------|--------|
| node_exporter | `9100` | active |

Target en Prometheus CT101:
```yaml
- '10.1.1.98:9100'    # CT100 LDAP
```
