# Configuración de LDAP en contenedor

LDAP (Lightweight Directory Access Protocol) es un protocolo estándar para gestionar directorios de usuarios y grupos de forma centralizada. En este documento se configura OpenLDAP (`slapd`) dentro de un contenedor para servir como directorio de autenticación.

---

## 1. Instalar LDAP

Instala el servidor OpenLDAP (`slapd`) y las utilidades de cliente (`ldap-utils`) que permiten interactuar con el directorio desde la línea de comandos.

Dentro del contenedor:

```bash
apt update
apt install slapd ldap-utils -y
```

---

## 2. Configuración inicial (IMPORTANTE)

El asistente de instalación por defecto no solicita todos los parámetros necesarios. Con `dpkg-reconfigure` se lanza el asistente completo para definir correctamente el dominio, la organización y la contraseña de administrador.

```bash
dpkg-reconfigure slapd
```

### Respuestas

| Pregunta | Respuesta |
|----------|-----------|
| Omit OpenLDAP server configuration? | ❌ NO |
| DNS domain name | `midominio.local` |
| Organization name | Lo que quieras (ej: `MiEmpresa`) |
| Administrator password | Pon una y apúntala |
| Database backend | `MDB` |
| Remove database when slapd is purged? | NO |
| Move old database? | YES |
| Allow LDAPv2? | NO |

- **DNS domain name:** Define el DN raíz del directorio (ej: `midominio.local` → `dc=midominio,dc=local`).
- **MDB:** Backend de base de datos moderno y recomendado, sustituto de BDB/HDB.
- **Allow LDAPv2:** Se deshabilita por seguridad; LDAPv2 es obsoleto y no cifra credenciales.

---

## 3. Verificar que funciona

`slapcat` vuelca el contenido completo de la base de datos LDAP en formato LDIF directamente desde disco, sin pasar por el servidor. Útil para verificar que la estructura base se ha creado correctamente tras la configuración.

```bash
sudo slapcat
```

Deberías ver tu base DN: `dc=soc,dc=local`

---

## 4. Crear la estructura base (OUs)

Las Organizational Units (OUs) son contenedores lógicos dentro del directorio que agrupan entradas del mismo tipo. Es buena práctica separar `usuarios` y `grupos` desde el inicio para facilitar la gestión y las búsquedas.

Crea un fichero `estructura.ldif`:

```ldif
dn: ou=usuarios,dc=soc,dc=local
objectClass: organizationalUnit
ou: usuarios

dn: ou=grupos,dc=soc,dc=local
objectClass: organizationalUnit
ou: grupos
```

Aplícalo con `ldapadd`, autenticándote como administrador (`-D`) e indicando el fichero a importar (`-f`). El flag `-W` solicita la contraseña de forma interactiva:

```bash
sudo ldapadd -x -D "cn=admin,dc=soc,dc=local" -W -f estructura.ldif
```

---

## 5. Generar hash de contraseña

Las contraseñas en LDAP nunca se almacenan en texto plano. `slappasswd` genera un hash SSHA (Salted SHA-1) listo para incluir en el campo `userPassword` de un fichero LDIF.

```bash
slappasswd -s mi_contraseña_secreta
```

### Script para generar hashes en lote

Cuando se crean varios usuarios a la vez, este script solicita la contraseña de cada uno de forma interactiva y devuelve el hash correspondiente, evitando tener que ejecutar `slappasswd` manualmente para cada usuario.

```bash
#!/bin/bash
# ─────────────────────────────────────────
# genera_hashes_admin.sh
# ─────────────────────────────────────────

echo "=== Generando hashes para grupo ADMIN ==="

echo ""
echo "Juan Gonzalez (jgonzalez)"
read -s -p " Contraseña: " pass
echo ""
hash=$(slappasswd -s "$pass")
echo " Hash: $hash"

echo ""
echo "Victoria Conde (vconde)"
read -s -p " Contraseña: " pass
echo ""
hash=$(slappasswd -s "$pass")
echo " Hash: $hash"

echo ""
echo "Victor Martinez (vmartinez)"
read -s -p " Contraseña: " pass
echo ""
hash=$(slappasswd -s "$pass")
echo " Hash: $hash"

echo ""
echo "✅ Copia cada hash en su userPassword dentro de usuarios_admin.ldif"
```

---

## 6. Crear un usuario

Cada usuario en OpenLDAP se define mediante una entrada LDIF con sus `objectClass` y atributos. La combinación de `inetOrgPerson`, `posixAccount` y `shadowAccount` permite usar el usuario tanto para autenticación LDAP como para login en sistemas Unix.

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

- **uidNumber / gidNumber:** Identificadores numéricos de usuario y grupo para el sistema Unix. Deben ser únicos en el directorio.
- **userPassword:** Sustituye `HASH_AQUI` por el hash generado con `slappasswd` en el paso anterior.

Copia el hash resultante en `userPassword` y aplica:

```bash
sudo ldapadd -x -D "cn=admin,dc=soc,dc=local" -W -f usuario.ldif
```

---

## 🔍 7. Consultar el directorio

`ldapsearch` permite realizar búsquedas en el directorio autenticándose con el administrador. Es útil para verificar que los usuarios y grupos se han creado correctamente.

Ver todo el árbol:

```bash
ldapsearch -x -b "dc=soc,dc=local" -D "cn=admin,dc=soc,dc=local" -W
```

Buscar un usuario concreto:

```bash
ldapsearch -x -b "ou=usuarios,dc=soc,dc=local" "(uid=jperez)" -D "cn=admin,dc=soc,dc=local" -W
```

- **`-b`:** Base de búsqueda (desde dónde busca en el árbol).
- **`(uid=jperez)`:** Filtro de búsqueda en formato LDAP; devuelve solo la entrada del usuario con ese UID.

---

## 8. Habilitar LDAPS (TLS) — recomendado

Por defecto, LDAP transmite los datos en texto plano, incluyendo las contraseñas. Habilitar TLS (LDAPS en el puerto 636) cifra toda la comunicación entre clientes y el servidor, siendo imprescindible en entornos de producción.

```bash
sudo apt install ssl-cert
sudo adduser openldap ssl-cert
sudo systemctl restart slapd
```

- **`ssl-cert`:** Paquete que incluye un certificado autofirmado listo para usar en servicios locales.
- **`adduser openldap ssl-cert`:** Añade el usuario del servicio `slapd` al grupo `ssl-cert` para que pueda leer los certificados del sistema.
