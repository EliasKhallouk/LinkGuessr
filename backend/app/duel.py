"""Jetons des liens de duel « Qui est caché ? » : l'énigme partagée sans révéler la réponse.

Le lien /defi?jeu=qui&t=<jeton> porte toute l'énigme (chemin, position cachée, niveau, époque) et le
résultat de l'ami, chiffrés en AES-GCM avec une clé connue de la seule API (DUEL_KEY). Rien n'est stocké :
le jeton suffit. AES-GCM authentifie aussi le contenu : un jeton modifié est refusé.

Format avant chiffrement (octets) : version, position cachée, niveau, époque, essais, trouvé, puis les
numéros des QID du chemin en entiers variables (7 bits par octet). Jeton : base64url(nonce ‖ chiffré ‖ tag).
"""
import base64
import os

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # dépendance absente : liens de duel désactivés, mais l'API démarre
    AESGCM = None
    InvalidTag = ValueError

VERSION = 1
CONTEXT = b"linkguessr-duel-qui"  # données associées : un jeton d'un autre usage ne passe pas


class InvalidToken(ValueError):
    pass


def _b64decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def load_key(value: str) -> bytes | None:
    """DUEL_KEY : 32 octets en base64url (générés par `python -m app.duel`). Vide : liens de duel désactivés."""
    if not value or AESGCM is None:
        return None
    key = _b64decode(value.strip())
    if len(key) != 32:
        raise ValueError("DUEL_KEY doit faire 32 octets (base64url)")
    return key


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        byte, n = n & 0x7F, n >> 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _read_varints(data: bytes) -> list[int]:
    values, n, shift = [], 0, 0
    for byte in data:
        n |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            values.append(n)
            n, shift = 0, 0
    if shift:
        raise InvalidToken("entier tronqué")
    return values


def encode(key: bytes, chain: list[str], masked: int, level: int, era: int, tries: int, found: bool) -> str:
    plain = bytes([VERSION, masked, level, era, tries, int(found)]) + b"".join(_varint(int(q[1:])) for q in chain)
    nonce = os.urandom(12)
    token = nonce + AESGCM(key).encrypt(nonce, plain, CONTEXT)
    return base64.urlsafe_b64encode(token).rstrip(b"=").decode()


def decode(key: bytes, token: str) -> dict:
    try:
        raw = _b64decode(token)
        plain = AESGCM(key).decrypt(raw[:12], raw[12:], CONTEXT)
    except (ValueError, InvalidTag) as e:
        raise InvalidToken("jeton illisible ou modifié") from e
    if len(plain) < 6 or plain[0] != VERSION:
        raise InvalidToken("version inconnue")
    _, masked, level, era, tries, found = plain[:6]
    return {"chain": [f"Q{n}" for n in _read_varints(plain[6:])], "masked": masked, "level": level, "era": era,
            "tries": tries, "found": bool(found)}


if __name__ == "__main__":
    # Nouvelle clé, à mettre dans /srv/linkguessr/.env : DUEL_KEY=...
    print(base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode())
