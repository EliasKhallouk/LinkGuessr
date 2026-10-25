import pytest

from app.moderation import is_offensive


@pytest.mark.parametrize("name", ["c0nn4rd", "S.A.L.O.P.E", "FuuuuCK", "p d", "Grosse pute", "connaaaard", "N1gg@", "fdp 75"])
def test_bloque(name):
    assert is_offensive(name)


@pytest.mark.parametrize("name", ["Elias", "Pierre", "Dickens", "Cocktail", "Bitencourt", "Batman", "Tgv92", "Ludivine",
                                  "Marie-Curie", "Mongolfière", "Scunthorpe"])
def test_laisse_passer(name):
    assert not is_offensive(name)
