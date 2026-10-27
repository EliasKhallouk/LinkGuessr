import base64
import os

import pytest

from app import duel

KEY = os.urandom(32)
CHAIN = ["Q21621995", "Q517", "Q7186"]


def test_aller_retour():
    t = duel.encode(KEY, CHAIN, 1, 2, 0, 3, True)
    assert duel.decode(KEY, t) == {"chain": CHAIN, "masked": 1, "level": 2, "era": 0, "tries": 3, "found": True}


def test_le_jeton_ne_revele_pas_le_chemin():
    t = duel.encode(KEY, CHAIN, 1, 0, 0, 1, False)
    assert "517" not in t and "Q" not in base64.urlsafe_b64decode(t + "=" * (-len(t) % 4)).decode("latin-1")
    assert duel.encode(KEY, CHAIN, 1, 0, 0, 1, False) != t  # nonce aléatoire : deux liens différents


def test_jeton_modifie_refuse():
    t = duel.encode(KEY, CHAIN, 1, 0, 0, 1, False)
    altered = t[:20] + ("A" if t[20] != "A" else "B") + t[21:]
    with pytest.raises(duel.InvalidToken):
        duel.decode(KEY, altered)


@pytest.mark.parametrize("bad", ["", "abc", "!!!", "A" * 80])
def test_jeton_illisible_refuse(bad):
    with pytest.raises(duel.InvalidToken):
        duel.decode(KEY, bad)


def test_autre_cle_refusee():
    t = duel.encode(KEY, CHAIN, 1, 0, 0, 1, False)
    with pytest.raises(duel.InvalidToken):
        duel.decode(os.urandom(32), t)


def test_cle():
    assert duel.load_key("") is None
    assert duel.load_key(base64.urlsafe_b64encode(KEY).rstrip(b"=").decode()) == KEY
    with pytest.raises(ValueError):
        duel.load_key(base64.urlsafe_b64encode(b"court").decode())


def test_jeton_court():
    long_chain = [f"Q{100_000_000 + i}" for i in range(8)]
    assert len(duel.encode(KEY, long_chain, 3, 4, 2, 4, True)) < 100
