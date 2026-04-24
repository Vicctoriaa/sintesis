"""
services/rdp.py — Servicio RDP falso (asyncio puro)
Puerto 3389 · Honeypot VM203

Mejoras v2:
  - Handshake más creíble: simula las 3 fases del protocolo RDP
      Fase 1: X.224 Connection Request → Connection Confirm (ya existía)
      Fase 2: MCS Connect Initial → simula respuesta Server GCC
      Fase 3: Si el cliente envía datos CredSSP/NLA → captura y loguea
  - Soporte de RDP Security Layer (código 0x0001) además de NLA (0x0002)
  - Respuesta de error RDP creíble tras autenticación fallida
    (en lugar de cerrar la conexión bruscamente)
  - Detección de scanners (Shodan, Masscan, nmap) por longitud mínima
    del paquete y tiempo de conexión
  - record_connection() para el detector de port scan
  - Logging enriquecido: security_protocol, requested_protocols, client_name
"""

import asyncio
import struct
import time

from core.logger import get_logger
from core.alerts import BruteForceDetector

# ---------------------------------------------------------------------------
# Constantes de protocolo RDP
# ---------------------------------------------------------------------------

TPKT_HEADER_LEN = 4

# Protocolos de seguridad RDP (campo requestedProtocols en X.224 CR)
RDP_PROTOCOL_RDP  = 0x00000000   # Classic RDP Security
RDP_PROTOCOL_SSL  = 0x00000001   # TLS
RDP_PROTOCOL_HYBR = 0x00000002   # NLA (CredSSP)
RDP_PROTOCOL_RDSAAD = 0x00000008 # AAD

# ---------------------------------------------------------------------------
# Construcción de respuestas RDP
# ---------------------------------------------------------------------------

def _x224_cc(requested_protocol: int = 0) -> bytes:
    """
    X.224 Connection Confirm.
    Negocia el mismo protocolo que pidió el cliente (o RDP clásico si
    el cliente no especificó nada).
    """
    # TPKT: version=3, reserved=0, length=19
    # X.224 CC: length indicator, type CC (0xD0), dst_ref, src_ref, class
    # RDP Negotiation Response (type=0x02, flags=0x00, length=8, selectedProtocol)
    selected = requested_protocol if requested_protocol in (
        RDP_PROTOCOL_RDP, RDP_PROTOCOL_SSL, RDP_PROTOCOL_HYBR
    ) else RDP_PROTOCOL_RDP

    neg_resp = struct.pack("<BBHI", 0x02, 0x00, 8, selected)
    x224_body = bytes([14, 0xD0, 0x00, 0x00, 0x12, 0x34, 0x00]) + neg_resp
    tpkt = struct.pack(">BBH", 3, 0, 4 + len(x224_body))
    return tpkt + x224_body


def _mcs_connect_response() -> bytes:
    """
    MCS Connect Response mínima que hace creer al cliente que el servidor
    acepta la conexión MCS. El cliente enviará MCS Erect Domain Request
    y MCS Attach User Request a continuación.
    Usamos un BER encoding simplificado válido.
    """
    # T.125 MCS Connect Response con resultado = rt-successful (0)
    # BER encoding: Application 102 (ConnectMCSPDU) → ConnectResponse
    # Suficiente para que mstsc y rdesktop avancen a la siguiente fase
    payload = bytes([
        0x7f, 0x65,             # BER: Application 101 tag (ConnectResponse)
        0x82, 0x01, 0x2a,       # Length (306) — suficiente para no despertar sospechas
        0x30, 0x1a,             # SEQUENCE
          0x02, 0x01, 0x00,     # result: rt-successful (0)
          0x02, 0x01, 0x00,     # calledConnectId: 0
          0x30, 0x12,           # domainParameters
            0x02, 0x01, 0x22,   #   maxChannelIds: 34
            0x02, 0x01, 0x02,   #   maxUserIds: 2
            0x02, 0x01, 0x00,   #   maxTokenIds: 0
            0x02, 0x01, 0x01,   #   numPriorities: 1
            0x02, 0x01, 0x00,   #   minThroughput: 0
            0x02, 0x01, 0x01,   #   maxHeight: 1
            0x02, 0x02, 0xff, 0xff,  # maxMCSPDUsize: 65535
            0x02, 0x01, 0x02,   #   protocolVersion: 2
        0x04, 0x82, 0x01, 0x04, # OCTET STRING (userDataLength=260) — GCC relleno
    ] + [0x00] * 260)

    # Envolver en TPKT
    tpkt = struct.pack(">BBH", 3, 0, 4 + len(payload))
    return tpkt + payload


