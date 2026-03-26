🧠 1. Instalar LDAP

Dentro del contenedor:
apt update
apt install slapd ldap-utils -y


⚙️ 2. Configuración inicial (IMPORTANTE)

Reconfigura para hacerlo bien:
dpkg-reconfigure slapd

Respuestas
Omit OpenLDAP server configuration? → ❌ NO
DNS domain name:
👉 midominio.local
Organization name:
👉 lo que quieras (ej: MiEmpresa)
Administrator password:
👉 pon una (apúntala)
Database backend:
👉 MDB
Remove database when slapd is purged? → NO
Move old database? → YES
Allow LDAPv2? → NO


3. Verificar que funciona
bashsudo slapcat
Deberías ver tu base DN: dc=soc,dc=local


4. Crear la estructura base (OUs)
Crea un fichero estructura.ldif:
ldifdn: ou=usuarios,dc=soc,dc=local
objectClass: organizationalUnit
ou: usuarios
dn: ou=grupos,dc=soc,dc=local
objectClass: organizationalUnit
ou: grupos


5. Aplícalo:
bashsudo ldapadd -x -D "cn=admin,dc=soc,dc=local" -W -f estructura.ldif


6. Para generar el hash de la contraseña:
bashslappasswd -s mi_contraseña_secreta


7. Crear un usuario
Crea usuario.ldif:
ldifdn: uid=jperez,ou=usuarios,dc=soc,dc=local
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


8. Copia el hash resultante en userPassword y aplica:
bashsudo ldapadd -x -D "cn=admin,dc=soc,dc=local" -W -f usuario.ldif


9. Consultar el directorio
bash# Ver todo el árbol
ldapsearch -x -b "dc=soc,dc=local" -D "cn=admin,dc=soc,dc=local" -W

# Buscar un usuario concreto
ldapsearch -x -b "ou=usuarios,dc=soc,dc=local" "(uid=jperez)" -D "cn=admin,dc=soc,dc=local" -W


10. Habilitar LDAPS (TLS) — recomendado
bashsudo apt install ssl-cert
sudo adduser openldap ssl-cert
sudo systemctl restart slapd
