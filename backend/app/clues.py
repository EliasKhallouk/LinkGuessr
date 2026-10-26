"""« Qui est caché ? » : phrases à trou qui relient la personne cachée à ses voisins."""
import re

HOLE = "▢▢▢"
# Mots trop courants pour être masqués seuls (« Louis de Funès » : on masque « Louis » et « Funès », pas « de »).
PARTICLES = {"de", "du", "des", "la", "le", "les", "von", "van", "der", "den", "di", "da", "del", "dos", "el", "al",
             "bin", "ben", "ibn", "saint", "sainte", "ier", "ii", "iii", "iv", "jr", "sr"}


def mask(text: str, name: str) -> str:
    """Remplace dans `text` chaque mot du nom par un trou ; les mots voisins masqués ne font qu'un trou."""
    base = re.sub(r"\s*\(.*\)$", "", name)
    words = {w for w in re.split(r"[\s\-'’.]+", base) if len(w) >= 3 and w.lower() not in PARTICLES}
    if not words:
        return text
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, sorted(words, key=len, reverse=True))) + r")\b", re.IGNORECASE)
    return re.sub(rf"{HOLE}(?:[\s\-]+(?:(?:de|du|des|la|le|d'|l')\s*)?{HOLE})+", HOLE, pattern.sub(HOLE, text))


def relation_sentence(rel: dict, answer: dict, other: dict) -> str:
    """Même tournure que l'affichage du chemin (PathView) : « élève de » se lit depuis la source,
    « père », « successeur »… depuis la cible. La personne cachée devient un trou."""
    source, target = (answer, other) if rel["source_id"] == answer["id"] else (other, answer)
    name = lambda p: HOLE if p is answer else p["name"]  # noqa: E731
    if re.search(r" (de|par)$", rel["label"]):
        sentence = f"{name(source)} est {rel['label']} {name(target)}"
    else:
        sentence = f"{name(target)} est {rel['label']} de {name(source)}"
    if rel.get("context"):
        sentence += f" ({rel['context']}{', ' + str(rel['start_year']) if rel.get('start_year') else ''})"
    return sentence


def clues(hidden_hops: dict, answer: dict, persons: dict) -> list[dict]:
    """Pour chaque lien de la personne cachée : la relation Wikidata et la meilleure phrase, nom masqué."""
    out = []
    for key, hop in hidden_hops.items():
        other = persons[next(q for q in key.split("-") if q != answer["qid"])]
        rel = hop["relations"][0] if hop["relations"] else None
        texts = sorted(hop["text"], key=lambda r: (-r["in_lead"], -r["mentions"]))
        snippet = next((r["snippet"] for r in texts if r.get("snippet")), None)
        out.append({
            "with": other["qid"],
            "relation": relation_sentence(rel, answer, other) if rel else None,
            "snippet": mask(snippet, answer["name"]) if snippet else None,
        })
    return out