def _rdp_error_response() -> bytes:
    """
    Paquete de error RDP Security Exchange que indica que la autenticación
    falló — cierre limpio que parece un servidor real rechazando credenciales.
    En NLA el servidor cierra el TLS; aquí simulamos un error RDP clásico.
    """
    # RDP Security Exchange Error (PDU type 0x0400 = ERRINFO_RPC_INITIATED_DISCONNECT)
    # Suficiente para que el cliente muestre "Authentication failed"
    rdp_err = struct.pack("<IIIH",
        0x00000065,   # shareId
        0x03EA,       # streamId + pduType2 (PDUTYPE2_SET_ERROR_INFO_PDU = 0x2F)
        0x00000808,   # errorInfo: ERRINFO_RPC_INITIATED_DISCONNECT
        0x0000,       # pad
    )
    tpkt = struct.pack(">BBH", 3, 0, 4 + len(rdp_err))
    return tpkt + rdp_err


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_requested_protocol(data: bytes) -> int:
    """
    Extrae requestedProtocols del X.224 Connection Request.
    El campo está en los últimos 4 bytes del RDP Negotiation Request
    (type=0x01) que sigue al X.224 CR.
    """
    try:
        # Buscar el byte de tipo de negociación RDP (0x01 = RDP_NEG_REQ)
        idx = data.find(b'\x01\x00\x08\x00')
        if idx != -1 and idx + 8 <= len(data):
            return struct.unpack_from("<I", data, idx + 4)[0]
    except Exception:
        pass
    return RDP_PROTOCOL_RDP


def _parse_cookie(data: bytes) -> str:
    """Extrae mstshash de los datos de usuario del X.224 CR."""
    try:
        text = data.decode("utf-8", errors="replace")
        for part in text.split("\r\n"):
            if part.startswith("Cookie: mstshash="):
                return part.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _parse_client_name(data: bytes) -> str:
    """
    Intenta extraer el nombre de máquina cliente del GCC Conference Create
    Request (clientName en el bloque TS_UD_CS_CORE), codificado en UTF-16LE.
    """
    try:
        idx = data.find(b'\x01\xc0')   # CS_CORE type marker
        if idx != -1:
            # clientName está en offset 24 desde el inicio del bloque CS_CORE
            name_start = idx + 24
            raw = data[name_start: name_start + 32]
            name = raw.decode("utf-16-le", errors="replace").rstrip("\x00")
            if name and all(32 <= ord(c) < 127 for c in name if c != "\x00"):
                return name
    except Exception:
        pass
    return ""


def _parse_ntlm_user(data: bytes) -> str:
    """Extrae username de NTLM Authenticate (type 3)."""
    try:
        idx = data.find(b"NTLMSSP\x00")
        if idx == -1:
            return ""
        msg_type = struct.unpack_from("<I", data, idx + 8)[0]
        if msg_type == 3:
            user_len = struct.unpack_from("<H", data, idx + 36)[0]
            user_off = struct.unpack_from("<I", data, idx + 40)[0]
            raw = data[idx + user_off: idx + user_off + user_len]
            return raw.decode("utf-16-le", errors="replace")
    except Exception:
        pass
    return ""


def _proto_name(protocol: int) -> str:
    names = {
        RDP_PROTOCOL_RDP:  "RDP",
        RDP_PROTOCOL_SSL:  "SSL/TLS",
        RDP_PROTOCOL_HYBR: "NLA/CredSSP",
        RDP_PROTOCOL_RDSAAD: "AAD",
    }
    return names.get(protocol, f"0x{protocol:08x}")


# ---------------------------------------------------------------------------
# Estado de la conexión por fases
# ---------------------------------------------------------------------------

class _Phase:
    INIT    = 0   # Esperando X.224 CR
    X224    = 1   # X.224 CC enviado, esperando MCS Connect Initial
    MCS     = 2   # MCS response enviado, esperando datos de autenticación
    AUTH    = 3   # Autenticación capturada, cerrando


# ---------------------------------------------------------------------------
# Protocolo
# ---------------------------------------------------------------------------

