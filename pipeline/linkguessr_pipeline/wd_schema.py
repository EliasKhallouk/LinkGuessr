"""Ce qu'on garde de Wikidata pour chaque personne, et comment on l'interprète.

Tous les identifiants ont été vérifiés (libellés fr) le 2026-10-25.
"""

# Faits datés sur une personne (une ligne par affirmation dans person_fact).
FACT_PROPS = {
    "P106": "occupation",
    "P101": "domaine d'activité",
    "P39": "fonction",
    "P102": "parti politique",
    "P54": "équipe de sport",
    "P413": "poste de jeu",
    "P641": "sport",
    "P118": "ligue ou coupe",
    "P69": "scolarité",
    "P108": "employeur",
    "P463": "membre de",
    "P166": "distinction",
    "P1411": "nommé pour",
    "P800": "œuvre notable",
    "P136": "genre",
    "P1303": "instrument",
    "P264": "label",
    "P135": "mouvement",
    "P140": "religion",
    "P1412": "langues parlées",
    "P27": "nationalité",
    "P551": "résidence",
    "P937": "lieu de travail",
    "P119": "lieu de sépulture",
    "P509": "cause de la mort",
    "P1344": "participant à",
    "P241": "corps militaire",
    "P410": "grade militaire",
    "P607": "conflit",
    "P97": "titre de noblesse",
    "P53": "famille noble",
}

# Qualificatifs entités utiles à résoudre (ex. circonscription d'un député).
QUALIFIER_PROPS = {"P768", "P4100", "P642", "P1027", "P1686", "P3831", "P1350"}

# Relations directes entre personnes. inverse : propriété équivalente vue depuis l'autre personne.
RELATION_PROPS = {
    "P22": {"label": "père", "family": "famille", "inverse": "P40"},
    "P25": {"label": "mère", "family": "famille", "inverse": "P40"},
    "P8810": {"label": "parent", "family": "famille", "inverse": "P40"},
    "P40": {"label": "enfant", "family": "famille", "inverse": "P8810"},
    "P26": {"label": "conjoint", "family": "couple", "symmetric": True},
    "P451": {"label": "partenaire de vie", "family": "couple", "symmetric": True},
    "P3373": {"label": "frère ou sœur", "family": "famille", "symmetric": True},
    "P1038": {"label": "membre de la famille", "family": "famille", "symmetric": True},
    "P3448": {"label": "beau-parent", "family": "famille"},
    "P1290": {"label": "parrain ou marraine", "family": "famille"},
    "P1066": {"label": "élève de", "family": "transmission", "inverse": "P802"},
    "P802": {"label": "élève", "family": "transmission", "inverse": "P1066"},
    "P184": {"label": "directeur de thèse", "family": "transmission", "inverse": "P185"},
    "P185": {"label": "doctorant", "family": "transmission", "inverse": "P184"},
    "P737": {"label": "influencé par", "family": "influence"},
    "P1327": {"label": "partenaire professionnel ou sportif", "family": "collaboration", "symmetric": True},
    "P3342": {"label": "personne clé", "family": "autre"},
}
# Successions dans une fonction : qualificatifs de P39 (fonction).
SUCCESSION_QUALIFIERS = {"P1365": "prédécesseur", "P1366": "successeur"}

# Identifiants externes affichés sur la fiche.
EXTERNAL_IDS = {"P345": "imdb", "P2397": "youtube", "P2003": "instagram", "P2002": "x", "P856": "site"}

# Champs de la fiche à valeur unique.
GENDERS = {"Q6581097": "homme", "Q6581072": "femme", "Q1097630": "intersexe",
           "Q1052281": "femme trans", "Q2449503": "homme trans", "Q48270": "non-binaire"}

# Domaines : professions « racines ». Le domaine d'une profession est celui de la racine
# la plus proche en remontant « sous-classe de » (P279).
DOMAINS = {
    "politique": {"Q82955", "Q372436", "Q193391"},
    "militaire": {"Q47064", "Q189290"},
    "sport": {"Q2066131", "Q41583", "Q202648"},
    "musique": {"Q639669", "Q177220", "Q36834", "Q130857", "Q753110"},
    "cinéma et télévision": {"Q33999", "Q2526255", "Q3282637", "Q28389", "Q947873", "Q245068", "Q1414443"},
    "littérature": {"Q36180", "Q49757", "Q6625963", "Q482980", "Q11774202"},
    "arts": {"Q483501", "Q1028181", "Q1281618", "Q33231", "Q42973", "Q15296811", "Q3501317",
             "Q5716684", "Q4610556"},
    "sciences": {"Q901", "Q1650915", "Q81096", "Q170790", "Q169470", "Q593644", "Q864503",
                 "Q39631", "Q14467526"},
    "sciences humaines": {"Q201788", "Q4964182", "Q188094"},
    "affaires": {"Q43845", "Q131524", "Q12362622"},
    "médias": {"Q1930187", "Q17125263", "Q2722764"},
    "religion": {"Q250867", "Q1234713", "Q2259532", "Q611644"},
    "droit": {"Q40348", "Q16533"},
    "noblesse": {"Q116", "Q2478141"},
    "éducation": {"Q37226", "Q1622272"},
}
ANCHOR_TO_DOMAIN = {q: d for d, qs in DOMAINS.items() for q in qs}
# Indices d'un domaine : départagent les domaines déjà trouvés via les professions,
# ou servent de domaine si aucune profession n'est classable.
DOMAIN_SIGNALS = {"P102": "politique", "P54": "sport", "P641": "sport", "P118": "sport",
                  "P1303": "musique", "P264": "musique", "P241": "militaire", "P410": "militaire",
                  "P97": "noblesse"}

# Propriétés gardées pour les entités de référence (lieux, professions, organisations...).
REF_CLAIMS = {"P31", "P279", "P625", "P17", "P131"}
