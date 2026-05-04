import requests
from urllib.parse import unquote, urlparse
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple
import time
import threading

# Shared session with proper User-Agent to avoid 403 from Wikimedia
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

# Rate limiting
_LAST_REQUEST_TIME = {"time": 0.0}
_REQUEST_LOCK = threading.Lock()

def _rate_limit():
    """Minimum 200ms between API calls"""
    with _REQUEST_LOCK:
        elapsed = time.time() - _LAST_REQUEST_TIME["time"]
        if elapsed < 0.2:
            time.sleep(0.2 - elapsed)
        _LAST_REQUEST_TIME["time"] = time.time()


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
    _rate_limit()
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
    _rate_limit()
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


# ==========================
#   Classification métier
# ==========================

@lru_cache(maxsize=4096)
def fetch_entity(qid: str) -> Optional[Dict]:
    """Télécharge l'entité Wikidata en JSON via Special:EntityData.

    Retourne le dict de l'entité (clé qid dans entities) ou None en cas d'erreur.
    """
    try:
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
        r = _SESSION.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("entities", {}).get(qid)
    except Exception:
        return None


def _pref_label_from_entity(entity: Dict, langs: Tuple[str, ...] = ("fr", "en")) -> Optional[str]:
    """Retourne un label priorisant fr puis en, sinon n'importe lequel."""
    if not entity:
        return None
    labels = entity.get("labels", {})
    for lg in langs:
        if lg in labels and "value" in labels[lg]:
            return labels[lg]["value"]
    # fallback arbitraire
    if labels:
        any_label = next(iter(labels.values()))
        return any_label.get("value")
    return None


@lru_cache(maxsize=4096)
def get_label_for_qid(qid: str, langs: Tuple[str, ...] = ("fr", "en")) -> Optional[str]:
    entity = fetch_entity(qid)
    return _pref_label_from_entity(entity, langs)


def _extract_claim_ids(entity: Dict, pid: str) -> List[str]:
    """Extrait la liste des identifiants Qxxx pour une propriété donnée (pid)."""
    out: List[str] = []
    if not entity:
        return out
    for claim in entity.get("claims", {}).get(pid, []):
        mainsnak = claim.get("mainsnak", {})
        datavalue = mainsnak.get("datavalue", {})
        value = datavalue.get("value")
        if isinstance(value, dict) and value.get("id"):
            out.append(value["id"])
    return out


CATEGORY_DEFS: Dict[str, Dict[str, Set[str]]] = {
    # 1) Divertissement (Acteur/Actrice, Chanteur/Musicien, Humoriste, Réalisateur, Influenceur/YouTuber, Animateur TV/Radio)
    "divertissement": {
        "anchors": {
            "Q33999",   # actor
            "Q177220",  # singer
            "Q639669",  # musician
            "Q10800557",# comedian
            "Q2526255", # film director
            "Q3282637", # film producer
            "Q947873",  # television presenter
            "Q131524",  # radio personality
            "Q17125263",# youtuber
            "Q983314",  # vlogger (approx)
        },
        "keywords": {
            "acteur", "actrice", "actor", "actress", "chanteur", "chanteuse", "singer",
            "musicien", "musicienne", "musician", "humoriste", "comedian", "stand-up",
            "réalisateur", "réalisatrice", "director", "producer", "producteur", "productrice",
            "influenceur", "influenceuse", "youtuber", "youtubeur", "youtubeuse", "videaste", "vidéaste",
            "animateur", "animatrice", "presenter", "tv host", "radio host"
        },
    },
    # 2) Politique et société (Politicien, Chef d’État, Militant/Activiste, Journaliste, Philosophe, Économiste)
    "politique_societe": {
        "anchors": {
            "Q82955",   # politician
            "Q30461",   # statesperson
            "Q372436",  # officeholder
            "Q173517",  # activist
            "Q1930187", # journalist
            "Q496418",  # philosopher
            "Q188094",  # economist
        },
        "keywords": {
            "politique", "politicien", "politician", "homme d'État", "femme d'État", "président",
            "militant", "activiste", "activist", "journaliste", "journalist", "reporter", "presenter",
            "philosophe", "philosopher", "économiste", "economist"
        },
    },
    # 3) Sciences et savoir (Scientifique, Inventeur, Médecin, Chercheur, Professeur/Enseignant)
    "sciences_savoir": {
        "anchors": {
            "Q901",     # scientist
            "Q2037",    # inventor
            "Q39631",   # physician
            "Q15978631",# surgeon
            "Q1650915", # researcher
            "Q121594",  # professor
            "Q37226",   # teacher
        },
        "keywords": {
            "scientifique", "scientist", "inventeur", "inventrice", "inventor",
            "médecin", "doctor", "physician", "chirurgien", "surgeon",
            "chercheur", "chercheuse", "researcher", "professeur", "enseignant", "enseignante", "teacher"
        },
    },
    # 4) Entrepreneuriat (Entrepreneur, PDG/Fondateur, Investisseur, Économiste)
    "entrepreneuriat": {
        "anchors": {
            "Q1762553", # entrepreneur
            "Q484876",  # businessperson
            "Q5003584", # CEO
            "Q16979650",# founder
            "Q41506",   # investor
            "Q1189840", # venture capitalist
            "Q188094",  # economist
        },
        "keywords": {
            "entrepreneur", "entrepreneuse", "fondateur", "fondatrice", "founder", "co-founder", "pdg", "ceo",
            "investisseur", "investisseuse", "investor", "économiste", "economist"
        },
    },
    # 5) Sport (Sportif, Entraîneur, Arbitre, Champion olympique)
    "sport": {
        "anchors": {
            "Q115sport13337",# sportsperson
            "Q2066131", # athlete
            "Q937857",  # coach
            "Q2736",    # referee
            "Q1341837", # Olympic athlete
        },
        "keywords": {
            "sportif", "sportive", "athlète", "athlete", "coach", "entraîneur", "entraineur",
            "manager", "arbitre", "referee", "champion olympique", "olympic champion"
        },
    },
}


