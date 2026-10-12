"""Generate a private CA + server certificate (+ optional client certs) for MQTT over TLS.

    python tools/generate_certs.py --host 192.168.1.100 --host my-server.local --client robot01

Writes into infra/certs/: ca.crt/ca.key, server.crt/server.key, <client>.crt/<client>.key
Copy ca.crt (and robot01.crt/.key for mutual TLS) to the Raspberry Pi.
Requires:  pip install cryptography
"""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

OUT = Path(__file__).resolve().parent.parent / "infra" / "certs"


def _key():
    return ec.generate_private_key(ec.SECP256R1())


def _write(name: str, key, cert):
    (OUT / f"{name}.key").write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                                        serialization.PrivateFormat.PKCS8,
                                                        serialization.NoEncryption()))
    (OUT / f"{name}.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print("wrote", OUT / f"{name}.crt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", action="append", default=[], help="server DNS name or IP (repeatable)")
    ap.add_argument("--client", action="append", default=[], help="client cert CN, e.g. robot01 (repeatable)")
    ap.add_argument("--days", type=int, default=825)
    a = ap.parse_args()
    hosts = a.host or ["localhost", "127.0.0.1"]
    OUT.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)

    ca_key = _key()
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Inspection Robot CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now)
          .not_valid_after(now + dt.timedelta(days=3650))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .sign(ca_key, hashes.SHA256()))
    _write("ca", ca_key, ca)

    def leaf(cn: str, server: bool):
        key = _key()
        b = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)]))
             .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
             .not_valid_before(now).not_valid_after(now + dt.timedelta(days=a.days))
             .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
             .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH if server
                                                   else ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False))
        if server:
            sans = []
            for h in hosts:
                try:
                    sans.append(x509.IPAddress(ipaddress.ip_address(h)))
                except ValueError:
                    sans.append(x509.DNSName(h))
            b = b.add_extension(x509.SubjectAlternativeName(sans), critical=False)
        return key, b.sign(ca_key, hashes.SHA256())

    _write("server", *leaf(hosts[0], True))
    for c in a.client:
        _write(c, *leaf(c, False))
    print("\nNext: enable the 'listener 8883' block in infra/mosquitto/config/mosquitto.conf")


if __name__ == "__main__":
    main()
