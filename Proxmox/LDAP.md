# Configuración de LDAP en contenedor

---

## 1. Instalar LDAP

Dentro del contenedor:
```bash
apt update
apt install slapd ldap-utils -y
```

---

## 2. Configuración inicial (IMPORTANTE)

Reconfigura para hacerlo bien:
```bash
dpkg-reconfigure slapd
```

**Respuestas:**

| Pregunta | Respuesta |
|---|---|
| Omit OpenLDAP server configuration? | ❌ NO |
| DNS domain name | `midominio.local` |
| Organization name | Lo que quieras (ej: `MiEmpresa`) |
| Administrator password | Pon una y apúntala |
| Database backend | `MDB` |
| Remove database when slapd is purged? | NO |
| Move old database? | YES |
| Allow LDAPv2? | NO |

---

## 3. Verificar que funciona
```bash
sudo slapcat
```

> Deberías ver tu base DN: `dc=soc,dc=local`

---

## 4. Crear la estructura base (OUs)

Crea un fichero `estructura.ldif`:
```ldif
dn: ou=usuarios,dc=soc,dc=local
objectClass: organizationalUnit
ou: usuarios

dn: ou=grupos,dc=soc,dc=local
objectClass: organizationalUnit
ou: grupos
```

Aplícalo:
```bash
sudo ldapadd -x -D "cn=admin,dc=soc,dc=local" -W -f estructura.ldif
```

---

## 5. Generar hash de contraseña
```bash
slappasswd -s mi_contraseña_secreta
```
#!/bin/bash

# ─────────────────────────────────────────
# genera_hashes_admin.sh
# ─────────────────────────────────────────

echo "=== Generando hashes para grupo ADMIN ==="

echo ""
echo "Juan Gonzalez (jgonzalez)"
read -s -p "   Contraseña: " pass
echo ""
hash=$(slappasswd -s "$pass")
echo "   Hash: $hash"

echo ""
echo "Victoria Conde (vconde)"
read -s -p "   Contraseña: " pass
echo ""
hash=$(slappasswd -s "$pass")
echo "   Hash: $hash"

echo ""
echo "Victor Martinez (vmartinez)"
read -s -p "   Contraseña: " pass
echo ""
hash=$(slappasswd -s "$pass")
echo "   Hash: $hash"

echo ""
echo "✅ Copia cada hash en su userPassword dentro de usuarios_admin.ldif"
---

## 6. Crear un usuario

Crea `usuario.ldif`:
```ldif
dn: uid=jperez,ou=usuarios,dc=soc,dc=local
objectClass: inetOrgPerson
objectClass: posixAccount
objectClass: shadowAccount
uid: {Nombre-usuario}
cn: {Nombre}
sn: {Apellido}
uidNumber: 10001
gidNumber: 10001
homeDirectory: /home/{Nombre-usuario}
loginShell: /bin/bash
userPassword: {SSHA}HASH_AQUI
```

Copia el hash resultante en `userPassword` y aplica:
```bash
sudo ldapadd -x -D "cn=admin,dc=soc,dc=local" -W -f usuario.ldif
```

---

## 🔍 7. Consultar el directorio

**Ver todo el árbol:**
```bash
ldapsearch -x -b "dc=soc,dc=local" -D "cn=admin,dc=soc,dc=local" -W
```

**Buscar un usuario concreto:**
```bash
ldapsearch -x -b "ou=usuarios,dc=soc,dc=local" "(uid=jperez)" -D "cn=admin,dc=soc,dc=local" -W
```

---

## 8. Habilitar LDAPS (TLS) — recomendado
```bash
sudo apt install ssl-cert
sudo adduser openldap ssl-cert
sudo systemctl restart slapd
```
