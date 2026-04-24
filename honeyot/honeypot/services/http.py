"""
services/http.py — Servicios HTTP y HTTPS falsos (aiohttp)
Puertos 80 y 443 · Honeypot VM203

Mejoras v2:
  - Headers HTTP realistas en todas las respuestas (Server, X-Powered-By, etc.)
  - Captura enriquecida: User-Agent, Referer, body completo en POST, cookies
  - ~60 rutas de scanner adicionales que generan eventos WARNING con la ruta probada
  - Cookies de sesión falsas tras login (hace creer al atacante que está autenticado)
  - Simulación de panel admin con "acceso concedido" con credenciales señuelo
  - Nuevas rutas: /backup.zip, /.git/config, /actuator/env, /api/v1/users, /console, etc.
"""

import json
import ssl
import os
import asyncio
import hashlib
import time
from datetime import datetime

from aiohttp import web

from core.logger import get_logger
from core.alerts import BruteForceDetector

# ---------------------------------------------------------------------------
# Headers comunes realistas
# ---------------------------------------------------------------------------

COMMON_HEADERS = {
    "Server": "Apache/2.4.57 (Ubuntu)",
    "X-Powered-By": "PHP/8.1.12",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Cache-Control": "no-store, no-cache, must-revalidate",
}

NGINX_HEADERS = {
    "Server": "nginx/1.24.0 (Ubuntu)",
    "X-Powered-By": "PHP/8.1.12",
}

TOMCAT_HEADERS = {
    "Server": "Apache-Coyote/1.1",
    "X-Powered-By": "Servlet/4.0",
}

def _resp(text: str, *, content_type="text/html", status=200,
          headers: dict = None, cookies: dict = None) -> web.Response:
    h = {**COMMON_HEADERS, **(headers or {})}
    r = web.Response(text=text, content_type=content_type,
                     status=status, headers=h)
    if cookies:
        for k, v in cookies.items():
            r.set_cookie(k, v, httponly=True, samesite="Lax")
    return r

# ---------------------------------------------------------------------------
# Páginas HTML señuelo
# ---------------------------------------------------------------------------

PAGE_APACHE_DEFAULT = """<!DOCTYPE html>
<html>
<head><title>Apache2 Ubuntu Default Page: It works</title>
<style>body{font-family:DejaVu Sans,sans-serif;background:#fff}
h1{color:#777;margin:20px 0}div.main{padding:20px}</style>
</head>
<body>
<div class="main">
<h1>Apache2 Ubuntu Default Page</h1>
<p>This is the default welcome page used to test the correct operation
of the Apache2 server after installation on Ubuntu systems.</p>
<p><b>If you can read this page, it means that the Apache HTTP server installed
at this site is working properly.</b></p>
<p>Server: Apache/2.4.57 (Ubuntu)<br>
IP: 192.168.1.111</p>
</div>
</body></html>"""

PAGE_ADMIN = """<!DOCTYPE html>
<html><head><title>Administration Panel</title>
<style>body{background:#1a1a2e;color:#eee;font-family:Arial,sans-serif;display:flex;
justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:#16213e;padding:40px;border-radius:8px;min-width:320px}
h2{margin:0 0 20px;color:#e94560}
input{width:100%;padding:10px;margin:8px 0;background:#0f3460;
border:1px solid #e94560;color:#eee;border-radius:4px;box-sizing:border-box}
button{width:100%;padding:12px;background:#e94560;border:none;color:#fff;
cursor:pointer;border-radius:4px;font-size:16px;margin-top:10px}
.msg{color:#ff6b6b;font-size:13px;margin-top:8px}
</style></head>
<body><div class="box">
<h2>&#128274; Administration Panel</h2>
<form method="POST" action="/admin">
<input type="text" name="username" placeholder="Username" required>
<input type="password" name="password" placeholder="Password" required>
<button type="submit">Login</button>
</form>
{msg}
</div></body></html>"""

