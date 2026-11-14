# Lab : proposition de plan

Document de travail à valider, rédigé le 30 octobre 2026 à partir du code du dépôt (commit `75614f8`) et des
données du dump `20261001`. Rien n'est encore codé. Les chiffres marqués « ≈ » sont déduits du code et pas
mesurés : ils sont à confirmer au début de la v1 (voir l'étape 0).

Sommaire : 1. Données · 2. Analyses candidates · 3. Feuille de route · 4. Architecture · 5. Page d'analyse ·
6. Rigueur et éthique · 7. Mes questions · Annexe : références.

---

## 1. Inventaire des données

### 1.1 Ce qu'on a déjà

Tout sort de `pipeline/data/work/<DUMP_DATE>/final/*.parquet` (mêmes tables que Postgres, schéma
`pipeline/sql/graph_schema.sql`). Le Lab lira ces fichiers sur le PC, **jamais Postgres sur la VM**.

| Donnée | Table, colonnes | Volume | Utile pour |
|---|---|---|---|
| Personnes | `person` : 765 000 lignes (P31 = Q5 et article frwiki) | — | toutes |
| Genre | `person.gender` (7 valeurs Wikidata) | — | analyse 6 |
| Dates | `birth_year`, `death_year` avec précision (jour → siècle) | — | époques (analyse 5), contrôles |
| Lieux, pays | `birth_place`, `birth_country`, `death_*`, `citizenships` (QID → `ref`, coordonnées) | — | contrôles, cartes |
| Domaines | `domains` (15 domaines maison, via la hiérarchie P279 des professions), `primary_domain` | — | **définition des ponts** |
| Professions | `occupations` (QID) | — | sous-domaines, typologie |
| Notoriété | `pageviews_12m`, `pageviews_monthly` (12 mois), `sitelinks`, `article_len`, `popularity` | — | analyse 2, contrôles |
| Texte | `lead`, `infobox`, `categories`, `n_chars`, `n_sections` | — | contrôles (longueur de l'article) |
| Métriques | `degree`, `in_links`, `out_links`, `pagerank`, `community` (Leiden, modularité) | — | analyses 2 et 3 |
| Liens textuels | `text_link` : A cite B, orienté. `mentions`, `first_pos`, `in_lead`, `in_infobox`, `sections` (titres), `snippet` | ≈ 5 à 7 M | typage, robustesse |
| Relations Wikidata | `relation` : `prop`, `family` (famille, couple, transmission, influence, collaboration, succession, autre), `label`, `context_qid`, dates | à mesurer | **étiquettes de départ** du typage |
| Faits datés | `fact` : 31 propriétés (P39 fonction, P102 parti, P54 équipe, P69 scolarité, P108 employeur, P166 distinction, P463 membre de, P607 conflit, P135 mouvement, P264 label…) avec début et fin | à mesurer | **affiliations partagées** (coéquipiers, même gouvernement…) |
| Arêtes | `edge` non orientées : `kinds` (bits texte a→b, b→a, Wikidata), `mentions`, `weight` | ≈ 5 M (graphe CSR ≈ 45 Mo d'après `tools/surprises.py`), degré moyen ≈ 13 | toutes les distances |
| Joueurs : Relier | `app.game_event` (VM) : chemin complet joué, départ, cible, plus court chemin, indices, niveau | selon l'audience | analyse 7 |
| Joueurs : Combien ? | `app.game_event` : paire, vraie distance, estimation, temps de réponse, niveau | selon l'audience | analyse 7 |
| Joueurs : Explorer | `app.path_request` : paires demandées (sans session) | selon l'audience | analyse 7 (curiosité) |

### 1.2 Limites des données existantes qui pèsent sur la recherche

1. **Une seule phrase par lien.** `snippet` est la phrase de la *première* mention. Si Zidane cite Materazzi trois
   fois, on n'a que la première phrase, pas forcément la plus parlante. Pour le typage, c'est la principale limite.
   Les liens présents seulement dans l'infobox ou une légende d'image ont une phrase pauvre ou vide.
2. **Pas de type pour les liens textuels.** C'est le manque central de la problématique (voir 1.3).
3. **Les œuvres ne sont pas des nœuds.** Deux acteurs du même film ne sont reliés que si un article cite l'autre.
   Les propriétés Wikidata de collaboration sont portées par les œuvres (P161 distribution, P57 réalisateur,
   P86 compositeur, P175 interprète), et le pipeline ne les récupère pas.
4. **Les groupes ne sont pas des personnes.** Les Beatles ou Daft Punk ne sont pas des nœuds : les liens entre
   membres passent par leurs biographies seulement.
5. **Pas d'histoire.** Un seul instantané ; pas de date de création des liens. L'évolution du réseau demanderait
   d'anciens dumps (archive.org) ou l'historique complet (des téraoctets, hors de portée).
6. **Un domaine par profession racine.** 15 domaines, attribués via P279. Les personnes sans profession classable
   n'ont pas de domaine (part à mesurer) : elles seront exclues des calculs de ponts, et on le dira.
7. **Le graphe des jeux est non orienté.** Pour les asymétries (qui cite qui), il faut repartir de `text_link`.

### 1.3 Ce qui manque, analyse par analyse

| Manque | Analyses | Comment l'obtenir | Coût |
|---|---|---|---|
| Type de chaque lien textuel | 4, 5, 8 | Classifieur sur `snippet` + `sections`, entraîné par supervision distante (1.4) et un jeu d'or annoté à la main | gros (v2) |
| Affiliations partagées (coéquipiers, même parti, même gouvernement…) | 4 | Jointure de `fact` sur lui-même pour chaque arête existante : même `value_qid`, périodes qui se chevauchent | quelques minutes, à ajouter au Lab |
| Collaborations sur des œuvres | 4 | Nouvelle étape du pipeline : œuvres Wikidata avec ≥ 2 personnes du graphe (P161, P57, P58, P86, P175, P50) | une nuit de requêtes, optionnel |
| Distances de l'échantillon, centralités approchées | 1, 2 | Calcul hors ligne (parcours en largeur depuis un échantillon de sources) | 15 min à 1 h |
| Réseaux aléatoires de référence | 1, 3, 4 | Permutations d'arêtes qui conservent les degrés (et le mélange entre domaines) | minutes par réseau |
| Signe des liens (positif, négatif) | 8 | Classifieur dédié, jeu d'or séparé | v3 ou après |
| Données des joueurs | 7 | Export SQL agrégé depuis la VM (une requête légère, hors des heures de pointe) | négligeable |

### 1.4 Les étiquettes « gratuites » pour entraîner le classifieur

Une arête qui porte aussi une relation Wikidata ou une affiliation partagée fournit une étiquette probable pour sa
phrase. C'est de la supervision distante (Mintz et al., 2009) : bruitée, car la phrase peut parler d'autre chose.

| Source | Type proposé |
|---|---|
| P22, P25, P40, P8810, P3373, P1038, P3448 | famille |
| P26, P451 | couple |
| P1066, P802, P184, P185 | transmission |
| P737 | influence |
| P1327 | collaboration |
| P1365, P1366 (successions dans une fonction) | politique et institutions |
| Même P54 (équipe) avec des périodes qui se chevauchent | sport (coéquipiers) |
| Même P102 (parti) ou même P39 (fonction) avec chevauchement | politique et institutions |
| Même P108 (employeur), même P264 (label), même P135 (mouvement) | collaboration (faible) |

Il n'existe pas d'étiquette gratuite pour **médias et représentation** (un acteur qui joue Napoléon), **rivalité**
ni **mention contextuelle**. Ces classes dépendent entièrement du jeu d'or annoté.

---

## 2. Analyses candidates

Huit analyses, de la plus simple à la plus ambitieuse. Les coûts supposent ton PC (8 Go de RAM). L'étape 0 de la
v1 mesure le temps d'un parcours en largeur complet ; d'ici là, j'estime 0,2 à 1 s par source selon la
bibliothèque (≈ 765 000 nœuds, ≈ 5 M arêtes). Règle commune : **on ne garde jamais une matrice de distances**
(2 000 sources × 765 000 personnes = 1,5 Go même en octets). Chaque lot de sources met à jour des histogrammes
et des sommes par personne, puis la mémoire est libérée.

### Analyse 1. « Le monde est-il petit ? »

- **Question** : combien de liens séparent deux personnalités prises au hasard ?
- **Méthode** : parcours en largeur depuis S = 2 000 sources tirées uniformément dans la composante géante. On en
  tire la distribution des distances, la distance moyenne ℓ, la médiane et le diamètre effectif (90e centile).
  Intervalles de confiance à 95 % par bootstrap sur les sources. Diamètre exact par la méthode du double
  balayage puis iFUB, plus les deux personnes les plus éloignées. Calcul pour les 3 modes du site : tous les
  liens, liens forts, Wikidata seule.
- **Référence** : même ℓ dans (a) un réseau aléatoire de même taille et densité (Erdős–Rényi), (b) un réseau qui
  conserve les degrés (permutations de Maslov–Sneppen, 10 × E échanges). Le message : « plus petit que le hasard,
  ou pas ? ». Le coefficient de regroupement (clustering) complète la définition de Watts–Strogatz.
- **Données** : `edge`, `person` (pour les tranches par époque ou domaine). Déjà là.
- **Coût** : 2 000 parcours ≈ 10 à 30 min ; 3 réseaux aléatoires × 500 sources ≈ 30 min. Moins de 1 Go de RAM.
- **Potentiel waouh** : fort. « Entre Cléopâtre et Mbappé : 4 liens. » Chiffre clé, histogramme, les deux
  personnes les plus éloignées de Wikipédia FR, bouton « tire deux personnes au hasard » vers Explorer.
- **Lien avec la problématique** : c'est le constat de départ. Le mode « Wikidata seule » montre déjà que le monde
  rétrécit ou non selon les liens qu'on garde : c'est la question de la v2, posée dès la v1.
- **Original ou réplication** : **réplication** (Milgram 1967, Watts et Strogatz 1998, Backstrom et al. 2012 sur
  Facebook, réseaux de biographies Wikipédia chez Aragón et al. 2012). Original : la comparaison entre les trois
  modes de liens et les tranches par époque.

### Analyse 2. « Napoléon est-il le centre de la mémoire française ? »

- **Question** : qui est au centre du réseau, et est-ce la même chose qu'être célèbre ?
- **Méthode** : classements par degré, liens entrants, PageRank (déjà calculés), centralité harmonique estimée
  (gratuite : les 2 000 parcours de l'analyse 1 donnent pour chaque personne sa distance moyenne à l'échantillon,
  Boldi et Vigna 2014) et intermédiarité approchée (échantillonnage de Brandes ou KADABRA, ≈ 1 000 sources).
  Comparaison avec les pages vues : nuage de points centralité contre notoriété, avec les « centraux mais
  oubliés » et les « célèbres mais isolés ». Expérience « un monde sans Napoléon » : on retire une personne et on
  mesure l'allongement des chemins sur le même échantillon de sources (comparaison appariée, intervalle serré).
- **Référence** : stabilité des rangs d'une mesure à l'autre (corrélation de Kendall), rangs dans le réseau qui
  conserve les degrés (le PageRank dépend surtout du degré : ce qui reste après permutation est la position).
  Pour « un monde sans X », référence = retrait d'une personne tirée au hasard de même degré.
- **Données** : déjà là. Photos Commons avec crédits pour le podium.
- **Coût** : intermédiarité ≈ 30 min à 1 h ; « monde sans X » pour les 50 premiers × 500 sources = 25 000
  parcours ≈ 2 à 7 h (une nuit).
- **Potentiel waouh** : très fort, c'est le titre d'appel. Résultat probable et contre-intuitif : retirer
  Napoléon allonge à peine les chemins. Le réseau n'a pas de centre unique, ce qui amène la v2 : ce ne sont pas les
  personnes qui font le petit monde, ce sont les types de liens.
- **Lien avec la problématique** : contrefactuel sur les nœuds, version simple du $\Delta\ell_\tau$ sur les arêtes.
- **Original ou réplication** : **réplication** pour les classements (Aragón et al. 2012, Eom et al. 2015 sur
  24 éditions, Skiena et Ward 2013). Original : le contrefactuel « monde sans X » sur un échantillon apparié,
  et l'écart centralité – pages vues sur frwiki.

### Analyse 3. « Quels milieux se parlent ? »

- **Question** : les sportifs parlent-ils aux politiques, les scientifiques aux artistes ?
- **Méthode** : matrice de mélange 15 × 15 des domaines (part des arêtes entre chaque paire de domaines),
  assortativité de Newman (2003), part des arêtes qui sont des ponts selon trois définitions : (a) domaines
  principaux différents, (b) ensembles de domaines disjoints (plus strict, écarte les profils multiples comme
  Schwarzenegger), (c) communautés Leiden différentes. Comparaison des communautés Leiden avec les domaines, les
  pays et les siècles (information mutuelle normalisée).
- **Référence** : matrice attendue dans le réseau qui conserve les degrés ; on publie le rapport observé /
  attendu, pas les comptes bruts (sinon le sport, très nombreux, écrase tout).
- **Données** : déjà là.
- **Coût** : quelques minutes.
- **Potentiel waouh** : moyen à fort. Carte de chaleur ou diagramme en cordes ; « la politique parle à tout le
  monde, le sport ne parle qu'au sport ».
- **Lien avec la problématique** : **indispensable**. Elle fixe la définition d'un pont et la matrice de mélange
  que le modèle nul de la v2 doit conserver.
- **Original ou réplication** : en partie réplication (assortativité, communautés). La comparaison des trois
  définitions de pont est le socle méthodologique de l'article.

### Analyse 4. « Qu'est-ce qui rend le monde petit ? » (problématique principale)

- **Question** : la famille, la politique, la collaboration, les médias ou les rivalités : quels liens
  fabriquent les raccourcis entre des mondes qui ne se croisent pas ?
- **Méthode**, avec un ensemble de types $T$ (multi-étiquettes : une arête peut en porter plusieurs) :
  1. **Enrichissement** $R(\tau) = P(\tau \mid \text{pont}) / P(\tau)$, pour chacune des trois définitions de pont.
     Intervalles par bootstrap **par personne** (les arêtes d'une même personne ne sont pas indépendantes).
     Version ajustée : régression logistique pont ~ type + log degré des deux bouts + écart d'années de naissance
     + notoriété, pour vérifier que l'effet ne vient pas du fait que les liens de famille touchent des gens
     très connus.
  2. **Contribution contrefactuelle** $\Delta\ell_\tau = \ell(G \setminus E_\tau) - \ell(G)$ sur le même
     échantillon de sources (apparié). Retirer des arêtes déconnecte des paires : on rapporte aussi l'efficacité
     globale (moyenne de $1/d$, définie même quand des paires sont déconnectées) et la part de paires perdues.
     On rapporte l'effet par arête, $\Delta\ell_\tau / |E_\tau|$, car les familles de liens n'ont pas la même taille.
  3. **Modèle nul principal** : réseau permuté qui conserve, pour chaque type, le degré de chaque personne et la
     matrice de mélange entre domaines (échange des extrémités seulement entre arêtes du même type dont les bouts
     échangés ont le même domaine). Il casse la position fine des arêtes (voisins communs, regroupement) mais garde
     leur quantité, leurs degrés et les domaines qu'elles relient. L'**excès de raccourci**
     $\Delta\ell_\tau(G) - \mathbb{E}[\Delta\ell_\tau(G_{\text{nul}})]$ mesure ce que la *place* des liens de type
     τ apporte, au-delà de leur nombre et des milieux qu'ils relient. Référence plus simple en complément : retrait
     de $|E_\tau|$ arêtes tirées au hasard.
  4. **Part des pas** : sur un plus court chemin tiré au hasard pour chaque paire échantillonnée, part des pas de
     type τ, comparée à la part de τ dans toutes les arêtes. Facile à expliquer : « les liens de famille font 3 %
     du réseau mais 9 % des pas sur les plus courts chemins » (chiffres fictifs).
  5. **Ponts locaux** (Granovetter 1973) : arêtes sans voisin commun, et leur portée (distance entre les deux bouts
     sans l'arête). Ce sont les raccourcis au sens strict ; on mesure la composition par type de ces arêtes.
  Les types n'agissent pas indépendamment : retirer famille et politique ensemble n'équivaut pas à la somme. On
  rapporte « τ retiré seul » et « τ seul conservé », et si le temps le permet une décomposition de Shapley sur
  les familles principales (au plus 6 familles, donc 64 sous-ensembles).
- **Données** : typage des liens (1.3, 1.4, et classifieur en v2). Avant le classifieur, une **version 0** est
  possible dès la fin de la v1 avec les seules arêtes étiquetées par Wikidata et les affiliations partagées.
- **Coût** : 500 sources par configuration. Pour 10 types : (1 graphe complet + 10 retraits + 10 types × 5
  réseaux nuls) × 500 parcours ≈ 30 000 parcours ≈ 2 à 8 h, une nuit. Génération des réseaux nuls (≈ 50 M échanges
  chacun, en numba) : environ 1 min chacun.
- **Potentiel waouh** : fort, si le résultat est net. Titres possibles : « Ce n'est pas Napoléon qui rend le monde
  petit, ce sont les mariages » ou « Les acteurs sont les raccourcis du temps ». On ne choisit le titre qu'après
  les résultats.
- **Original ou réplication** : **original**. La méthode de retrait d'arêtes par classe existe (Onnela et al. 2007
  pour les liens faibles et forts d'un réseau téléphonique), mais pas, à ma connaissance, la décomposition du
  petit monde par type sémantique de relation dans un réseau de biographies. Une revue bibliographique dédiée
  en début de v2 doit le confirmer.
- **Hypothèses à écrire avant de voir les résultats** (pré-enregistrement léger, daté, dans le dépôt) :
  H1, la famille et le couple sont enrichis parmi les ponts entre domaines ($R > 1$) ; H2, les liens « médias et
  représentation » ont le plus fort effet par arête sur les écarts d'époque ; H3, la collaboration est surtout
  interne aux domaines ($R < 1$) ; H4, l'excès de raccourci des liens politiques reste positif sous le modèle nul.

### Analyse 5. « Les raccourcis du temps »

- **Question** : combien de liens séparent le Moyen Âge d'aujourd'hui, et qui fait le pont entre les époques ?
- **Méthode** : distribution de l'écart d'années de naissance par arête ; asymétrie de citation (les modernes
  citent-ils plus les anciens que l'inverse, via `text_link` orienté) ; distance moyenne entre tranches de siècles
  (matrice siècle × siècle à partir des parcours de l'analyse 1, regroupés par siècle de la cible) ; personnes et
  types de liens qui portent les plus grands sauts dans le temps.
- **Référence** : réseau qui conserve les degrés et le mélange entre époques ; écart d'années attendu si les
  liens ignoraient le temps.
- **Données** : déjà là pour la partie descriptive ; le type « médias et représentation » demande le classifieur.
- **Coût** : faible, réutilise les parcours de l'analyse 1.
- **Potentiel waouh** : fort. « De Vercingétorix à Kylian Mbappé en 4 liens, grâce à un acteur ».
- **Lien avec la problématique** : déclinaison temporelle. On remplace « pont entre domaines » par « pont entre
  époques » dans $R(\tau)$.
- **Original ou réplication** : en partie original. La dimension temporelle des biographies a été étudiée
  (Schich et al. 2014 sur les naissances et décès ; Gergaud, Laouenan et Wasmer sur les personnalités
  historiques), mais pas, à ma connaissance, les liens comme raccourcis entre époques.

### Analyse 6. « Les femmes dans le réseau »

- **Question** : les femmes sont-elles reliées comme les hommes dans Wikipédia FR ?
- **Méthode** : part des femmes par domaine et par siècle ; part des liens reçus ; homophilie (assortativité de
  genre) ; asymétrie de citation (un article d'homme cite-t-il une femme aussi souvent que l'inverse) ; part des
  liens de famille et de couple parmi les liens vers des femmes ; position dans le réseau (centralité harmonique)
  à domaine, époque et notoriété égaux.
- **Référence** : réseau qui conserve les degrés, et comparaisons **à strates égales** (même domaine, même siècle),
  sinon on mesure surtout la composition historique de Wikipédia.
- **Données** : déjà là. Les liens de famille et couple viennent de Wikidata ; la mention « épouse de » dans le
  texte demande le classifieur.
- **Coût** : faible.
- **Potentiel waouh** : fort, mais sujet sensible : prudence dans les titres.
- **Lien avec la problématique** : secondaire. Si les liens de famille sont des ponts (H1) et touchent davantage
  les femmes, une partie de la visibilité des femmes passe par leurs liens familiaux.
- **Original ou réplication** : **réplication sur la Wikipédia FR** de Wagner et al. 2015 et 2016, et
  Graells-Garrido et al. 2015. À présenter comme telle, avec comparaison chiffrée aux résultats publiés.

### Analyse 7. « Les joueurs connaissent-ils le réseau ? »

- **Question** : quand tu devines une distance ou cherches un chemin, est-ce que tu raisonnes comme le réseau ?
- **Méthode** :
  - Combien ? : estimation contre vraie distance (biais moyen, surestimation des longues distances, effet de la
    notoriété et du domaine des deux personnes, temps de réponse).
  - Relier : allongement des chemins joués par rapport au plus court ; stratégie « monter vers un hub puis
    redescendre » (degré le long du chemin joué, West et Leskovec 2012) ; personnes par lesquelles les joueurs
    passent le plus, comparées aux personnes réellement centrales (analyse 2).
  - Explorer : quelles paires les gens demandent (domaines, époques), sans rien publier de nominatif.
- **Référence** : stratégie gloutonne simulée (aller toujours vers le voisin le plus proche de la cible, ou le
  plus connu) sur les mêmes paires. Les joueurs font-ils mieux qu'un algorithme simple ?
- **Données** : `app.game_event`, export agrégé (voir 6.4). Taille selon l'audience : à mesurer, c'est l'une de
  mes questions.
- **Coût** : négligeable.
- **Potentiel waouh** : fort, car les lecteurs sont les joueurs. « Tu surestimes la distance de 1,3 lien en
  moyenne ».
- **Lien avec la problématique** : indirect. On regarde si les raccourcis perçus sont les raccourcis réels.
- **Original ou réplication** : réplication de Wikispeedia (West et al. 2009, West et Leskovec 2012), mais avec un
  jeu de données francophone **inédit**. L'estimation de distances (Combien ?) n'a, à ma connaissance, pas
  d'équivalent publié : c'est un point fort pour l'article.

### Analyse 8 (plus tard). « Amis et ennemis »

- **Question** : l'ennemi de mon ennemi est-il mon ami dans Wikipédia ?
- **Méthode** : signer les liens (positif, négatif, neutre) par un classifieur dédié ; compter les triangles
  signés ; test de l'équilibre structural (Heider 1946, Cartwright et Harary 1956), par triangles et par
  frustration globale (Facchetti et al. 2011).
- **Référence** : mêmes triangles avec signes permutés au hasard (proportion de négatifs conservée).
- **Données** : classifieur de signe, jeu d'or séparé. La plupart des liens seront neutres ; peu de triangles
  entièrement signés.
- **Coût** : faible une fois les signes obtenus ; tout le coût est dans l'annotation.
- **Potentiel waouh** : très fort, et risque fort (voir 6.3 sur les personnes vivantes).
- **Lien avec la problématique** : la rivalité est un des types de la v2 ; ici on étudie sa structure.
- **Original ou réplication** : réplication de Leskovec et al. 2010 (réseaux signés en ligne), sur un réseau où le
  signe est extrait du texte : plus original.

### Tableau récapitulatif

| # | Analyse | Version | Données en plus | Calcul | Waouh | Problématique | Statut |
|---|---|---|---|---|---|---|---|
| 1 | Le monde est-il petit ? | v1 | aucune | 1 h | ★★★ | constat | réplication |
| 2 | Napoléon au centre ? | v1 | aucune | 1 nuit | ★★★ | contrefactuel sur les nœuds | réplication + original |
| 3 | Quels milieux se parlent ? | v1.5 | aucune | minutes | ★★ | socle (définition des ponts) | réplication |
| 4 | Qu'est-ce qui rend le monde petit ? | v2 | typage | 1 nuit par version | ★★★ | **cœur** | original |
| 5 | Les raccourcis du temps | v2 | typage (en partie) | faible | ★★★ | déclinaison | en partie original |
| 6 | Les femmes dans le réseau | v2 ou v3 | aucune | faible | ★★ | secondaire | réplication |
| 7 | Les joueurs connaissent-ils le réseau ? | v2 | export VM | négligeable | ★★★ | indirect | jeu de données inédit |
| 8 | Amis et ennemis | après v3 | signes | faible | ★★★ | piste secondaire | réplication + original |

---

## 3. Feuille de route

Les charges sont des estimations en jours de travail, à affiner après l'étape 0.

### Lab v1 : deux analyses publiées (≈ 8 à 12 jours)

0. **Étalonnage** (½ jour) : script qui mesure les vrais volumes (arêtes, liens textuels, part des phrases vides,
   relations par famille, personnes sans domaine, événements de jeu) et le temps d'un parcours en largeur avec
   igraph, scipy et networkit. Les chiffres « ≈ » de ce document sont remplacés par les vrais.
1. **Socle `lab/`** (2 jours) : chargement du graphe, échantillonnage reproductible, bootstrap, réseaux
   aléatoires, export JSON avec manifeste (section 4).
2. **Analyse 1** « Le monde est-il petit ? » (2 jours).
3. **Analyse 2** « Napoléon est-il le centre de la mémoire française ? » (2 jours, plus une nuit de calcul).
4. **Front** (3 à 4 jours) : page `/lab` (sommaire des analyses avec chiffre clé), gabarit `/lab/:slug`,
   graphiques, méthode dépliable, exemples cliquables, partage, image d'aperçu `type=lab` dans `api/og.js`,
   balises dans `middleware.js`, sitemap (`seo.py`), événements Umami, mises à jour de `docs/tracking.md`,
   `docs/liens.md`, de la page À propos et de CLAUDE.md.
5. **Relecture de rigueur** : chaque page passe la liste de contrôle de la section 6.1 avant publication.

Critère de sortie : deux pages en ligne, chiffres reproductibles par `uv run lab all` sur le dump `20261001`,
JSON horodatés et signés par le commit du code.

### Lab v2 : typage des liens et premiers résultats (≈ 20 à 30 jours)

1. **Revue de la littérature** (2 à 3 jours) sur la décomposition du petit monde par type de lien : confirmer
   l'originalité de l'analyse 4 avant d'y investir.
2. **Analyse 3** « Quels milieux se parlent ? » (fixe la définition des ponts).
3. **Version 0 de l'analyse 4** avec les seules étiquettes Wikidata et les affiliations partagées (1.4). On sait
   alors quelle part des arêtes est typée gratuitement et si les premières tendances sont nettes.
4. **Typologie et guide d'annotation** (1 jour) : environ 10 classes, avec définitions et exemples.
   Proposition : famille, couple, transmission, collaboration, sport, politique et institutions, rivalité et
   opposition, médias et représentation, influence et référence, mention contextuelle.
5. **Jeu d'or** (≈ 12 h d'annotation) : 1 500 phrases tirées par strates (domaines, types Wikidata, sections),
   dont 300 annotées par une deuxième personne pour l'accord inter-annotateurs (κ de Cohen, cible ≥ 0,7).
6. **Classifieur**, par paliers :
   - base : régression logistique sur n-grammes (vectorisation par hachage, RAM bornée) + titre de section +
     infobox + paire de domaines. Entraînement en minutes, prédiction des ≈ 6 M phrases en moins d'une heure ;
   - si la base est insuffisante sur les classes rares : CamemBERT ou un petit modèle d'encodage multilingue,
     affiné et appliqué sur un GPU gratuit (Colab ou Kaggle : les phrases sont publiques, il n'y a rien de
     personnel), ou sur ton PC par lots (≈ 15 à 40 h en CPU, à reprendre nuit après nuit) ;
   - précautions : les noms des deux personnes sont masqués dans la phrase (sinon le modèle apprend « Carla Bruni
     → couple ») ; découpage entraînement / test **par personne** pour éviter les fuites ; évaluation sur le jeu
     d'or uniquement (F1 par classe, matrice de confusion).
7. **Analyse 4 complète**, avec correction de l'erreur du classifieur : les proportions de types sont corrigées par
   la matrice de confusion du jeu d'or, et le bootstrap intègre l'incertitude du classifieur.
8. **Analyses 5 et 7**, et la 6 si le temps le permet.

Critère de sortie : une page publique sur la problématique principale, une note méthodologique interne de 10 à
15 pages qui sert de brouillon à l'article.

### Lab v3 : jeu de données et article (≈ 10 à 15 jours, plus la rédaction)

1. **Instantané de référence figé** : le dump utilisé dans l'article (proposition : celui de la v2) ne change
   plus. Le site continue ses mises à jour mensuelles ; l'article et le DOI pointent vers l'instantané.
2. **Jeu de données sur Zenodo, avec DOI** :

   | Fichier | Contenu | Licence |
   |---|---|---|
   | `persons.parquet` | QID, nom, dates, genre, domaines, pays, notoriété, métriques | CC0 (Wikidata, pages vues Wikimedia) ; le nom et la description viennent de Wikidata |
   | `edges.parquet` | arêtes non orientées, `kinds`, poids | CC0 pour la structure, avec citation de la source |
   | `text_links.parquet` | liens orientés, sections, **phrases de contexte** | **CC BY-SA 4.0**, attribution « contributeurs de Wikipédia », lien vers le dump |
   | `relations.parquet`, `facts.parquet` | relations et faits Wikidata | CC0 |
   | `edge_types.parquet` | types prédits, probabilités, version du modèle | CC BY-SA 4.0 par prudence (dérivés de phrases CC BY-SA), à trancher |
   | `gold_annotations.csv` | jeu d'or annoté, avec le guide | CC BY-SA 4.0 (contient les phrases) |
   | `README.md`, `datasheet.md`, `CITATION.cff` | documentation | CC BY 4.0 |

   Format Parquet (plus un extrait CSV pour la consultation), métadonnées Croissant si possible. Taille estimée :
   1 à 2 Go compressés, surtout les phrases. Pas de données de joueurs brutes, seulement des agrégats.
3. **Datasheet** sur le modèle de Gebru et al. (2021) : motivation, composition, collecte, prétraitement, usages
   prévus et déconseillés (pas de jugement sur des individus), diffusion, maintenance.
4. **Code** publié et archivé (Zenodo via GitHub, ou Software Heritage), avec la commande qui reproduit chaque
   figure de l'article.
5. **Article** : venues possibles, à choisir avec ton encadrant : Wiki Workshop (format court, le public le plus
   proche), ICWSM (avec le jeu de données), EPJ Data Science ou Applied Network Science (version longue), et en
   France MARAMI ou EGC.

---

## 4. Architecture technique

Principe : **tout est calculé sur le PC, rien sur la VM.** Le Lab produit des fichiers JSON statiques, versionnés
dans le dépôt et servis par Vercel avec le front. Les pages du Lab n'appellent pas l'API : les exemples sont
précalculés dans le JSON. Seul un clic vers Explorer ou un jeu touche l'API, comme aujourd'hui (avec le cache
Vercel devant).

### 4.1 Dossiers

```
lab/                                  nouveau projet uv, séparé du pipeline (dépendances plus lourdes)
  pyproject.toml, uv.lock             polars, numpy, scipy, igraph, numba, scikit-learn (+ networkit si Windows OK)
  README.md                           commandes, durées, ordre
  hypotheses/                         pré-enregistrements datés (H1 à H4…), jamais réécrits après coup
  annotation/
    guide.md                          guide d'annotation de la typologie
    gold_v1.csv                       jeu d'or (phrases, deux annotations, arbitrage)
  linkguessr_lab/
    cli.py                            `lab run <slug>`, `lab all`, `lab check`, `lab publish`
    common/
      data.py                         lecture des parquet finaux (colonnes utiles seulement, en mode paresseux)
      graph.py                        CSR, sous-graphes par mode ou par type d'arête
      sampling.py                     sources échantillonnées (graine fixée, stockée dans la sortie)
      bfs.py                          parcours par lots, accumulateurs (histogrammes, sommes par personne)
      nulls.py                        permutations : degrés ; degrés + mélange entre domaines ; par type (numba)
      stats.py                        bootstrap (par source, par personne), Benjamini–Hochberg
      export.py                       écriture JSON + manifeste, arrondis, contrôle de taille
    analyses/
      monde_petit.py                  analyse 1
      centres.py                      analyse 2
      milieux.py                      analyse 3
      raccourcis.py                   analyse 4
      ...
    typing/                           v2 : étiquettes distantes, entraînement, prédiction
  notebooks/                          exploration seulement ; aucun chiffre publié ne doit en sortir
pipeline/data/lab/<DUMP_DATE>/        résultats intermédiaires lourds (non versionnés, comme pipeline/data)
frontend/public/lab/
  index.json                          manifeste : analyses, version des données, chiffre clé, date
  <slug>/<DUMP_DATE>.json             une sortie par analyse et par version des données (archive)
frontend/src/lab/
  pages/<Slug>.jsx                    texte et mise en page de chaque analyse (le texte éditorial vit ici)
  components/                         KeyFigure, Method, Limits, ExampleLinks, LabChart…
```

Pourquoi garder les anciennes versions : une page peut citer « au 1er octobre 2026 », l'article pointe vers
une version précise, et on peut montrer l'évolution d'un mois sur l'autre. Taille visée : < 150 Ko par fichier
(compressé par Vercel), donc quelques Mo par an au plus.

### 4.2 Format d'une sortie

```json
{
  "schema": 1,
  "slug": "monde-petit",
  "data_version": "20261001",
  "generated_at": "2026-11-03T21:14:00Z",
  "code_version": "a1b2c3d",
  "params": { "mode": "all", "sources": 2000, "seed": 20261001, "bootstrap": 1000 },
  "n": { "persons": 765123, "edges": 4987654, "giant_component": 0.987 },
  "headline": { "value": 4.21, "ci95": [4.19, 4.23], "unit": "liens" },
  "flags": { "plus_petit_que_hasard": true },
  "figures": {
    "distance_hist": { "x": [1, 2, 3], "share": [0.0001, 0.004, 0.08], "ci95": [[0.0001, 0.0001], [0.0039, 0.0041], [0.079, 0.081]] },
    "by_mode": [{ "mode": "all", "mean": 4.21, "ci95": [4.19, 4.23] }]
  },
  "examples": [
    { "label": "Les deux personnes les plus éloignées", "from": "Q…", "to": "Q…", "length": 17, "path": ["Q…", "Q…"] }
  ],
  "people": { "Q517": { "name": "Napoléon Ier", "image": "…jpg" } }
}
```

Règles : chiffres arrondis à 3 ou 4 chiffres significatifs ; QID plutôt que noms dans les figures, avec un
dictionnaire `people` pour l'affichage ; toujours `data_version`, `code_version`, `params` et la graine ; aucune
donnée de joueur en dessous d'un seuil d'effectif (6.4). Les `flags` sont les affirmations dont dépend le texte
(« Napoléon est premier en PageRank ») : le texte de la page s'appuie sur eux, pas sur des chiffres écrits en dur.

### 4.3 Mise à jour mensuelle

```
lg graph                    (pipeline, existant)
uv run lab all --mensuel    analyses rapides (1, 2 sans la nuit « monde sans X », 3, 5, 6, 7) : ≈ 1 h
uv run lab check            compare avec la version précédente
uv run lab publish          copie les JSON dans frontend/public/lab/, met à jour index.json
git commit -m "Lab : données du 1er novembre 2026" && git push   → Vercel déploie
lg load                     (existant, indépendant)
```

- `lab check` signale tout `flag` qui change de valeur et tout chiffre clé qui bouge de plus de 5 % : le texte de
  la page doit alors être relu avant publication. La publication s'arrête tant que ce n'est pas fait.
- Les calculs lourds (contrefactuels, réseaux nuls, classifieur) ne tournent pas chaque mois. Ils sont refaits sur
  l'instantané de référence et quand le classifieur change.
- Les pages affichent la date des données ; un lien vers Explorer ouvre le graphe du mois en cours, qui peut
  différer un peu (un chemin peut avoir changé). Les chemins affichés dans la page restent ceux du JSON.

---

## 5. Format d'une page d'analyse

Adresses : `/lab` (sommaire) et `/lab/<slug>` en français sans accents : `/lab/monde-petit`,
`/lab/napoleon-centre`, `/lab/milieux`, `/lab/raccourcis`, `/lab/raccourcis-du-temps`, `/lab/femmes`,
`/lab/joueurs`.

### 5.1 Structure type

1. **Titre en question** et une phrase de réponse : « Napoléon est-il le centre de la mémoire française ? Non :
   le réseau tient sans lui. »
2. **Chiffre clé** en grand, avec son intervalle en petit et une phrase qui le traduit (« 4,2 liens en moyenne,
   entre 4,19 et 4,23 »).
3. **Graphique interactif principal** : une seule figure qui porte le message. Infobulles, choix d'un mode ou
   d'une tranche, texte alternatif et tableau de données accessible (`<details>` avec le tableau).
4. **À toi de jouer** : 3 à 5 exemples cliquables, précalculés (« Cléopâtre → Mbappé en 4 liens »), qui ouvrent
   Explorer avec la paire, plus un bouton vers le jeu le plus proche (Combien ? pour les distances, Relier pour
   les chemins). Photos Commons avec auteur et licence (`ImageCredit.jsx`).
5. **Explication** en 3 à 5 paragraphes, tutoiement, sans jargon. Un seul graphique secondaire au plus.
6. **Ce que ça ne dit pas** : les limites, visibles (pas cachées dans la méthode), en 3 ou 4 puces.
7. **Méthode** dépliable : données et version, définitions, modèle nul, taille d'échantillon et intervalles,
   robustesse (les résultats avec les liens forts seulement), lien vers le code, références de l'état de l'art.
   Pour une réplication : « ce résultat reproduit sur Wikipédia FR celui de … ; voici l'écart ».
8. **Partager** : bouton commun (`ShareButton`), image d'aperçu dédiée.
9. **Citer et télécharger** : le JSON de la page, une citation (BibTeX), plus tard le DOI du jeu de données.
10. **Crédits** : textes Wikipédia en français (CC BY-SA 4.0, contributeurs de Wikipédia), données Wikidata
    (CC0), pages vues Wikimedia (CC0), photos Wikimedia Commons (auteur et licence affichés). Toute phrase de
    Wikipédia citée dans une page renvoie à l'article.

Le sommaire `/lab` présente une carte par analyse (titre, chiffre clé, vignette), le lien vers « Méthode générale
et données » (une page qui regroupe les définitions communes et les limites de la section 6.2) et, plus tard, le
DOI.

### 5.2 Image de partage

Ajouter `type=lab&slug=…` à `api/og.js` : titre en question, chiffre clé, photo éventuelle (Napoléon pour
l'analyse 2), logo, « linkguessr.com/lab ». Les données viennent de `/lab/index.json` (statique, même domaine,
pas d'appel à la VM). `middleware.js` sert les balises d'aperçu de chaque `/lab/<slug>` à partir du même
manifeste. Lien partagé : `https://linkguessr.com/lab/monde-petit?utm_source=partage&utm_medium=copie&utm_campaign=lab`.

### 5.3 Bibliothèque de graphiques

**Recommandation : Observable Plot** (bibliothèque déclarative fondée sur D3, licence ISC), chargée seulement sur
les pages du Lab (`React.lazy`), sans toucher aux jeux qui gardent chart.js.

- Elle couvre nativement les figures du Lab : histogrammes avec intervalles de confiance, cartes de chaleur
  (matrice de mélange), nuages de points annotés (centralité contre notoriété), facettes (par époque, par mode),
  échelles logarithmiques, annotations de texte. Avec chart.js, il faudrait deux extensions (barres d'erreur,
  matrice) et beaucoup de code pour les annotations.
- Elle produit du SVG : texte net à toutes les tailles, lisible par les lecteurs d'écran, et exportable en image.
- Code court : une figure tient en une dizaine de lignes, facile à relire avec la méthode.
- Coût : ≈ 80 à 100 Ko compressés, sur les pages du Lab seulement.

Alternatives écartées : **chart.js** (déjà là, mais faible pour les intervalles et les matrices ; acceptable si
tu ne veux aucune dépendance de plus), **D3 brut** (trop de code pour chaque figure), **Plotly** (≈ 1 Mo, style
difficile à accorder au site), **ECharts** (lourd, rendu canvas). Pour un réseau dessiné, on garde vis-network,
déjà utilisé par Explorer.

---

## 6. Rigueur et éthique

### 6.1 Liste de contrôle avant chaque publication

- [ ] La question, la définition des objets (personne, lien, pont, distance) et la version des données sont écrites.
- [ ] Chaque chiffre a son intervalle de confiance ou son effectif.
- [ ] Il y a un modèle nul ou une référence, et le texte compare toujours à elle.
- [ ] Le résultat tient en mode « liens forts » et sans les sections de liste (« Voir aussi », « Filmographie »,
      « Distinctions »…). Sinon, le texte le dit.
- [ ] Les comparaisons multiples sont corrigées (Benjamini–Hochberg) quand on teste plusieurs types ou domaines.
- [ ] Réplication : l'article d'origine est cité et l'écart est commenté.
- [ ] Le texte ne dit pas plus que les chiffres : « dans Wikipédia FR », jamais « dans la société française ».
- [ ] `uv run lab run <slug>` reproduit le JSON publié à l'identique.
- [ ] Rien sur une personne vivante qui ressemble à un jugement (6.3).

### 6.2 Limites à expliquer, une fois sur la page de méthode générale et rappelées sur chaque page

- **Ce qu'est une « personnalité »** : un humain (P31 = Q5 dans Wikidata) qui a un article dans Wikipédia en
  français. Les personnages de fiction, les groupes et les familles en tant que telles ne sont pas des nœuds.
- **Biais de couverture** : Wikipédia FR reflète ce que ses contributeurs jugent notable (la France, les hommes,
  le sport, la politique et l'époque contemporaine y sont surreprésentés). Le Lab mesure la **mémoire
  encyclopédique francophone**, pas la société.
- **Ce qu'est un lien** : un lien interne dans le corps d'une biographie (hors notes et palettes) ou une relation
  Wikidata. Un lien n'est pas une relation réelle : il peut être anecdotique (« surnommé le nouveau Zidane »),
  contextuel (« sous le règne de Louis XIV ») ou une liste. Les articles longs citent plus : le degré reflète en
  partie l'attention des contributeurs.
- **Une phrase par lien** : la première mention seulement ; le typage peut s'y tromper.
- **Instantané** : un mois donné ; les liens n'ont pas de date.
- **Domaines** : taxonomie maison à 15 domaines, attribuée automatiquement ; une partie des personnes n'en a pas.
- **Classifieur** (v2) : taux d'erreur par classe affiché, et pris en compte dans les intervalles.

### 6.3 Éthique

- **Personnes vivantes** : pas de classement qui ressemble à un jugement (« le plus détesté ») ; le réseau signé
  (analyse 8) ne publie que des agrégats, et ses exemples nominatifs se limitent à des personnes mortes ou à des
  rivalités publiques citées avec la phrase de Wikipédia et le lien vers l'article.
- **Attributs sensibles** : aucune analyse sur la religion, la cause de la mort ou l'orientation, même si les
  données existent (`fact` contient P140 et P509). Le genre n'est analysé qu'en agrégat, avec les catégories
  Wikidata, et les effectifs faibles (personnes non binaires, trans) sont signalés comme trop petits pour conclure.
- **Pas de publicité, pas de compte, pas de cookie** : rien ne change avec le Lab.

### 6.4 Données des joueurs (analyse 7)

- Ces données existent déjà (`app.game_event`, chemins de Relier, estimations de Combien ?) et sont anonymes :
  identifiant de session aléatoire, aucun pseudo, aucune adresse IP.
- Export depuis la VM : une requête SQL agrégée, lancée à la main hors des heures de pointe, qui ne sort ni les
  identifiants de session ni les horodatages précis. Le calcul se fait sur le PC.
- Publication : agrégats seulement, aucune cellule de moins de 20 parties.
- La politique de confidentialité doit dire, avant toute publication, que des statistiques anonymes et agrégées
  des parties servent au Lab et à la recherche (une phrase à ajouter).

### 6.5 Reproductibilité

- Code versionné, dépendances verrouillées (`uv.lock`), graines fixées et écrites dans chaque sortie.
- Chaque JSON porte la date des données et le commit du code.
- Hypothèses de la v2 écrites et datées dans `lab/hypotheses/` avant le calcul. Une analyse non prévue est
  présentée comme exploratoire.
- Le jeu d'or et le guide d'annotation sont publiés avec le jeu de données.
- Les notebooks servent à explorer ; aucun chiffre publié n'en sort directement.

### 6.6 Suivi Umami (conforme à `docs/tracking.md`)

À ajouter à `tracking.md` **avant** le code, comme le veut la convention :

| Événement | Quand | Propriétés |
|---|---|---|
| `lab_lecture` | Une fois par visite de page, quand le lecteur a dépassé le graphique principal | `analyse` (slug), `source` |
| `lab_methode` | Ouverture de la méthode dépliable | `analyse`, `source` |
| `lab_exemple` | Clic sur un exemple ou sur le bouton vers un jeu | `analyse`, `source`, `cible` (`explorer`, `relier`, `combien`, `qui-est-cache`) |
| `partage_clic` | Existant | `jeu` = `lab` (nouvelle valeur), `analyse`, `source`, `methode` |

- Nouvelle valeur `utm_campaign=lab` pour les liens partagés depuis le Lab. L'analyse se lit dans l'adresse de la
  page d'arrivée, inutile de la mettre dans l'UTM.
- **Aucune personne** dans les événements : `lab_exemple` envoie la cible (un jeu), jamais le QID de l'exemple,
  comme pour les jeux (« pas de personnalité jouée »).
- Indicateurs à suivre : visites par page, taux de lecture (`lab_lecture` / visites), taux d'ouverture de la
  méthode, clics vers les jeux (le rôle de pont), et l'entonnoir `partage_clic` → visites `utm_campaign=lab` →
  `partie_debut`.
- `docs/liens.md` : ajouter `/lab/:slug` et le format du lien partagé.

---

## 7. Mes questions avant de commencer

1. **Chiffres réels** : je n'ai pas accès aux données d'ici (elles sont sur ton PC). Veux-tu lancer l'étape 0
   (un petit script que j'écrirai) ou me donner le nombre d'arêtes, de `text_link`, de `relation` par famille, la
   part de phrases vides et le nombre d'événements de Relier et de Combien ? dans `app.game_event` ?
2. **Ton PC** : combien de cœurs, quel système (Windows, d'après le pipeline) et un GPU ? Ça décide du
   classifieur et de networkit (à vérifier sous Windows).
3. **La thèse** : discipline visée (informatique, sociologie, humanités numériques), laboratoire ou encadrant
   pressenti, et échéance. Ça change le cadrage, les venues et l'ordre des priorités (analyse 4 d'abord, ou
   jeu de données d'abord).
4. **Code public** : le dépôt sera-t-il public (GitHub) ? Pour un article, le code doit l'être ; sinon je prévois
   un dépôt séparé pour `lab/` seulement. Quelle licence pour le code ?
5. **Annotation** : peux-tu y consacrer ≈ 12 heures, et as-tu une deuxième personne pour 300 phrases ? Acceptes-tu
   une pré-annotation par un modèle de langage, relue à la main (plus rapide, mais à déclarer dans la méthode) ?
6. **Typologie** : ma proposition à 10 classes (v2, étape 4) te convient-elle, ou as-tu déjà une typologie en tête
   (par exemple liée à ta problématique de thèse) ?
7. **Données des joueurs** : d'accord pour les utiliser dans le Lab, en agrégats, et pour ajouter la phrase
   correspondante à la politique de confidentialité ?
8. **Langue** : le Lab est-il en français seulement, ou bilingue comme le reste du site ? Le bilingue double la
   rédaction et la relecture de chaque page.
9. **Graphiques** : d'accord pour ajouter Observable Plot, ou préfères-tu rester sur chart.js ?
10. **Rédaction** : je rédige les textes des pages et tu les valides, ou l'inverse ?
11. **Mise à jour mensuelle** : est-elle déjà faite chaque mois à la main (`lg download` → `lg load`), et
    acceptes-tu qu'elle inclue `lab all --mensuel` puis un commit des JSON ?
12. **Analyse 8 (réseau signé)** : la garde-t-on dans la feuille de route publique, vu le risque sur les personnes
    vivantes, ou seulement pour l'article ?
13. **Collaborations sur des œuvres** (1.3) : vaut-il la peine d'ajouter cette étape au pipeline pour la v2 ? Elle
    donnerait des étiquettes pour le cinéma et la musique, aujourd'hui sans étiquette Wikidata.

---

## Annexe : références citées

- Aragón, Kaltenbrunner, Laniado, Volkovich (2012). *Biographical social networks on Wikipedia: a cross-cultural
  study of links that made history.* WikiSym.
- Backstrom, Boldi, Rosa, Ugander, Vigna (2012). *Four degrees of separation.* WebSci.
- Boldi, Vigna (2014). *Axioms for centrality.* Internet Mathematics.
- Borassi, Natale (2016). *KADABRA is an ADaptive Algorithm for Betweenness via Random Approximation.* ESA.
- Cartwright, Harary (1956). *Structural balance: a generalization of Heider's theory.* Psychological Review.
- Eom, Aragón, Laniado, Kaltenbrunner, Vigna, Shepelyansky (2015). *Interactions of cultures and top people of
  Wikipedia from ranking of 24 language editions.* PLoS ONE.
- Facchetti, Iacono, Altafini (2011). *Computing global structural balance in large-scale signed social
  networks.* PNAS.
- Gebru et al. (2021). *Datasheets for datasets.* Communications of the ACM.
- Graells-Garrido, Lalmas, Menczer (2015). *First women, second sex: gender bias in Wikipedia.* Hypertext.
- Granovetter (1973). *The strength of weak ties.* American Journal of Sociology.
- Heider (1946). *Attitudes and cognitive organization.* Journal of Psychology.
- Leskovec, Huttenlocher, Kleinberg (2010). *Signed networks in social media.* CHI.
- Martin et al. (2020). *CamemBERT: a tasty French language model.* ACL.
- Maslov, Sneppen (2002). *Specificity and stability in topology of protein networks.* Science.
- Milgram (1967). *The small world problem.* Psychology Today.
- Mintz, Bills, Snow, Jurafsky (2009). *Distant supervision for relation extraction without labeled data.* ACL.
- Newman (2003). *Mixing patterns in networks.* Physical Review E.
- Onnela et al. (2007). *Structure and tie strengths in mobile communication networks.* PNAS.
- Schich et al. (2014). *A network framework of cultural history.* Science.
- Skiena, Ward (2013). *Who's Bigger? Where Historical Figures Really Rank.* Cambridge University Press.
- Wagner, Garcia, Jadidi, Strohmaier (2015). *It's a man's Wikipedia? Assessing gender inequality in an online
  encyclopedia.* ICWSM.
- Wagner, Graells-Garrido, Garcia, Menczer (2016). *Women through the glass ceiling: gender asymmetries in
  Wikipedia.* EPJ Data Science.
- Watts, Strogatz (1998). *Collective dynamics of 'small-world' networks.* Nature.
- West, Pineau, Precup (2009). *Wikispeedia: an online game for inferring semantic distances between concepts.*
  IJCAI.
- West, Leskovec (2012). *Human wayfinding in information networks.* WWW.

Les références sont citées de mémoire : à vérifier une par une (titres, années, venues) avant de les reprendre
dans une page publique ou dans l'article. Le travail de Gergaud, Laouenan et Wasmer sur une base de personnalités
historiques est mentionné sans référence précise, à retrouver.
