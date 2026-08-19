"""Minimal MTProto proxy checker (FakeTLS + obfuscated2)."""

from __future__ import annotations

import hashlib
import hmac
import os
import socket
import struct
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PROTO_ABRIDGED = b"\xef\xef\xef\xef"
PROTO_INTERMEDIATE = b"\xee\xee\xee\xee"
PROTO_SECURE = b"\xdd\xdd\xdd\xdd"
REQ_PQ_MULTI = 0xBE7E8EF1
RES_PQ = 0x05162463
FAKETLS_CLIENT_HELLO_LEN = 517
FAKETLS_MAX_APP_DATA = 1425
FAKETLS_CCS = b"\x14\x03\x03\x00\x01\x01"
FAKETLS_APP_DATA_PREFIX = b"\x17\x03\x03"
DEFAULT_DOMAIN = "www.google.com"


class SecretKind(str, Enum):
    FAKETLS = "faketls"
    DD = "dd"
    PLAIN = "plain"


@dataclass(frozen=True, slots=True)
class ParsedSecret:
    raw: bytes
    kind: SecretKind
    domain: str = DEFAULT_DOMAIN


@dataclass(frozen=True, slots=True)
class ProxyEndpoint:
    host: str
    port: int
    secret: ParsedSecret


@dataclass(slots=True)
class MtprotoCheckResult:
    ok: bool
    rtt_ms: float | None = None
    mode: str | None = None
    dc: int | None = None
    error: str | None = None


class ProtocolError(Exception):
    pass


def parse_proxy_url(url: str) -> ProxyEndpoint:
    normalized = url.strip().replace("tg://", "https://", 1)
    parsed = urlparse(normalized)
    params = parse_qs(parsed.query)

    host = params.get("server", [None])[0]
    port_raw = params.get("port", [None])[0]
    secret_raw = params.get("secret", [None])[0]

    if not host or not port_raw or not secret_raw:
        raise ValueError("Invalid proxy URL")

    return ProxyEndpoint(
        host=host,
        port=int(port_raw),
        secret=decode_secret(unquote(secret_raw)),
    )


def decode_secret(secret: str) -> ParsedSecret:
    secret = secret.strip()
    lower = secret.lower()

    if all(ch in "0123456789abcdef" for ch in lower):
        if lower.startswith("ee") and len(lower) >= 34:
            domain = ""
            if len(lower) > 34:
                try:
                    domain = bytes.fromhex(lower[34:]).decode("ascii", "ignore").rstrip("\x00")
                except ValueError:
                    domain = ""
            return ParsedSecret(
                raw=bytes.fromhex(lower[2:34]),
                kind=SecretKind.FAKETLS,
                domain=domain or DEFAULT_DOMAIN,
            )
        if lower.startswith("dd") and len(lower) >= 34:
            return ParsedSecret(
                raw=bytes.fromhex(lower[2:34]),
                kind=SecretKind.DD,
            )
        raw = bytes.fromhex(lower)
        if len(raw) != 16:
            raise ValueError("Plain hex secret must be 16 bytes")
        return ParsedSecret(raw=raw, kind=SecretKind.PLAIN)

    raise ValueError("Unsupported secret format")


