"""Filtre des pseudos : insultes et injures courantes (français, anglais), y compris déguisées.

On normalise (minuscules, accents retirés, chiffres et symboles « leet » remplacés, lettres
répétées réduites à une seule, séparateurs supprimés) puis on cherche des racines interdites.
Le filtre reste volontairement simple : il bloque l'essentiel sans prétendre être exhaustif.
"""
import re
import unicodedata

LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "@": "a", "$": "s", "€": "e",
                      "!": "i", "|": "i", "+": "t"})

# Racines (après normalisation). Choisies pour éviter les faux positifs sur des prénoms courants.
BANNED = {
    # français
    "connard", "connasse", "conasse", "salope", "salaud", "encule", "enculer", "pute", "putain", "batard", "batar",
    "pede", "tapette", "gouine", "negre", "bougnoul", "youpin", "bicot", "nique", "niquer", "ntm", "fdp", "tg",
    "pd", "merde", "couille", "bite", "chatte", "branleur", "branleuse", "abruti", "debile", "nazi",
    "hitler", "pucelle", "suceur", "suceuse", "trouduc", "grosporc", "tafiole", "zgeg",
    # anglais
    "fuck", "shit", "bitch", "cunt", "dick", "pussy", "asshole", "bastard", "whore", "slut", "nigger", "nigga",
    "faggot", "retard", "rape", "porn", "cock", "wanker", "twat",
}
# Racines trop courtes pour être cherchées à l'intérieur d'un mot : seulement en mot entier.
WHOLE_WORD = {"tg", "pd", "ntm", "fdp", "bite", "cock", "dick", "nique", "pute", "pede"}
# Mots légitimes qui contiennent une racine interdite (« problème de Scunthorpe »).
ALLOWED = {"scunthorpe", "dickens", "cocktail", "cockpit", "peacock", "shitake", "bitencourt"}


def _single(s: str) -> str:
    """Lettres répétées réduites à une seule : « fuuuck » -> « fuck », « connard » -> « conard »."""
    return re.sub(r"(.)\1+", r"\1", s)


def normalize(text: str) -> str:
    s = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in s if not unicodedata.combining(c)).translate(LEET)


def is_offensive(text: str) -> bool:
    words = [w for w in re.findall(r"[a-z]+", normalize(text)) if w not in ALLOWED]
    squashed = _single("".join(words))  # « c.o.n.n.a.r.d » -> « conard »
    single_words = {_single(w) for w in words}
    for root in BANNED:
        r = _single(root)
        if root in WHOLE_WORD:
            if r in single_words or squashed == r:
                return True
        elif r in squashed:
            return True
    return False
