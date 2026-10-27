# Mesure d'audience : paramètres UTM et événements

LinkGuessr mesure sa fréquentation avec Umami, hébergé sur la VM et relayé par Vercel sous
`linkguessr.com/umami`. Umami fonctionne sans cookie et respecte « Do Not Track ». Aucune donnée personnelle
n'est envoyée : pas d'identifiant de joueur, pas de personnalité jouée, pas de texte saisi.
Code : `frontend/src/lib/tracking.js`, `frontend/src/lib/share.js`, balise Umami dans `frontend/index.html`.

## Paramètres UTM

Règles :

- toujours en **minuscules**, mots séparés par des **tirets** (`defi-du-jour`), sans accent ni espace ;
- les trois paramètres `utm_source`, `utm_medium` et `utm_campaign`, dans cet ordre ;
- seulement les valeurs ci-dessous ; une nouvelle valeur s'ajoute d'abord ici.

| Paramètre | Valeurs | Sens |
|---|---|---|
| `utm_source` | `partage`, `duel` | Liens générés par le site : résultat partagé (défi du jour, chemin d'Explorer), invitation à un duel |
| | `reddit`, `discord`, `instagram`, `tiktok`, `x`, `facebook`, `whatsapp`, `newsletter`, `presse` | Liens posés à la main par l'équipe |
| `utm_medium` | `copie`, `webshare` | Liens du site : copié dans le presse-papiers, ou menu de partage natif (téléphone) |
| | `post`, `commentaire`, `bio`, `message`, `email`, `article` | Liens posés à la main |
| `utm_campaign` | `qui-est-cache`, `relier`, `combien`, `explorer`, `defi-du-jour` | Le jeu mis en avant (même nom que sa page) |
| | `lancement`, ou un nom court daté (`halloween-2026`) | Opérations ponctuelles |

Liens générés par le site :

| Lien | Exemple |
|---|---|
| Défi du jour | `https://linkguessr.com/jour/12?utm_source=partage&utm_medium=webshare&utm_campaign=defi-du-jour` |
| Duel Qui est caché ? | `https://linkguessr.com/defi?jeu=cache&…&utm_source=duel&utm_medium=copie&utm_campaign=qui-est-cache` |
| Duel Relier | `https://linkguessr.com/defi?jeu=relais&paire=Q1-Q2&score=3&utm_source=duel&utm_medium=copie&utm_campaign=relier` |
| Duel Combien ? | `https://linkguessr.com/defi?jeu=nombre&score=340&utm_source=duel&utm_medium=copie&utm_campaign=combien` |
| Chemin d'Explorer | `https://linkguessr.com/explorer?de=Q21621995&a=Q7186&utm_source=partage&utm_medium=copie&utm_campaign=explorer` |

Formats détaillés de tous les liens, et liens de promotion prêts à copier : [liens.md](liens.md).

Comportement :

- Les redirections (`www.linkguessr.com`, `http://`, `link-guessr.vercel.app` → `https://linkguessr.com`)
  conservent le chemin et les paramètres.
- Umami enregistre les UTM avec la première page vue. Ensuite, le site retire `utm_*` de la barre d'adresse sans
  recharger la page. Une adresse copiée et renvoyée à un ami ne compte donc pas une seconde fois pour la même
  source. Si Umami est bloqué, le nettoyage se fait quand même 3 s après le chargement.
- `utm_source` est aussi gardé pour la session (sessionStorage) et joint aux événements, côté Umami
  (propriété `source`) et côté API (`src`, tableau `/admin`). L'ancien paramètre `?src=` est encore lu
  pour les liens partagés avant le passage aux UTM.

## Événements Umami

Les noms sont fixes et le jeu est une propriété : un seul événement suffit pour comparer les jeux.

| Événement | Quand | Propriétés |
|---|---|---|
| `partie_debut` | Première action d'une partie (première proposition, premier coup, début du chrono) | `jeu`, `source` |
| `partie_fin` | Fin d'une partie | `jeu`, `source`, `resultat`, `essais` |
| `partage_clic` | Clic sur « Partager », « Défier un ami » ou « Partager ce chemin » | `jeu`, `source`, `methode` |
| `duel_ouvert` | Arrivée sur un lien de duel (`/defi`) | `jeu`, `source` |
| `exploration_recherche` | Chaque recherche de chemin dans Explorer | `jeu` (`explorer`), `source`, `resultat` |
| `partage_ouvert` | Arrivée sur un chemin partagé d'Explorer (`/explorer?de=…&a=…`), même si le lien est périmé | `jeu` (`explorer`), `source` |

Valeurs des propriétés :

| Propriété | Valeurs |
|---|---|
| `jeu` | `qui-est-cache`, `relier`, `combien`, `defi-du-jour` ; `explorer` (pour `exploration_recherche`, `partage_clic` et `partage_ouvert`) |
| `source` | `utm_source` de l'arrivée, ou `direct` |
| `resultat` | `gagne` / `perdu` (Qui est caché ?, défi du jour) ; `gagne` (Relier, une partie se termine en atteignant la cible) ; `termine` (Combien ?, fin du chrono) ; `chemin` / `aucun` (`exploration_recherche` : chemin trouvé ou non) |
| `essais` | Propositions (Qui est caché ?, défi du jour), coups (Relier), réponses données (Combien ?) |
| `methode` | `webshare`, `copie`, `annule` (menu natif fermé), `echec` (copie impossible) |

Explorer n'a pas de partie à finir : il n'envoie ni `partie_debut` ni `partie_fin`, ce qui fausserait les taux de
fin de partie. Il se mesure en **recherches par visite** (`exploration_recherche`) et en **durée de visite** sur
`/explorer`. L'affichage d'un chemin partagé n'est pas une recherche : il envoie `partage_ouvert`, pas
`exploration_recherche`.

L'API reçoit en parallèle ses propres événements (`start`, `finish`, `share`, `duel_open`, `explore`) pour le
tableau de bord `/admin`. Ils ne changent pas.

## Lire les résultats dans Umami

Ouvrir `https://linkguessr.com/umami`, puis le site **LinkGuessr** (domaine `linkguessr.com`).

- **D'où viennent les visiteurs** : onglet **UTM** (répartition par source, support et campagne), ou bouton
  **Filtre** de la vue d'ensemble, par exemple `utm_source` = `reddit`.
- **Ce que rapporte le partage** : filtre `utm_source` = `partage` ou `duel`, puis répartition par `utm_campaign`
  (le jeu) et `utm_medium` (copie ou menu natif).
- **Activité par jeu** : onglet **Événements**, choisir `partie_debut` ou `partie_fin`, puis **Propriétés** →
  `jeu`. Taux de fin d'un jeu : `partie_fin` divisé par `partie_debut` pour la même valeur de `jeu`.
- **Explorer** : recherches par visite = nombre d'`exploration_recherche` divisé par le nombre de visites qui
  passent par `/explorer` (Événements → `exploration_recherche` → **Propriétés** → `resultat` pour la part sans chemin).
  Durée de visite : vue d'ensemble filtrée sur l'URL `/explorer` (durée moyenne de visite).
- **Réussite et difficulté** : `partie_fin`, propriétés `resultat` et `essais`, filtrées sur un `jeu`.
- **Viralité** : `partage_clic` (par `jeu` et `methode`), puis `duel_ouvert`, puis les visites
  `utm_source` = `duel`. Un **entonnoir** (Funnel) `partage_clic` → `duel_ouvert` → `partie_fin` donne la boucle complète.
  Pour Explorer : `partage_clic` (`jeu` = `explorer`) → `partage_ouvert` → `exploration_recherche`.
- **Attribution** : le rapport **Attribution** relie les événements (par exemple `partie_fin`) à la première source
  de la visite.

Test rapide : ouvrir `https://linkguessr.com/?utm_source=test&utm_medium=test&utm_campaign=test`. L'URL se nettoie
en moins d'une seconde, et la visite apparaît dans **Temps réel** puis dans l'onglet **UTM** avec la valeur `test`.
