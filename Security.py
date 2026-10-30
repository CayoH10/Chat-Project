import os
import ssl
import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding

PASTA_SEGURANCA = Path(__file__).resolve().parent
ARQUIVO_CERTIFICADO = PASTA_SEGURANCA / "servidor_cert.pem"
ARQUIVO_CHAVE_PRIVADA = PASTA_SEGURANCA / "servidor_chave.pem"

def gerar_certificado_servidor():
    if ARQUIVO_CERTIFICADO.exists() and ARQUIVO_CHAVE_PRIVADA.exists():
        return
    chave = rsa.generate_private_key(
        public_exponent=65537,
        key_size=3072
    )

    nome = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost")
    ])

    agora = datetime.now(timezone.utc)

    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(minutes=5))
        .not_valid_after(agora + timedelta(minutes=365))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1"))
            ]),
            critical=False
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True
        )
        .sign(chave, hashes.SHA256())
    )

    ARQUIVO_CHAVE_PRIVADA.write_bytes(
        chave.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
    )

    ARQUIVO_CERTIFICADO.write_bytes(
        certificado.public_bytes(Encoding.PEM)
    )

    print("Certificado de desenvolvimento criado.")

def criar_contexto_servidor():
    gerar_certificado_servidor()

    contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexto.minimum_version = ssl.TLSVersion.TLSv1_3

    contexto.load_cert_chain(
        certfile=str(ARQUIVO_CERTIFICADO),
        keyfile=str(ARQUIVO_CHAVE_PRIVADA)
    )
    return contexto

def criar_contexto_cliente():
    if not ARQUIVO_CERTIFICADO.exists():
        raise FileNotFoundError(
            "Certificado ausente. Copie servidor_cert.pem"
            "do servidor para a pasta do cliente."
        )
    contexto = ssl.create_default_context(
        ssl.Purpose.SERVER_AUTH,
        cafile=str(ARQUIVO_CERTIFICADO)
    )
    contexto.minimum_version = ssl.TLSVersion.TLSv1_3
    return contexto

def proteger_socket_cliente(sock):
    contexto = criar_contexto_cliente()

    return contexto.wrap_socket(
        sock,
        server_hostname="localhost"
    )

def proteger_socket_servidor(sock, contexto):

    return contexto.wrap_socket(
        sock,
        server_side=True
    )