def check_proxy(
    url: str,
    *,
    connect_timeout: float = 3.0,
    response_timeout: float = 5.0,
    dc: int = 2,
) -> MtprotoCheckResult:
    started = time.perf_counter()
    try:
        target = parse_proxy_url(url)
    except Exception as exc:
        return MtprotoCheckResult(ok=False, error=str(exc))

    try:
        sock = socket.create_connection(
            (target.host, target.port),
            timeout=connect_timeout,
        )
    except TimeoutError:
        return MtprotoCheckResult(ok=False, error="Connection timed out")
    except OSError as exc:
        return MtprotoCheckResult(ok=False, error=str(exc))

    try:
        sock.settimeout(response_timeout)
        if target.secret.kind is SecretKind.FAKETLS:
            transport = FakeTlsTransport(sock, target.secret.raw, target.secret.domain)
            transport.handshake()
            mode = "faketls"
        else:
            transport = PlainTransport(sock)
            mode = "secure"

        init_packet, enc, dec = make_obfuscated2_handshake(target.secret.raw, dc)
        transport.write(init_packet)
        nonce, req = make_unencrypted_req_pq_multi()
        transport.write(enc.update(frame_message(req)))
        frame = read_frame(transport, dec)
        parse_res_pq(frame, nonce)
    except TimeoutError:
        return MtprotoCheckResult(ok=False, error="Response timed out")
    except (ProtocolError, OSError) as exc:
        return MtprotoCheckResult(ok=False, error=str(exc))
    finally:
        sock.close()

    return MtprotoCheckResult(
        ok=True,
        rtt_ms=(time.perf_counter() - started) * 1000,
        mode=mode,
        dc=dc,
    )


def aes_ctr(key: bytes, iv: bytes) -> Any:
    return Cipher(algorithms.AES(key), modes.CTR(iv)).encryptor()


def make_obfuscated2_handshake(secret: bytes, dc_id: int) -> tuple[bytes, Any, Any]:
    forbidden = {
        b"GET ",
        b"POST",
        b"HEAD",
        b"OPTI",
        b"\x00\x00\x00\x00",
        PROTO_ABRIDGED,
        PROTO_INTERMEDIATE,
        PROTO_SECURE,
    }

    while True:
        init = bytearray(os.urandom(64))
        if init[0] == 0xEF:
            continue
        if bytes(init[:4]) in forbidden:
            continue
        if bytes(init[4:8]) == b"\x00\x00\x00\x00":
            continue
        break

    init[56:60] = PROTO_SECURE
    init[60] = dc_id & 0xFF
    init[61:64] = b"\x00\x00\x00"

    enc_key = hashlib.sha256(bytes(init[8:40]) + secret).digest()
    dec_key = hashlib.sha256(bytes(init[55:23:-1]) + secret).digest()
    enc = aes_ctr(enc_key, bytes(init[40:56]))
    dec = aes_ctr(dec_key, bytes(init[23:7:-1]))
    encrypted_init = enc.update(bytes(init))
    init[56:64] = encrypted_init[56:64]
    return bytes(init), enc, dec


def make_unencrypted_req_pq_multi() -> tuple[bytes, bytes]:
    nonce = os.urandom(16)
    payload = struct.pack("<I", REQ_PQ_MULTI) + nonce
    msg_id = int(time.time() * (2**32)) & ~3
    message = b"\x00" * 8 + struct.pack("<Q", msg_id) + struct.pack("<I", len(payload)) + payload
    return nonce, message


def frame_message(data: bytes) -> bytes:
    padding_len = os.urandom(1)[0] % 4
    padding = os.urandom(padding_len)
    return struct.pack("<I", len(data) + padding_len) + data + padding


def read_frame(transport: "PlainTransport | FakeTlsTransport", dec: Any) -> bytes:
    length_bytes = dec.update(transport.read_exact(4))
    frame_len = struct.unpack("<I", length_bytes)[0]
    if frame_len > 0x80000000:
        frame_len -= 0x80000000
    if frame_len <= 0 or frame_len > 2 * 1024 * 1024:
        raise ProtocolError(f"Bad frame length: {frame_len}")
    return bytes(dec.update(transport.read_exact(frame_len)))


def parse_res_pq(frame: bytes, expected_nonce: bytes) -> None:
    if len(frame) < 40 or frame[:8] != b"\x00" * 8:
        raise ProtocolError("Invalid MTProto response")
    msg_len = struct.unpack("<I", frame[16:20])[0]
    body = frame[20 : 20 + msg_len]
    if struct.unpack("<I", body[:4])[0] != RES_PQ:
        raise ProtocolError("Unexpected MTProto constructor")
    if body[4:20] != expected_nonce:
        raise ProtocolError("Nonce mismatch")


