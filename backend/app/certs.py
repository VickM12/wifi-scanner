from __future__ import annotations

import datetime
import shutil
import subprocess
from pathlib import Path


CERT_DIR = Path(__file__).resolve().parents[1] / "certs"
CERT_FILE = CERT_DIR / "radar.crt"
KEY_FILE = CERT_DIR / "radar.key"


def ensure_tls(ips: list[str]) -> tuple[Path, Path] | None:
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    if CERT_FILE.is_file() and KEY_FILE.is_file():
        return CERT_FILE, KEY_FILE
    names = ["localhost", "wifi-radar.local", *ips]
    if _write_with_cryptography(names, ips) or _write_with_openssl(names, ips):
        return CERT_FILE, KEY_FILE
    return None


def _write_with_cryptography(names: list[str], ips: list[str]) -> bool:
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except Exception:
        return False
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    san = [x509.DNSName(name) for name in names if not name.replace(".", "").isdigit()]
    for ip in ips + ["127.0.0.1"]:
        try:
            san.append(x509.IPAddress(__import__("ipaddress").ip_address(ip)))
        except ValueError:
            continue
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "wifi-radar")]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "wifi-radar")]))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(san), critical=False)
        .sign(key, hashes.SHA256())
    )
    KEY_FILE.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return True


def _write_with_openssl(names: list[str], ips: list[str]) -> bool:
    openssl = shutil.which("openssl")
    if not openssl:
        git = Path(r"C:\Program Files\Git\usr\bin\openssl.exe")
        openssl = str(git) if git.is_file() else None
    if not openssl:
        return False
    cfg = CERT_DIR / "san.cnf"
    alt = [f"DNS.{i}={name}" for i, name in enumerate(names, start=1) if not name.replace(".", "").isdigit()]
    alt += [f"IP.{i}={ip}" for i, ip in enumerate(["127.0.0.1", *ips], start=1)]
    cfg.write_text(
        "[req]\ndistinguished_name=req\nx509_extensions=v3\n[req_distinguished_name]\n[v3]\n"
        "subjectAltName=" + ",".join(part.split("=", 1)[1] and f"{part.split('=')[0].split('.')[0]}:{part.split('=', 1)[1]}" for part in alt)
        + "\n",
        encoding="utf-8",
    )
    # Rebuild a cleaner openssl config
    dns = [n for n in names if not n.replace(".", "").isdigit()]
    lines = ["[req]", "distinguished_name=req", "x509_extensions=v3", "[req_distinguished_name]", "[v3]", "subjectAltName=@alt", "[alt]"]
    for i, name in enumerate(dns, start=1):
        lines.append(f"DNS.{i}={name}")
    for i, ip in enumerate(["127.0.0.1", *ips], start=1):
        lines.append(f"IP.{i}={ip}")
    cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        subprocess.run(
            [
                openssl, "req", "-x509", "-newkey", "rsa:2048", "-sha256", "-days", "825",
                "-nodes", "-keyout", str(KEY_FILE), "-out", str(CERT_FILE),
                "-subj", "/CN=wifi-radar", "-config", str(cfg),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return CERT_FILE.is_file() and KEY_FILE.is_file()