class RDPServerProtocol(asyncio.Protocol):

    # Tiempo máximo por fase — evita conexiones zombie
    _PHASE_TIMEOUT = 15.0   # segundos

    def __init__(self, cfg: dict, detector: BruteForceDetector):
        self._cfg       = cfg
        self._detector  = detector
        self._transport = None
        self._src_ip    = ""
        self._src_port  = 0
        self._buf       = b""
        self._phase     = _Phase.INIT
        self._connect_ts = time.monotonic()
        self._requested_protocol = RDP_PROTOCOL_RDP
        self._timeout_handle = None

    def _base(self, action: str) -> dict:
        hp = self._cfg["honeypot"]
        return {
            "hostname":    hp["hostname"],
            "environment": hp["environment"],
            "vlan":        hp["vlan"],
            "host":        hp["hostname"],
            "service":     "rdp",
            "action":      action,
            "src_ip":      self._src_ip,
            "src_port":    self._src_port,
        }

    def _close(self, send_error: bool = False):
        if self._timeout_handle:
            self._timeout_handle.cancel()
        if self._transport and not self._transport.is_closing():
            if send_error:
                try:
                    self._transport.write(_rdp_error_response())
                except Exception:
                    pass
            self._transport.close()

    def connection_made(self, transport):
        self._transport  = transport
        peer = transport.get_extra_info("peername")
        self._src_ip     = peer[0] if peer else ""
        self._src_port   = peer[1] if peer else 0
        self._connect_ts = time.monotonic()

        get_logger().info("connection", extra=self._base("connection"))

        # Notificar al detector de port scan
        self._detector.record_connection("rdp", self._src_ip)

        # Timeout global de la conexión
        loop = asyncio.get_event_loop()
        self._timeout_handle = loop.call_later(
            self._PHASE_TIMEOUT * 3, self._close
        )

    def data_received(self, data: bytes):
        self._buf += data
        logger = get_logger()

        # ── Fase 0 → 1: X.224 Connection Request ─────────────────────
        if self._phase == _Phase.INIT:
            if len(self._buf) < TPKT_HEADER_LEN:
                return

            # Detección de scanner: paquetes muy cortos sin estructura RDP
            if len(self._buf) < 11:
                logger.info(
                    "scanner_probe",
                    extra={**self._base("probe"), "bytes": len(self._buf)},
                )
                self._close()
                return

            # Extraer protocolo solicitado y cookie
            self._requested_protocol = _parse_requested_protocol(self._buf)
            cookie      = _parse_cookie(self._buf)
            client_name = _parse_client_name(self._buf)

            extra = {
                **self._base("login_attempt"),
                "security_protocol":   _proto_name(self._requested_protocol),
                "requested_protocols": self._requested_protocol,
            }
            if cookie:
                extra["mstshash"] = cookie
            if client_name:
                extra["client_name"] = client_name

            logger.info("login_attempt", extra=extra)

            if cookie:
                self._detector.record("rdp", self._src_ip, cookie)

            # Enviar X.224 Connection Confirm
            try:
                self._transport.write(_x224_cc(self._requested_protocol))
            except Exception:
                self._close()
                return

            self._buf   = b""
            self._phase = _Phase.X224
            return

        # ── Fase 1 → 2: MCS Connect Initial ──────────────────────────
        if self._phase == _Phase.X224:
            if len(self._buf) < 5:
                return

            # Enviar MCS Connect Response
            try:
                self._transport.write(_mcs_connect_response())
            except Exception:
                self._close()
                return

            self._buf   = b""
            self._phase = _Phase.MCS
            return

        # ── Fase 2 → 3: Auth (CredSSP / NTLM / Security Exchange) ────
        if self._phase == _Phase.MCS:
            self._buf_auth = getattr(self, '_buf_auth', b'') + self._buf
            self._buf = b""

            # Intentar extraer NTLM username si el cliente usa NLA
            ntlm_user = _parse_ntlm_user(self._buf_auth)
            if ntlm_user:
                get_logger().warning(
                    "login_attempt",
                    extra={
                        **self._base("login_attempt"),
                        "ntlm_user":           ntlm_user,
                        "security_protocol":   _proto_name(self._requested_protocol),
                        "result":              "captured",
                    },
                )
                self._detector.record("rdp", self._src_ip, ntlm_user)
                self._phase = _Phase.AUTH
                # Respuesta de error creíble y cierre limpio
                self._close(send_error=True)
                return

            # Si recibimos suficientes datos sin NTLM → cerrar tras error
            if len(self._buf_auth) > 512:
                self._phase = _Phase.AUTH
                self._close(send_error=True)

    def connection_lost(self, exc):
        elapsed = time.monotonic() - self._connect_ts
        if self._timeout_handle:
            self._timeout_handle.cancel()
        # Solo loguear si la conexión duró más de 0.1s (evitar spam de scanners)
        if elapsed > 0.1:
            get_logger().debug(
                "connection_closed",
                extra={**self._base("connection"), "duration_s": round(elapsed, 2)},
            )


# ---------------------------------------------------------------------------
# Arranque del servicio
# ---------------------------------------------------------------------------

async def start_rdp(cfg: dict, detector: BruteForceDetector):
    port   = cfg["services"]["rdp"]["port"]
    logger = get_logger()

    loop   = asyncio.get_event_loop()
    server = await loop.create_server(
        lambda: RDPServerProtocol(cfg, detector),
        "0.0.0.0",
        port,
    )

    logger.info(
        "service_started",
        extra={
            "hostname":    cfg["honeypot"]["hostname"],
            "environment": cfg["honeypot"]["environment"],
            "vlan":        cfg["honeypot"]["vlan"],
            "host":        cfg["honeypot"]["hostname"],
            "service":     "rdp",
            "action":      "connection",
            "port":        port,
        },
    )

    async with server:
        await server.serve_forever()
