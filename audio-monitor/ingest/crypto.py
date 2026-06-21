"""RSA key management + hybrid (RSA-OAEP + AES-GCM) decryption.

Кроссплатформенно: только `cryptography`, без нативных зависимостей.
Формат зашифрованного файла (.enc), который шлёт клиент:
    [4 bytes BE: len(edek)] [edek] [12 bytes nonce] [AES-GCM ciphertext+tag]
"""
import os
import struct

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Ключи кладём рядом с данными (монтируемый volume), путь настраивается env-ом.
KEYS_DIR = os.environ.get("KEYS_DIR", os.path.join(os.path.dirname(__file__), "data"))
PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, "private_key.pem")
PUBLIC_KEY_PATH = os.path.join(KEYS_DIR, "public_key.pem")


def get_or_generate_keys():
    os.makedirs(KEYS_DIR, exist_ok=True)
    if os.path.exists(PRIVATE_KEY_PATH) and os.path.exists(PUBLIC_KEY_PATH):
        with open(PRIVATE_KEY_PATH, "r", encoding="utf-8") as f:
            priv_pem = f.read()
        with open(PUBLIC_KEY_PATH, "r", encoding="utf-8") as f:
            pub_pem = f.read()
        return priv_pem, pub_pem

    print("Generating new RSA key pair...")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    with open(PRIVATE_KEY_PATH, "w", encoding="utf-8") as f:
        f.write(priv_pem)
    with open(PUBLIC_KEY_PATH, "w", encoding="utf-8") as f:
        f.write(pub_pem)
    return priv_pem, pub_pem


def load_private_key(private_key_pem: str):
    return serialization.load_pem_private_key(private_key_pem.encode(), password=None)


def decrypt_token_rsa(private_key, encrypted_base64: str) -> str:
    import base64
    encrypted = base64.b64decode(encrypted_base64)
    decrypted = private_key.decrypt(
        encrypted,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(), label=None),
    )
    return decrypted.decode("utf-8")


def decrypt_enc_bytes(data: bytes, private_key) -> bytes:
    """Расшифровать содержимое .enc (в памяти) → сырой PCM."""
    offset = 0
    dek_len = struct.unpack(">I", data[offset:offset + 4])[0]
    offset += 4
    encrypted_dek = data[offset:offset + dek_len]
    offset += dek_len
    nonce = data[offset:offset + 12]
    offset += 12
    ciphertext = data[offset:]

    dek = private_key.decrypt(
        encrypted_dek,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(), label=None),
    )
    return AESGCM(dek).decrypt(nonce, ciphertext, None)