PAGE_ADMIN_LOGGED = """<!DOCTYPE html>
<html><head><title>Admin Dashboard</title>
<style>body{background:#1a1a2e;color:#eee;font-family:Arial,sans-serif;margin:0;padding:20px}
nav{background:#16213e;padding:10px 20px;display:flex;justify-content:space-between;margin:-20px -20px 20px}
nav a{color:#e94560;text-decoration:none;margin:0 8px}
h2{color:#4a9eff}table{width:100%;border-collapse:collapse}
td,th{border:1px solid #333;padding:8px;text-align:left}th{background:#0f3460}
.badge{background:#e94560;padding:2px 8px;border-radius:10px;font-size:11px}
</style></head>
<body>
<nav><span>&#128274; Admin Panel</span><div><a href="/admin/users">Users</a>
<a href="/admin/settings">Settings</a><a href="/logout">Logout</a></div></nav>
<h2>Dashboard</h2>
<p>Welcome back, <b>admin</b>. Last login: Mon Apr 14 09:21 from 10.0.0.100</p>
<h3>System Status <span class="badge">LIVE</span></h3>
<table>
<tr><th>Service</th><th>Status</th><th>Uptime</th></tr>
<tr><td>MySQL</td><td>&#10003; Running</td><td>47d 3h</td></tr>
<tr><td>Redis</td><td>&#10003; Running</td><td>47d 3h</td></tr>
<tr><td>Nginx</td><td>&#10003; Running</td><td>47d 3h</td></tr>
<tr><td>Backup</td><td>&#10003; Last: 2026-04-23 02:00</td><td>-</td></tr>
</table>
<h3>Recent Users</h3>
<table>
<tr><th>ID</th><th>Username</th><th>Email</th><th>Role</th><th>Last Login</th></tr>
<tr><td>1</td><td>admin</td><td>admin@soc.local</td><td>superadmin</td><td>2026-04-23</td></tr>
<tr><td>2</td><td>operator</td><td>ops@soc.local</td><td>operator</td><td>2026-04-22</td></tr>
<tr><td>3</td><td>deploy</td><td>deploy@soc.local</td><td>readonly</td><td>2026-04-21</td></tr>
</table>
</body></html>"""

PAGE_LOGIN = """<!DOCTYPE html>
<html><head><title>Login</title>
<style>body{background:#f0f2f5;font-family:Arial,sans-serif;display:flex;
justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:#fff;padding:40px;border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.1);min-width:300px}
h2{margin:0 0 20px;color:#333}
input{width:100%;padding:10px;margin:8px 0;border:1px solid #ddd;
border-radius:4px;box-sizing:border-box}
button{width:100%;padding:12px;background:#1877f2;border:none;color:#fff;
cursor:pointer;border-radius:4px;font-size:16px;margin-top:10px}
</style></head>
<body><div class="box">
<h2>Sign In</h2>
<form method="POST" action="/login">
<input type="text" name="username" placeholder="Username or email">
<input type="password" name="password" placeholder="Password">
<button type="submit">Sign In</button>
</form>
{msg}
</div></body></html>"""

PAGE_PHPMYADMIN = """<!DOCTYPE html>
<html><head><title>phpMyAdmin</title>
<style>body{background:#f5f5f5;font-family:Arial,sans-serif}</style>
</head><body>
<div style="background:#fff;padding:20px;max-width:400px;margin:50px auto;
border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,.2)">
<b>&#128196; phpMyAdmin 5.2.1</b>
<hr>
<form method="POST" action="/phpmyadmin">
<table><tr><td>Username:</td><td><input name="pma_username" type="text"></td></tr>
<tr><td>Password:</td><td><input name="pma_password" type="password"></td></tr>
<tr><td>Server:</td><td><input name="pma_servername" value="localhost" type="text"></td></tr>
<tr><td colspan=2><input type="submit" value="Go" style="padding:4px 16px"></td></tr>
</table>
{msg}
</form></div></body></html>"""

