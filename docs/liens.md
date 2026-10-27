# Liens de LinkGuessr

Tous les liens du site, au même endroit. Domaine : `https://linkguessr.com`. `www.linkguessr.com` et
`link-guessr.vercel.app` y redirigent en gardant le chemin et les paramètres.
Convention des paramètres UTM et événements Umami : [tracking.md](tracking.md).

## a. Pages du site

| Adresse | À quoi elle sert |
|---|---|
| `/` | Accueil : défi du jour, cartes des jeux, chiffres du réseau |
| `/qui-est-cache` | Jeu « Qui est caché ? » : deviner la personne masquée au milieu d'un chemin |
| `/relier` | Jeu « Relier » : aller d'une personnalité à une autre, de lien en lien |
| `/combien` | Jeu « Combien de liens ? » : estimer des distances en 60 secondes, avec classement |
| `/explorer` | Explorer : le plus court chemin entre deux personnalités, lien par lien (`?from=Q…` pré-remplit la première personne) |
| `/jour/:n` | Défi du jour numéro `n` (archive, ou celui du jour) |
| `/defi?jeu=…` | Arrivée d'un lien de duel (voir b.) |
| `/personne/:qid` | Fiche d'une personnalité : liens, personnes les plus proches, photo et crédits |
| `/lab` | Lab : analyses du réseau (popularité, communautés, distances). `/stats` redirige ici |
| `/a-propos` | À propos : sources, méthode, licences et crédits |
| `/contact` | Contact (contact@linkguessr.com) |
| `/politique-de-confidentialite` | Ce qui est enregistré, pourquoi, combien de temps |
| `/mentions-legales` | Éditeur, publication, hébergeurs, crédits |
| `/admin` | Privé (jeton) : retours des joueurs, parties par jeu et par source, lien vers Umami |
| `/admin/defis` | Privé (jeton) : programmation des défis du jour |
| `/umami` | Privé (compte) : tableau de bord Umami |

## b. Liens générés par le site

Le site ajoute toujours `utm_source`, `utm_medium` et `utm_campaign`, dans cet ordre. `utm_medium` vaut
`webshare` (menu de partage du téléphone) ou `copie` (presse-papiers). Les UTM sont retirés de la barre
d'adresse après l'arrivée.

| Lien | Format | Paramètres | UTM |
|---|---|---|---|
| Défi du jour | `/jour/:n` | `n` : numéro du défi | `utm_source=partage`, `utm_campaign=defi-du-jour` |
| Duel Qui est caché ? | `/defi?jeu=qui&t=<jeton>` | `t` : énigme (chemin, position cachée, niveau, époque) et résultat de l'ami, chiffrés par l'API (AES-GCM). Les anciens liens `jeu=cache&chemin=…` restent acceptés | `utm_source=duel`, `utm_campaign=qui-est-cache` |
| Duel Relier | `/defi?jeu=relais&paire=Q1-Q2&score=N` | `paire` : départ et cible ; `score` : coups de l'ami | `utm_source=duel`, `utm_campaign=relier` |
| Duel Combien ? | `/defi?jeu=nombre&score=N` | `score` : points de l'ami | `utm_source=duel`, `utm_campaign=combien` |
| Chemin d'Explorer | `/explorer?de=Q1&a=Q2[&mode=strong\|wikidata]` | `de`, `a` : les deux bouts (chemin recalculé à l'ouverture) ; `mode` seulement s'il n'est pas « tous les liens » | `utm_source=partage`, `utm_campaign=explorer` |

Exemples complets :

```
https://linkguessr.com/jour/12?utm_source=partage&utm_medium=webshare&utm_campaign=defi-du-jour
https://linkguessr.com/defi?jeu=qui&t=3q2-7Xk…(≈ 60 à 100 caractères)&utm_source=duel&utm_medium=copie&utm_campaign=qui-est-cache
https://linkguessr.com/defi?jeu=relais&paire=Q21621995-Q7186&score=4&utm_source=duel&utm_medium=copie&utm_campaign=relier
https://linkguessr.com/defi?jeu=nombre&score=340&utm_source=duel&utm_medium=webshare&utm_campaign=combien
https://linkguessr.com/explorer?de=Q21621995&a=Q7186&utm_source=partage&utm_medium=copie&utm_campaign=explorer
```

Aucun de ces liens ne contient de réponse en clair : le défi du jour ne porte que son numéro, Relier et
Combien les deux bouts et le score de l'ami (pas le plus court chemin ni les bonnes réponses), et le duel
« Qui est caché ? » un jeton illisible sans la clé de l'API. Un jeton modifié est refusé (message et bouton
« Nouvelle partie »).

## c. Liens de promotion à poser à la main

| Où | Lien | Où je l'ai utilisé / date |
|---|---|---|
| LinkedIn, post | `https://linkguessr.com/?utm_source=linkedin&utm_medium=post&utm_campaign=lancement` | |
| École, message | `https://linkguessr.com/?utm_source=ecole&utm_medium=message&utm_campaign=lancement` | |
| Reddit, post | `https://linkguessr.com/?utm_source=reddit&utm_medium=post&utm_campaign=lancement` | |
| TikTok, bio | `https://linkguessr.com/?utm_source=tiktok&utm_medium=bio&utm_campaign=lancement` | |
| Instagram, bio | `https://linkguessr.com/?utm_source=instagram&utm_medium=bio&utm_campaign=lancement` | |
| Discord, message | `https://linkguessr.com/?utm_source=discord&utm_medium=message&utm_campaign=lancement` | |
| WhatsApp, message | `https://linkguessr.com/?utm_source=whatsapp&utm_medium=message&utm_campaign=lancement` | |
| Presse, article | `https://linkguessr.com/?utm_source=presse&utm_medium=article&utm_campaign=lancement` | |
| Email, signature | `https://linkguessr.com/?utm_source=email&utm_medium=signature&utm_campaign=permanent` | |

Pour envoyer vers un jeu précis, garde les mêmes paramètres et change le chemin, par exemple
`https://linkguessr.com/qui-est-cache?utm_source=reddit&utm_medium=post&utm_campaign=lancement`.

## d. Créer un nouveau lien de campagne

1. Tout en minuscules, mots séparés par des tirets, sans accent ni espace.
2. Garde `utm_source` (le site ou la personne qui publie) et `utm_medium` (le format) de la liste de
   [tracking.md](tracking.md) ; ajoute-y d'abord toute nouvelle valeur.
3. Pour une opération précise, change seulement `utm_campaign`, par exemple
   `https://linkguessr.com/explorer?de=Q21621995&a=Q7186&utm_source=tiktok&utm_medium=bio&utm_campaign=video-mbappe-curie`.

Dans Umami (`https://linkguessr.com/umami`, site LinkGuessr) : onglet **UTM**, répartition par campagne, ou
**Filtre** `utm_campaign` = `video-mbappe-curie` sur la vue d'ensemble. Le rapport **Attribution** montre ce que
la campagne a rapporté en parties (`partie_fin`) et en partages (`partage_clic`).
