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
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

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

def gerar_chaves_dh():

    chave_privada = x25519.X25519PrivateKey.generate()
    chave_publica = chave_privada.public_key()

    return chave_privada, chave_publica

def serializar_chave_publica(chave_publica):
    return chave_publica.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw)

def carregar_chave_publica(chave_bytes):
    return x25519.X25519PublicKey.from_public_bytes(chave_bytes)

def derivar_chave_sessao(chave_privada, chave_publica_remota, salt):

    segredo_compartilhado = chave_privada.exchange(chave_publica_remota)

    chave = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"chat-e2ee-aes-256"
    ).derive(segredo_compartilhado)

    return chave

def criptografar_mensagem(chave, mensagem):

    aes = AESGCM(chave)
    nonce = os.urandom(12)
    mensagem_bytes = mensagem.encode('utf-8')

    mensagem_cifrada = aes.encrypt(
        nonce,
        mensagem_bytes,
        None
    )
    return nonce, mensagem_cifrada

def descriptografar_mensagem(chave, nonce, mensagem_cifrada):

    aes = AESGCM(chave)

    mensagem_original = aes.decrypt(
        nonce,
        mensagem_cifrada,
        None
    )
    return mensagem_original.decode('utf-8')