PAGE_WP_ADMIN = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Log In &lsaquo; My WordPress Site &#8212; WordPress</title>
<style>body{background:#f0f0f1;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
#login{width:320px;margin:100px auto}
#loginform{background:#fff;padding:26px 24px;margin-top:8px;border-radius:3px;
box-shadow:0 1px 3px rgba(0,0,0,.13)}
input[type=text],input[type=password]{width:100%;padding:8px;margin:4px 0 16px;
border:1px solid #8c8f94;border-radius:4px;box-sizing:border-box}
.button-primary{background:#2271b1;color:#fff;border:none;padding:8px 12px;
cursor:pointer;width:100%;border-radius:3px}
#login_error{background:#fff;border-left:4px solid #d63638;padding:10px;margin-bottom:10px}
</style></head>
<body><div id="login">
<h1 style="text-align:center;font-size:24px;font-weight:400">&#128292; WordPress</h1>
<div id="login_error">{msg}</div>
<form name="loginform" id="loginform" action="/wp-admin" method="post">
<input type="text" name="log" placeholder="Username or Email Address">
<input type="password" name="pwd" placeholder="Password">
<input type="submit" name="wp-submit" class="button-primary" value="Log In">
<input type="hidden" name="redirect_to" value="/wp-admin/">
</form>
</div></body></html>"""

PAGE_TOMCAT_401 = """<!DOCTYPE html>
<html><head><title>401 Unauthorized</title></head>
<body><h1>HTTP Status 401 – Unauthorized</h1>
<p>You are not authorized to view this page. Please authenticate with valid Tomcat Manager credentials.</p>
<hr><small>Apache Tomcat/10.1.7</small>
</body></html>"""

PAGE_404 = """<!DOCTYPE html>
<html><head><title>404 Not Found</title></head>
<body>
<h1>Not Found</h1>
<p>The requested URL was not found on this server.</p>
<hr><address>Apache/2.4.57 (Ubuntu) Server at 192.168.1.111 Port 80</address>
</body></html>"""

CONTENT_ENV = """\
APP_ENV=production
APP_DEBUG=false
APP_KEY=base64:dGhpc2lzYWZha2VrZXlmb3Job25leXBvdA==
APP_URL=http://192.168.1.111

DB_CONNECTION=mysql
DB_HOST=10.1.1.98
DB_PORT=3306
DB_DATABASE=production
DB_USERNAME=dbadmin
DB_PASSWORD=DB_S3cur3_2024!

REDIS_HOST=127.0.0.1
REDIS_PASSWORD=R3d1sS3cr3t
REDIS_PORT=6379

MAIL_MAILER=smtp
MAIL_HOST=10.1.1.53
MAIL_PORT=587
MAIL_USERNAME=alertas@soc.local
MAIL_PASSWORD=M@il_S3cr3t_2024
MAIL_FROM_ADDRESS=app@soc.local

AWS_ACCESS_KEY_ID=AKIAIOSFODNN7DECOY00
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYDECOYKEY
AWS_DEFAULT_REGION=eu-west-1
AWS_BUCKET=company-backups-decoy

JWT_SECRET=eyJhbGciOiJIUzI1NiIsInR5cCI6DECOY_SECRET_2024
SESSION_DRIVER=redis
SESSION_LIFETIME=120
"""

CONTENT_CONFIG_PHP = """\
<?php
/** WordPress DB credentials */
define( 'DB_NAME', 'wordpress_prod' );
define( 'DB_USER', 'wp_user' );
define( 'DB_PASSWORD', 'WP_DB_P@ss2024!' );
define( 'DB_HOST', '10.1.1.98' );
define( 'DB_CHARSET', 'utf8mb4' );

/** Authentication Keys */
define( 'AUTH_KEY',         'decoy-key-honeypot-vm203-alpha' );
define( 'SECURE_AUTH_KEY',  'decoy-key-honeypot-vm203-beta' );
define( 'LOGGED_IN_KEY',    'decoy-key-honeypot-vm203-gamma' );
define( 'NONCE_KEY',        'decoy-key-honeypot-vm203-delta' );

$table_prefix = 'wp_';
define( 'WP_DEBUG', false );
if ( ! defined( 'ABSPATH' ) ) {
    define( 'ABSPATH', __DIR__ . '/' );
}
require_once ABSPATH . 'wp-settings.php';
"""

CONTENT_GIT_CONFIG = """\
[core]
\trepositoryformatversion = 0
\tfilemode = true
\tbare = false
\tlogallrefupdates = true
[remote "origin"]
\turl = git@github.com:soc-honeycos/webapp-prod.git
\tfetch = +refs/heads/*:refs/remotes/origin/*
[branch "main"]
\tremote = origin
\tmerge = refs/heads/main
[user]
\tname = deploy
\temail = deploy@soc.local
"""

CONTENT_ACTUATOR_ENV = json.dumps({
    "activeProfiles": ["production"],
    "propertySources": [
        {"name": "applicationConfig", "properties": {
            "spring.datasource.url": {"value": "jdbc:mysql://10.1.1.98:3306/production"},
            "spring.datasource.username": {"value": "dbadmin"},
            "spring.datasource.password": {"value": "DB_S3cur3_2024!"},
            "spring.redis.host": {"value": "127.0.0.1"},
            "spring.redis.password": {"value": "R3d1sS3cr3t"},
            "server.port": {"value": "8080"},
        }}
    ]
}, indent=2)

# Credenciales señuelo que "funcionan" en el admin
_ADMIN_VALID_CREDS = {
    ("admin", "admin"),
    ("admin", "admin123"),
    ("root", "root"),
    ("administrator", "administrator"),
}

# ---------------------------------------------------------------------------
# Helper: extraer info enriquecida del request
# ---------------------------------------------------------------------------

def _req_extra(request: web.Request, cfg: dict, action: str, service: str = "http") -> dict:
    peer = request.transport.get_extra_info("peername", ("", 0)) if request.transport else ("", 0)
    return {
        "hostname": cfg["honeypot"]["hostname"],
        "environment": cfg["honeypot"]["environment"],
        "vlan": cfg["honeypot"]["vlan"],
        "host": cfg["honeypot"]["hostname"],
        "service": service,
        "action": action,
        "src_ip": request.remote or "unknown",
        "src_port": peer[1] if peer else 0,
        "method": request.method,
        "path": request.path,
        "user_agent": request.headers.get("User-Agent", ""),
        "referer": request.headers.get("Referer", ""),
        "x_forwarded_for": request.headers.get("X-Forwarded-For", ""),
        "accept_language": request.headers.get("Accept-Language", ""),
    }

def _fake_session_token(username: str) -> str:
    return hashlib.md5(f"{username}{time.time()}honeypot".encode()).hexdigest()

# ---------------------------------------------------------------------------
# Middleware de logging
# ---------------------------------------------------------------------------

def make_logging_middleware(cfg: dict, detector: BruteForceDetector):

    @web.middleware
    async def logging_middleware(request: web.Request, handler):
        logger = get_logger()
        scheme = "https" if request.secure else "http"

        try:
            response = await handler(request)
            status = response.status
        except web.HTTPException as exc:
            status = exc.status
            response = exc
        except Exception as exc:
            logger.error("http_error", extra={
                **_req_extra(request, cfg, "error", scheme),
                "error": str(exc),
            })
            raise

        logger.info(
            "request",
            extra={
                **_req_extra(request, cfg, "request", scheme),
                "status": status,
                "content_length": request.headers.get("Content-Length", ""),
                "cookie": request.headers.get("Cookie", ""),
            },
        )
        return response

    return logging_middleware


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def handle_root(request):
    return _resp(PAGE_APACHE_DEFAULT)


async def handle_admin(request):
    cfg = request.app["cfg"]
    detector = request.app["detector"]
    src = request.remote or "unknown"

    if request.method == "POST":
        data = await request.post()
        username = data.get("username", "")
        password = data.get("password", "")

        extra = {
            **_req_extra(request, cfg, "login_attempt"),
            "username": username,
            "password": password,
        }

        # Credenciales señuelo: simular acceso concedido
        if (username, password) in _ADMIN_VALID_CREDS:
            extra["result"] = "success_decoy"
            get_logger().warning("login_attempt", extra=extra)
            token = _fake_session_token(username)
            return _resp(
                PAGE_ADMIN_LOGGED,
                cookies={"PHPSESSID": token, "admin_token": token[:16]},
            )

        extra["result"] = "failed"
        get_logger().warning("login_attempt", extra=extra)
        detector.record("http", src, username)
        return _resp(
            PAGE_ADMIN.replace("{msg}", "<p class='msg'>Invalid username or password.</p>"),
        )

    return _resp(PAGE_ADMIN.replace("{msg}", ""))


async def handle_login(request):
    cfg = request.app["cfg"]
    detector = request.app["detector"]
    src = request.remote or "unknown"

    if request.method == "POST":
        data = await request.post()
        username = data.get("username", "")
        password = data.get("password", "")
        extra = {
            **_req_extra(request, cfg, "login_attempt"),
            "username": username,
            "password": password,
            "result": "failed",
        }
        get_logger().warning("login_attempt", extra=extra)
        detector.record("http", src, username)
        return _resp(
            PAGE_LOGIN.replace("{msg}", "<p style='color:red;font-size:13px'>Invalid credentials.</p>"),
        )
    return _resp(PAGE_LOGIN.replace("{msg}", ""))


async def handle_phpmyadmin(request):
    cfg = request.app["cfg"]
    detector = request.app["detector"]
    src = request.remote or "unknown"

    if request.method == "POST":
        data = await request.post()
        username = data.get("pma_username", "")
        password = data.get("pma_password", "")
        extra = {
            **_req_extra(request, cfg, "login_attempt"),
            "username": username,
            "password": password,
            "path": "/phpmyadmin",
            "result": "failed",
        }
        get_logger().warning("login_attempt", extra=extra)
        detector.record("http", src, username)
        return _resp(
            PAGE_PHPMYADMIN.replace("{msg}", "<p style='color:red'>Access denied.</p>"),
        )
    return _resp(PAGE_PHPMYADMIN.replace("{msg}", ""))


async def handle_wp_admin(request):
    cfg = request.app["cfg"]
    detector = request.app["detector"]
    src = request.remote or "unknown"

    if request.method == "POST":
        data = await request.post()
        username = data.get("log", "")
        password = data.get("pwd", "")
        extra = {
            **_req_extra(request, cfg, "login_attempt"),
            "username": username,
            "password": password,
            "path": "/wp-admin",
            "result": "failed",
        }
        get_logger().warning("login_attempt", extra=extra)
        detector.record("http", src, username)
        return _resp(
            PAGE_WP_ADMIN.replace(
                "{msg}",
                "<strong>ERROR</strong>: The password you entered for username <strong>"
                + username + "</strong> is incorrect."
            ),
            headers={**COMMON_HEADERS, "X-Powered-By": "WordPress/6.4.2"},
        )
    return _resp(PAGE_WP_ADMIN.replace("{msg}", ""),
                 headers={**COMMON_HEADERS, "X-Powered-By": "WordPress/6.4.2"})


async def handle_manager(request):
    raise web.HTTPUnauthorized(
        text=PAGE_TOMCAT_401,
        content_type="text/html",
        headers={
            **TOMCAT_HEADERS,
            "WWW-Authenticate": 'Basic realm="Tomcat Manager Application"',
        },
    )


async def handle_env(request):
    cfg = request.app["cfg"]
    get_logger().warning(
        "sensitive_file_access",
        extra={**_req_extra(request, cfg, "file_access"), "file": "/.env"},
    )
    return _resp(CONTENT_ENV, content_type="text/plain",
                 headers={**COMMON_HEADERS, "Content-Disposition": "inline"})


async def handle_config_php(request):
    cfg = request.app["cfg"]
    get_logger().warning(
        "sensitive_file_access",
        extra={**_req_extra(request, cfg, "file_access"), "file": "/config.php"},
    )
    return _resp(CONTENT_CONFIG_PHP, content_type="text/plain")


async def handle_git_config(request):
    cfg = request.app["cfg"]
    get_logger().warning(
        "sensitive_file_access",
        extra={**_req_extra(request, cfg, "file_access"), "file": "/.git/config"},
    )
    return _resp(CONTENT_GIT_CONFIG, content_type="text/plain")


async def handle_actuator(request):
    cfg = request.app["cfg"]
    get_logger().warning(
        "sensitive_file_access",
        extra={**_req_extra(request, cfg, "file_access"), "file": request.path},
    )
    if "env" in request.path or "configprops" in request.path:
        return _resp(CONTENT_ACTUATOR_ENV, content_type="application/json",
                     headers={"Server": "Apache-Coyote/1.1"})
    # Otros endpoints de actuator devuelven JSON vacío
    return _resp('{"status":"UP"}', content_type="application/json",
                 headers={"Server": "Apache-Coyote/1.1"})


async def handle_backup_zip(request):
    cfg = request.app["cfg"]
    get_logger().warning(
        "sensitive_file_access",
        extra={**_req_extra(request, cfg, "file_access"), "file": request.path},
    )
    # ZIP mínimo válido (vacío) con cabecera real
    import struct
    eocd = struct.pack("<IHHHHIIH", 0x06054b50, 0, 0, 0, 0, 0, 22, 0)
    headers = {**COMMON_HEADERS,
               "Content-Disposition": f'attachment; filename="{request.path.lstrip("/")}"'}
    return web.Response(body=eocd, content_type="application/zip",
                        status=200, headers=headers)


async def handle_xmlrpc(request):
    """WordPress xmlrpc.py — muy sondeado por bots."""
    cfg = request.app["cfg"]
    get_logger().warning(
        "xmlrpc_probe",
        extra={**_req_extra(request, cfg, "probe"), "file": "/xmlrpc.php"},
    )
    body = """\
<?xml version="1.0" encoding="UTF-8"?>
<methodResponse>
  <fault>
    <value><struct>
      <member><name>faultCode</name><value><int>403</int></value></member>
      <member><name>faultString</name><value><string>XML-RPC services are disabled on this site.</string></value></member>
    </struct></value>
  </fault>
</methodResponse>"""
    return _resp(body, content_type="text/xml",
                 headers={**COMMON_HEADERS, "X-Powered-By": "WordPress/6.4.2"})


async def handle_server_status(request):
    cfg = request.app["cfg"]
    get_logger().info(
        "server_status_probe",
        extra={**_req_extra(request, cfg, "probe"), "path": "/server-status"},
    )
    page = """\
<!DOCTYPE html><html><head><title>Apache Status</title></head><body>
<h1>Apache Server Status for 192.168.1.111</h1>
<pre>
ServerVersion: Apache/2.4.57 (Ubuntu)
ServerMPM: event
Server Built: 2023-08-31T12:00:00
CurrentTime: {dt}
RestartTime: {dt}
ParentServerConfigGeneration: 1
ParentServerMPMGeneration: 0
ServerUptimeSeconds: 4067592
ServerUptime: 47 days 3 hours 12 minutes
Total Accesses: 184392
Total kBytes: 24276
BusyWorkers: 1
IdleWorkers: 49
</pre></body></html>""".format(dt=datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT"))
    return _resp(page)


# Rutas de scanner que se loggean como WARNING y devuelven 404
_SCANNER_ROUTES = {
    # Archivos sensibles
    "/backup.zip", "/backup.tar.gz", "/backup.sql", "/dump.sql",
    "/db.sql", "/database.sql", "/.htpasswd", "/.htaccess",
    "/robots.txt", "/sitemap.xml", "/crossdomain.xml",
    "/web.config", "/Web.config", "/WEB-INF/web.xml",
    "/wp-config.php", "/wp-config.php.bak",
    "/wp-includes/wlwmanifest.xml",
    "/wp-json/wp/v2/users",
    "/.DS_Store",
    # Paneles de admin
    "/admin/login", "/admin/index.php", "/administrator",
    "/administrator/index.php", "/admin.php", "/manage",
    "/panel", "/cpanel", "/webadmin", "/siteadmin",
    "/controlpanel", "/filemanager",
    # APIs y frameworks
    "/api", "/api/v1", "/api/v2", "/api/v1/users",
    "/api/v1/admin", "/api/v1/config",
    "/swagger", "/swagger-ui.html", "/swagger.json",
    "/api-docs", "/openapi.json", "/v1", "/v2",
    "/graphql", "/graphiql",
    "/console", "/h2-console", "/solr",
    # Java / Spring
    "/actuator", "/actuator/health", "/actuator/metrics",
    "/actuator/loggers", "/actuator/mappings",
    "/health", "/metrics", "/info",
    # Shells y exploits conocidos
    "/shell.php", "/cmd.php", "/c99.php", "/r57.php",
    "/upload.php", "/uploads/shell.php",
    "/tmp/shell.php", "/cgi-bin/test.cgi",
    "/cgi-bin/bash", "/cgi-bin/id",
    # Proxies y herramientas
    "/proxy", "/proxy.php", "/tunnel.php",
    "/socket.io/", "/sockjs-node/",
    # Otros
    "/old", "/bak", "/test", "/dev", "/staging",
    "/_profiler", "/_wdt", "/debug",
    "/telescope", "/horizon",
    "/adminer.php", "/adminer",
}


async def handle_scanner_probe(request):
    """Handler genérico para rutas de scanner — loggea y devuelve 404."""
    cfg = request.app["cfg"]
    get_logger().warning(
        "scanner_probe",
        extra={
            **_req_extra(request, cfg, "probe"),
            "path": request.path,
        },
    )
    return _resp(PAGE_404, status=404)


async def handle_404(request):
    return _resp(PAGE_404, status=404)


# ---------------------------------------------------------------------------
# Factory de la app aiohttp
# ---------------------------------------------------------------------------

def _build_app(cfg: dict, detector: BruteForceDetector) -> web.Application:
    app = web.Application(middlewares=[make_logging_middleware(cfg, detector)])
    app["cfg"] = cfg
    app["detector"] = detector

    # Rutas principales
    app.router.add_get("/", handle_root)
    app.router.add_route("*", "/admin", handle_admin)
    app.router.add_route("*", "/admin/", handle_admin)
    app.router.add_route("*", "/login", handle_login)
    app.router.add_route("*", "/phpmyadmin", handle_phpmyadmin)
    app.router.add_route("*", "/phpmyadmin/", handle_phpmyadmin)
    app.router.add_route("*", "/wp-admin", handle_wp_admin)
    app.router.add_route("*", "/wp-admin/", handle_wp_admin)
    app.router.add_route("*", "/manager", handle_manager)
    app.router.add_route("*", "/manager/", handle_manager)
    app.router.add_route("*", "/manager/html", handle_manager)

    # Archivos sensibles
    app.router.add_get("/.env", handle_env)
    app.router.add_get("/config.php", handle_config_php)
    app.router.add_get("/.git/config", handle_git_config)

    # Actuator Spring Boot
    app.router.add_get("/actuator/env", handle_actuator)
    app.router.add_get("/actuator/configprops", handle_actuator)
    app.router.add_get("/actuator/health", handle_actuator)
    app.router.add_get("/actuator/info", handle_actuator)

    # Backups descargables (ZIP señuelo real)
    for bk in ("/backup.zip", "/backup.tar.gz", "/backup.sql", "/db.sql", "/dump.sql"):
        app.router.add_get(bk, handle_backup_zip)

    # WordPress xmlrpc
    app.router.add_route("*", "/xmlrpc.php", handle_xmlrpc)

    # Apache server-status
    app.router.add_get("/server-status", handle_server_status)

    # Rutas de scanner
    for route in _SCANNER_ROUTES:
        try:
            app.router.add_route("*", route, handle_scanner_probe)
        except Exception:
            pass  # Ignorar rutas duplicadas

    # 404 genérico
    app.router.add_route("*", "/{path_info:.*}", handle_404)

    return app


async def start_http(cfg: dict, detector: BruteForceDetector):
    port = cfg["services"]["http"]["port"]
    logger = get_logger()
    app = _build_app(cfg, detector)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(
        "service_started",
        extra={
            "hostname": cfg["honeypot"]["hostname"],
            "environment": cfg["honeypot"]["environment"],
            "vlan": cfg["honeypot"]["vlan"],
            "host": cfg["honeypot"]["hostname"],
            "service": "http",
            "action": "connection",
            "port": port,
        },
    )
    # Mantener vivo
    while True:
        await asyncio.sleep(3600)


async def start_https(cfg: dict, detector: BruteForceDetector):
    port = cfg["services"]["https"]["port"]
    cert_file = cfg["services"]["https"]["cert_file"]
    key_file = cfg["services"]["https"]["key_file"]
    logger = get_logger()

    if not (os.path.exists(cert_file) and os.path.exists(key_file)):
        _generate_self_signed_cert(cert_file, key_file, cfg["honeypot"]["ip"])

    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(cert_file, key_file)

    app = _build_app(cfg, detector)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port, ssl_context=ssl_ctx)
    await site.start()
    logger.info(
        "service_started",
        extra={
            "hostname": cfg["honeypot"]["hostname"],
            "environment": cfg["honeypot"]["environment"],
            "vlan": cfg["honeypot"]["vlan"],
            "host": cfg["honeypot"]["hostname"],
            "service": "https",
            "action": "connection",
            "port": port,
        },
    )
    while True:
        await asyncio.sleep(3600)


def _generate_self_signed_cert(cert_file: str, key_file: str, ip: str):
    import datetime
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import ipaddress

    os.makedirs(os.path.dirname(cert_file), exist_ok=True)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "ES"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SOC honeycos"),
        x509.NameAttribute(NameOID.COMMON_NAME, "honeypot.soc.local"),
    ])

    san = x509.SubjectAlternativeName([
        x509.DNSName("honeypot.soc.local"),
        x509.DNSName("honeypot"),
        x509.IPAddress(ipaddress.IPv4Address(ip)),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(san, critical=False)
        .sign(private_key, hashes.SHA256())
    )

    with open(key_file, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(cert_file, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