class PlainTransport:
    def __init__(self, sock: socket.socket):
        self.sock = sock

    def write(self, data: bytes) -> None:
        self.sock.sendall(data)

    def read_exact(self, n: int) -> bytes:
        return recv_exact(self.sock, n)


class FakeTlsTransport:
    def __init__(self, sock: socket.socket, secret: bytes, domain: str):
        self.sock = sock
        self.secret = secret
        self.domain = domain or DEFAULT_DOMAIN
        self.read_buffer = bytearray()
        self.did_first_write = False

    def handshake(self) -> None:
        client_hello, client_random = make_faketls_client_hello(self.secret, self.domain)
        self.sock.sendall(client_hello)

        first_header = recv_exact(self.sock, 5)
        record_type, payload_len = parse_tls_header(first_header)
        if record_type != 0x16:
            raise ProtocolError("Expected FakeTLS ServerHello")

        first_payload = recv_exact(self.sock, payload_len)
        ccs = recv_exact(self.sock, len(FAKETLS_CCS))
        if ccs != FAKETLS_CCS:
            raise ProtocolError("Bad FakeTLS ChangeCipherSpec")

        app_header = recv_exact(self.sock, 5)
        app_type, app_len = parse_tls_header(app_header)
        if app_type != 0x17:
            raise ProtocolError("Expected FakeTLS application data")

        app_payload = recv_exact(self.sock, app_len)
        response = first_header + first_payload + ccs + app_header + app_payload
        validate_faketls_server_response(self.secret, client_random, response)

    def write(self, data: bytes) -> None:
        out = bytearray()
        if not self.did_first_write:
            out += FAKETLS_CCS
            self.did_first_write = True
        for offset in range(0, len(data), FAKETLS_MAX_APP_DATA):
            chunk = data[offset : offset + FAKETLS_MAX_APP_DATA]
            out += FAKETLS_APP_DATA_PREFIX + struct.pack(">H", len(chunk)) + chunk
        self.sock.sendall(bytes(out))

    def read_exact(self, n: int) -> bytes:
        while len(self.read_buffer) < n:
            header = recv_exact(self.sock, 5)
            record_type, payload_len = parse_tls_header(header)
            payload = recv_exact(self.sock, payload_len)
            if record_type == 0x14 and payload == b"\x01":
                continue
            if record_type != 0x17:
                raise ProtocolError("Expected FakeTLS application data")
            self.read_buffer += payload
        out = bytes(self.read_buffer[:n])
        del self.read_buffer[:n]
        return out


