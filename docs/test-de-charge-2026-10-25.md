# Test de charge — 25 octobre 2026

Script : `backend/tools/load_test.py` (mélange réaliste : 30 % défi du jour, 20 % recherche, 15 % fiches,
15 % chemins, 10 % paires aléatoires, 10 % chiffres clés). Trois niveaux de 20 s : 5, 20 et 50 clients simultanés.

## Ce qu'il faut retenir

- **Le cache Vercel fonctionne** : 64 à 80 % des requêtes sont servies par Vercel sans toucher la VM
  (défi du jour, fiches, recherche, chiffres clés). Les chemins sont aussi mis en cache, par paire.
- **Capacité brute de la VM (sans cache) : environ 50 requêtes/s** sur ce mélange, CPU à 100 %.
  Mesure pessimiste : le générateur de charge tournait sur la même VM (1 cœur).
- **La « carte » d'une personne était le point faible** (500 ms, rang calculé en SQL à chaque appel) :
  rang précalculé au démarrage → 4 à 16 ms. Corrigé pendant le test.
- **Les quotas protègent la VM** : un seul client qui enchaîne 50 requêtes en parallèle reçoit des 429
  sur `/random_pair` et `/path` (60 et 120 par minute et par IP), sans erreur 5xx.
- **Le test à travers Vercel depuis le PC est limité par le PC lui-même** (connexion domestique, antivirus
  qui inspecte chaque connexion TLS) : les latences aux niveaux 20 et 50 mesurent surtout le client.
  Pour un vrai test de montée en charge, lancer le script depuis une machine dans le cloud.

## Ordre de grandeur

Avec ~75 % de cache, la VM ne voit qu'un quart du trafic : le site devrait encaisser **plusieurs centaines
de requêtes par seconde** côté joueurs avant de saturer la VM (estimation, non mesurée directement).
Une partie de « Qui est caché ? » fait une dizaine de requêtes : c'est large pour un pic de partage.

---

## Annexe 1 — Directement sur la VM (capacité brute, quotas levés)

Cible : `http://127.0.0.1:8000` · 20 s par niveau · quotas levés : oui

| Concurrence | Requêtes | Req/s | p50 | p95 | p99 | Erreurs | 429 | Cache HIT | CPU VM moyen / max | RAM dispo min |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 998 | 49.7 | 21 ms | 588 ms | 814 ms | 11 | 0 | 0 % | 100 % / 100 % | 4103 Mo |
| 20 | 818 | 40.6 | 419 ms | 1157 ms | 1767 ms | 11 | 0 | 0 % | 100 % / 100 % | 4021 Mo |
| 50 | 1113 | 52.7 | 941 ms | 1662 ms | 1824 ms | 9 | 0 | 0 % | 100 % / 100 % | 4016 Mo |

## Concurrence 5 : détail par route

| Route | Requêtes | p50 | p95 | Codes |
|---|---|---|---|---|
| card | 140 | 516 ms | 898 ms | {"200": 140} |
| daily | 302 | 9 ms | 24 ms | {"200": 302} |
| path | 139 | 42 ms | 98 ms | {"200": 139} |
| random_pair | 101 | 39 ms | 80 ms | {"200": 101} |
| search | 207 | 20 ms | 59 ms | {"0": 11, "200": 196} |
| stats | 109 | 3 ms | 11 ms | {"200": 109} |

## Concurrence 20 : détail par route

| Route | Requêtes | p50 | p95 | Codes |
|---|---|---|---|---|
| card | 139 | 876 ms | 1768 ms | {"200": 139} |
| daily | 243 | 320 ms | 814 ms | {"200": 243} |
| path | 120 | 711 ms | 1313 ms | {"200": 120} |
| random_pair | 70 | 381 ms | 795 ms | {"200": 70} |
| search | 174 | 318 ms | 842 ms | {"0": 11, "200": 163} |
| stats | 72 | 4 ms | 33 ms | {"200": 72} |

## Concurrence 50 : détail par route

| Route | Requêtes | p50 | p95 | Codes |
|---|---|---|---|---|
| card | 160 | 1300 ms | 1774 ms | {"200": 160} |
| daily | 363 | 782 ms | 1172 ms | {"200": 363} |
| path | 158 | 1438 ms | 1827 ms | {"200": 158} |
| random_pair | 106 | 874 ms | 1174 ms | {"200": 106} |
| search | 242 | 838 ms | 1168 ms | {"0": 9, "200": 233} |
| stats | 84 | 144 ms | 430 ms | {"200": 84} |

---

## Annexe 2 — Depuis le PC, à travers Vercel (cache et quotas actifs)

Cible : `https://link-guessr.vercel.app/v1` · 20 s par niveau · quotas levés : non

| Concurrence | Requêtes | Req/s | p50 | p95 | p99 | Erreurs | 429 | Cache HIT | CPU VM moyen / max | RAM dispo min |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 465 | 22.9 | 166 ms | 413 ms | 952 ms | 0 | 0 | 64 % | 18 % / 24 % | 4184 Mo |
| 20 | 560 | 27.0 | 595 ms | 1573 ms | 1995 ms | 0 | 69 | 77 % | 96 % / 100 % | 4184 Mo |
| 50 | 564 | 25.8 | 1511 ms | 4134 ms | 6079 ms | 0 | 107 | 80 % | 38 % / 100 % | 4186 Mo |

## Concurrence 5 : détail par route

| Route | Requêtes | p50 | p95 | Codes |
|---|---|---|---|---|
| card | 73 | 159 ms | 387 ms | {"200": 73} |
| daily | 133 | 122 ms | 216 ms | {"200": 133} |
| path | 87 | 309 ms | 517 ms | {"200": 87} |
| random_pair | 45 | 327 ms | 587 ms | {"200": 45} |
| search | 85 | 155 ms | 377 ms | {"200": 85} |
| stats | 42 | 126 ms | 289 ms | {"200": 42} |

## Concurrence 20 : détail par route

| Route | Requêtes | p50 | p95 | Codes |
|---|---|---|---|---|
| card | 99 | 489 ms | 1407 ms | {"200": 99} |
| daily | 160 | 487 ms | 1432 ms | {"200": 160} |
| path | 93 | 734 ms | 1922 ms | {"200": 67, "429": 26} |
| random_pair | 58 | 641 ms | 1822 ms | {"200": 15, "429": 43} |
| search | 103 | 590 ms | 1808 ms | {"200": 103} |
| stats | 47 | 598 ms | 1506 ms | {"200": 47} |

## Concurrence 50 : détail par route

| Route | Requêtes | p50 | p95 | Codes |
|---|---|---|---|---|
| card | 84 | 1155 ms | 4189 ms | {"200": 84} |
| daily | 188 | 1306 ms | 3936 ms | {"200": 188} |
| path | 81 | 1852 ms | 5198 ms | {"200": 26, "429": 55} |
| random_pair | 54 | 2334 ms | 3845 ms | {"200": 2, "429": 52} |
| search | 104 | 1656 ms | 4244 ms | {"200": 104} |
| stats | 53 | 1147 ms | 4910 ms | {"200": 53} |
