"""Grille du guide (lab/annotation/guide.md), identique à backend/app/annotation.py : à modifier aux deux endroits."""

FAMILIES = {
    "Personnel": ["famille", "couple", "proches"],
    "Travail": ["formation", "collaboration", "hierarchie"],
    "Conflit": ["competition", "lutte", "critique"],
    "Par les œuvres": ["sujet", "materiau"],
    "Mention": ["source", "comparaison", "co_mention"],
    "Inclassable": ["inclassable"],
}
LABELS = [l for ls in FAMILIES.values() for l in ls]
FAMILY_OF = {l: fam for fam, ls in FAMILIES.items() for l in ls}
COTOYES = ["non", "incertain", "oui"]  # dans cet ordre : « incertain » est entre les deux (κ pondéré)