def recv_exact(sock: socket.socket, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        chunk = sock.recv(n - len(out))
        if not chunk:
            raise ProtocolError(f"Connection closed while reading {n} bytes")
        out += chunk
    return bytes(out)


def parse_tls_header(header: bytes) -> tuple[int, int]:
    if len(header) != 5:
        raise ProtocolError("Short TLS header")
    return header[0], struct.unpack(">H", header[3:5])[0]


def generate_x25519_public_key() -> bytes:
    private_key = x25519.X25519PrivateKey.generate()
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def make_grease_values() -> list[int]:
    greases = [(value & 0xF0) + 0x0A for value in os.urandom(7)]
    for index in range(1, len(greases), 2):
        if greases[index] == greases[index - 1]:
            greases[index] = 0x10 ^ greases[index]
    return greases


def add_grease(out: bytearray, greases: list[int], index: int) -> None:
    value = greases[index]
    out += bytes([value, value])


def add_u16(out: bytearray, value: int) -> None:
    out += struct.pack(">H", value)


def make_faketls_client_hello(secret: bytes, domain: str) -> tuple[bytes, bytes]:
    if len(secret) != 16:
        raise ProtocolError(f"FakeTLS secret must be 16 bytes, got {len(secret)}")

    domain_ascii = (domain or DEFAULT_DOMAIN).encode("ascii", "ignore").decode("ascii")
    domain_ascii = domain_ascii or DEFAULT_DOMAIN
    domain_bytes = domain_ascii.encode("ascii")
    greases = make_grease_values()
    out = bytearray()

    out += b"\x16\x03\x01\x02\x00\x01\x00\x01\xfc\x03\x03"
    random_offset = len(out)
    out += b"\x00" * 32
    out += b"\x20"
    out += os.urandom(32)
    out += b"\x00\x22"
    add_grease(out, greases, 0)
    out += (
        b"\x13\x01\x13\x02\x13\x03\xc0\x2b\xc0\x2f\xc0\x2c\xc0\x30"
        b"\xcc\xa9\xcc\xa8\xc0\x13\xc0\x14\x00\x9c\x00\x9d\x00\x2f"
        b"\x00\x35\x00\x0a\x01\x00\x01\x91"
    )
    add_grease(out, greases, 2)
    out += b"\x00\x00\x00\x00"
    add_u16(out, len(domain_bytes) + 5)
    add_u16(out, len(domain_bytes) + 3)
    out += b"\x00"
    add_u16(out, len(domain_bytes))
    out += domain_bytes
    out += b"\x00\x17\x00\x00\xff\x01\x00\x01\x00\x00\x0a\x00\x0a\x00\x08"
    add_grease(out, greases, 4)
    out += (
        b"\x00\x1d\x00\x17\x00\x18\x00\x0b\x00\x02\x01\x00\x00\x23\x00\x00"
        b"\x00\x10\x00\x0e\x00\x0c\x02\x68\x32\x08\x68\x74\x74\x70\x2f\x31"
        b"\x2e\x31\x00\x05\x00\x05\x01\x00\x00\x00\x00\x00\x0d\x00\x14\x00"
        b"\x12\x04\x03\x08\x04\x04\x01\x05\x03\x08\x05\x05\x01\x08\x06\x06"
        b"\x01\x02\x01\x00\x12\x00\x00\x00\x33\x00\x2b\x00\x29"
    )
    add_grease(out, greases, 4)
    out += b"\x00\x01\x00\x00\x1d\x00\x20"
    out += generate_x25519_public_key()
    out += b"\x00\x2d\x00\x02\x01\x01\x00\x2b\x00\x0b\x0a"
    add_grease(out, greases, 6)
    out += b"\x03\x04\x03\x03\x03\x02\x03\x01\x00\x1b\x00\x03\x02\x00\x02"
    add_grease(out, greases, 3)
    out += b"\x00\x01\x00\x00\x15"

    padding_length = FAKETLS_CLIENT_HELLO_LEN - 2 - len(out)
    add_u16(out, padding_length)
    out += b"\x00" * padding_length

    if len(out) != FAKETLS_CLIENT_HELLO_LEN:
        raise ProtocolError(f"Bad FakeTLS ClientHello length: {len(out)}")

    digest = hmac.new(secret, bytes(out), hashlib.sha256).digest()
    timestamp = int(time.time())
    digest_tail = struct.unpack("<I", digest[28:32])[0]
    client_random = digest[:28] + struct.pack("<I", digest_tail ^ timestamp)
    out[random_offset : random_offset + 32] = client_random
    return bytes(out), client_random


def validate_faketls_server_response(secret: bytes, client_random: bytes, response: bytes) -> None:
    if len(response) < 43:
        raise ProtocolError("Short FakeTLS server response")
    server_random = response[11:43]
    zeroed = bytearray(response)
    zeroed[11:43] = b"\x00" * 32
    expected = hmac.new(secret, client_random + bytes(zeroed), hashlib.sha256).digest()
    if not hmac.compare_digest(server_random, expected):
        raise ProtocolError("FakeTLS secret not recognized")
