import unicodedata


def normalize(s: str) -> str:
    """Minuscules sans accents. Même règle que le pipeline (colonne person.search_text)."""
    s = unicodedata.normalize("NFKD", s.replace("œ", "oe").replace("æ", "ae").replace("Œ", "Oe").replace("Æ", "Ae"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()
