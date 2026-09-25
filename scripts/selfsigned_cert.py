# SPDX-License-Identifier: Apache-2.0
"""``make tls-selfsigned``: a self-signed certificate for local HTTPS tests (spec 013, FR-013-04).

Writes ``certs/dev-cert.pem`` and ``certs/dev-key.pem`` (git-ignored) for ``localhost``,
``127.0.0.1`` and ``::1`` with the ``cryptography`` package that already ships with the
project's dependencies, so no OpenSSL binary is needed. **Never use these files for a real
event**: browsers will warn, and rightly so. Production gets a certificate from your IT
department (``TLS_CERT_FILE`` / ``TLS_KEY_FILE``) or from Let's Encrypt through the Compose
``tls`` profile (``docs/deploy/production.md``).
"""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

DEFAULT_DIR = Path("certs")
DEFAULT_HOSTNAMES = ("localhost",)
DEFAULT_IPS = ("127.0.0.1", "::1")
DEFAULT_DAYS = 825  # the maximum lifetime browsers accept for a publicly trusted leaf


def generate_selfsigned(
    cert_path: Path,
    key_path: Path,
    *,
    hostnames: Sequence[str] = DEFAULT_HOSTNAMES,
    ips: Sequence[str] = DEFAULT_IPS,
    days: int = DEFAULT_DAYS,
) -> tuple[Path, Path]:
    """Write a self-signed EC P-256 certificate and its key; return the two paths.

    The key file is created with mode ``0600`` (no effect on Windows). Subject Alternative
    Names cover every hostname and IP, which is what browsers and ``httpx`` check.
    """
    if not hostnames:
        raise ValueError("at least one hostname is required")
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostnames[0])])
    now = dt.datetime.now(dt.UTC)
    san = x509.SubjectAlternativeName(
        [
            *(x509.DNSName(host) for host in hostnames),
            *(x509.IPAddress(ipaddress.ip_address(ip)) for ip in ips),
        ]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))  # tolerate clock skew
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(key_pem)
    if os.name == "posix":
        os.chmod(key_path, 0o600)  # O_TRUNC on an existing file keeps its old mode
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="selfsigned_cert",
        description="Self-signed development certificate for Lenguaraz (never for production).",
    )
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="output folder (certs/)")
    parser.add_argument(
        "--hostname",
        action="append",
        dest="hostnames",
        metavar="NAME",
        help="DNS name to include (repeatable; default: localhost)",
    )
    parser.add_argument(
        "--ip",
        action="append",
        dest="ips",
        metavar="ADDR",
        help="IP address to include (repeatable; default: 127.0.0.1 and ::1)",
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="validity in days (825)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cert, key = generate_selfsigned(
        args.dir / "dev-cert.pem",
        args.dir / "dev-key.pem",
        hostnames=tuple(args.hostnames or DEFAULT_HOSTNAMES),
        ips=tuple(args.ips or DEFAULT_IPS),
        days=args.days,
    )
    print(f"wrote {cert} and {key} (self-signed, {args.days} days; never for production)")
    print("Try it:")
    print(f"  TLS_CERT_FILE={cert.as_posix()} TLS_KEY_FILE={key.as_posix()} \\")
    print("  ENGINE=fake uv run lenguaraz serve --host 127.0.0.1 --port 8443")
    print('  curl -k https://127.0.0.1:8443/healthz     # expect "tls": true')
    return 0


if __name__ == "__main__":
    sys.exit(main())
