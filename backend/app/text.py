import re
import unicodedata


def normalize(s: str) -> str:
    """Minuscules sans accents. Même règle que le pipeline (colonne person.search_text)."""
    s = unicodedata.normalize("NFKD", s.replace("œ", "oe").replace("æ", "ae").replace("Œ", "Oe").replace("Æ", "Ae"))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


SENTENCE_START = re.compile(r"^[A-ZÀ-ÖØ-Þ«\"“(\[]")
SENTENCE_END = re.compile(r"[.!?…»\"”)\]]$")


def whole_words(snippet: str | None) -> str | None:
    """Extrait d'article coupé par une fenêtre de caractères (« … n, il rejoint le Paris Saint-Germain ») : s'il ne
    commence pas comme une phrase, son premier mot peut être tronqué, on le retire ; de même pour le dernier mot
    s'il ne finit pas comme une phrase. L'affichage marque ensuite les coupures par « … »."""
    if not snippet:
        return snippet
    out = snippet.strip()
    if not SENTENCE_START.match(out):
        out = re.sub(r"^\S*\s*", "", out, count=1).lstrip(",;:.) ")
    if out and not SENTENCE_END.search(out):
        out = re.sub(r"\s*\S*$", "", out, count=1).rstrip(",;:( ")
    return out or None