def _labels_for_qids(qids: Set[str]) -> List[str]:
    labels: List[str] = []
    for q in qids:
        lab = get_label_for_qid(q)
        if lab:
            labels.append(lab)
    return labels


def _map_labels_to_categories(labels: List[str]) -> Set[str]:
    """Déduit les catégories générales via mots-clés sur les labels de professions DIRECTES."""
    cats: Set[str] = set()
    for lbl in labels:
        low = lbl.lower()
        for cat, defn in CATEGORY_DEFS.items():
            if any(kw in low for kw in defn.get("keywords", set())):
                cats.add(cat)
    return cats


def _anchors_for_category(cat: str) -> Set[str]:
    return CATEGORY_DEFS.get(cat, {}).get("anchors", set())

IT_FIELD_ANCHORS: Set[str] = set()


def _traverse_subclasses_collect_qids(start_qid: str, max_depth: int = 5) -> Set[str]:
    """Explore la hiérarchie P279 (subclass of) depuis un QID et collecte les QID visités."""
    visited: Set[str] = set()
    frontier: List[Tuple[str, int]] = [(start_qid, 0)]
    while frontier:
        qid, depth = frontier.pop(0)
        if qid in visited or depth > max_depth:
            continue
        visited.add(qid)
        ent = fetch_entity(qid)
        if not ent:
            continue
        for sup_id in _extract_claim_ids(ent, "P279"):
            if sup_id not in visited:
                frontier.append((sup_id, depth + 1))
    return visited


def _map_qids_to_categories(visited_qids: Set[str]) -> Set[str]:
    cats: Set[str] = set()
    for cat, defn in CATEGORY_DEFS.items():
        anchors = defn.get("anchors", set())
        if any(a in visited_qids for a in anchors):
            cats.add(cat)
    return cats


def _get_field_of_work_qids(qid: str) -> Set[str]:
    ent = fetch_entity(qid)
    return set(_extract_claim_ids(ent, "P101")) if ent else set()


def _get_net_worth_amount(qid: str) -> Optional[float]:
    return None


def _get_person_label(qid: str) -> Optional[str]:
    ent = fetch_entity(qid)
    return _pref_label_from_entity(ent)


def _get_profession_qids_for_person(qid: str) -> List[str]:
    ent = fetch_entity(qid)
    return _extract_claim_ids(ent, "P106") if ent else []


def _labels_for_professions(qids: List[str]) -> List[str]:
    labels: List[str] = []
    for q in qids:
        lab = get_label_for_qid(q)
        if lab:
            labels.append(lab)
    return labels


def classify_person(url: str) -> Optional[Dict[str, List[str]]]:
    """Classifie une personne Wikipédia par catégories générales.

    Entrée: URL Wikipédia (fr/en/...). Utilise API Wikipédia pour récupérer QID,
    puis Special:EntityData pour extraire professions (P106) et remonter P279.

    Sortie: dict avec clés:
      - name: libellé Wikidata de la personne (fr/en)
      - professions: labels des professions directes (P106)
      - categorie_generale: catégories générales déduites (politique, artiste, ...)

    Retourne None si l'URL n'est pas une personne (Q5 manquant) ou si QID introuvable.
    """
    try:
        lang = urlparse(url).netloc.split('.')[0]
        title = get_wikipedia_title(url)
        qid = get_wikidata_id(title, lang)
        if not qid:
            return None

        # S'assure que c'est bien un humain
        if not is_human(qid):
            return None

        person_label = _get_person_label(qid) or title.replace('_', ' ')
        prof_qids = _get_profession_qids_for_person(qid)

        professions_labels = _labels_for_professions(prof_qids)

        categories: Set[str] = set()
        # Déterminer les catégories sur chaque profession via P279 et QIDs d'ancrage
        all_qids: Set[str] = set()
        for pq in prof_qids:
            visited = _traverse_subclasses_collect_qids(pq)
            visited.add(pq)  # inclure la profession elle-même
            all_qids |= visited
        categories = _map_qids_to_categories(all_qids)

        # fallback conservateur: mapper uniquement les labels des professions DIRECTES
        if not categories and professions_labels:
            categories = _map_labels_to_categories(professions_labels)

        # Note: la catégorie "entrepreneuriat" couvre Entrepreneur/PDG/Fondateur/Investisseur.

        return {
            "name": person_label,
            "professions": sorted(set(professions_labels)),
            "categorie_generale": sorted(categories)
        }
    except requests.Timeout:
        return None
    except Exception:
        # Robuste: on ne propage pas pour ne pas casser l'appelant
        return None



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

