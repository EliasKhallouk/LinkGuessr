import requests
from urllib.parse import unquote, urlparse
from functools import lru_cache

# Shared session with proper User-Agent to avoid 403 from Wikimedia
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "LinkGuessr/1.0 (https://github.com/EliasKhallouk/LinkGuessr; contact@example.com) Python/requests"
})


def get_wikipedia_title(url):
    """Extrait le titre de la page à partir de l'URL Wikipédia"""
    path = urlparse(url).path
    # ex: '/wiki/Prenom_Nom' -> 'Prenom_Nom'
    return unquote(path.split('/')[-1])


@lru_cache(maxsize=1024)
def get_wikidata_id(title, lang='fr'):
    """Récupère l'identifiant Wikidata (QID) depuis le titre Wikipédia.

    Mise en cache pour éviter les appels répétés au même titre.
    """
    endpoint = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "pageprops",
        "format": "json"
    }
    r = _SESSION.get(endpoint, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None
    page = next(iter(pages.values()))
    return page.get("pageprops", {}).get("wikibase_item")


@lru_cache(maxsize=1024)
def is_human(qid):
    """Vérifie si l'entité Wikidata est de type humain (Q5).

    Mise en cache pour éviter de retélécharger les mêmes entités.
    Retourne True/False.
    """
    url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
    r = _SESSION.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    entity = data.get("entities", {}).get(qid)
    if not entity:
        return False
    claims = entity.get("claims", {})
    for claim in claims.get("P31", []):  # P31 = instance of
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if value.get("id") == "Q5":
            return True
    return False


def detect_wikipedia_entity_type(url):
    """Renvoie True si la page Wikipédia représente une PERSONNE, False sinon.

    En cas d'erreur, lève l'exception afin que l'appelant puisse décider (utile
    pour les traitements concurrents).
    """
    lang = urlparse(url).netloc.split('.')[0]  # ex: fr.wikipedia.org -> fr
    title = get_wikipedia_title(url)
    qid = get_wikidata_id(title, lang)
    if not qid:
        return False
    return is_human(qid)
