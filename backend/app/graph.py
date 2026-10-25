"""Graphe des personnes en mémoire et plus courts chemins.

Le graphe est stocké en CSR (Compressed Sparse Row) : les voisins du nœud v sont
`neighbors[indptr[v]:indptr[v + 1]]`. Le parcours en largeur bidirectionnel traite
chaque niveau d'un coup avec numpy (pas de boucle Python par nœud), en avançant
toujours le côté dont la frontière a le moins de voisins à visiter.
"""
from dataclasses import dataclass

import numpy as np

# Bits de la colonne edge.kinds
TEXT_AB, TEXT_BA, WIKIDATA = 1, 2, 4

MODES = {
    # tous les liens
    "all": lambda k: np.ones(len(k), dtype=bool),
    # liens « forts » : cités dans les deux sens, ou relation Wikidata
    "strong": lambda k: ((k & (TEXT_AB | TEXT_BA)) == (TEXT_AB | TEXT_BA)) | ((k & WIKIDATA) > 0),
    # uniquement les relations Wikidata (famille, élève, succession...)
    "wikidata": lambda k: (k & WIKIDATA) > 0,
}


@dataclass
class CSR:
    indptr: np.ndarray     # int64, taille n + 1
    neighbors: np.ndarray  # int32

    def degree(self, v: int) -> int:
        return int(self.indptr[v + 1] - self.indptr[v])

    def neighbors_of(self, v: int) -> np.ndarray:
        return self.neighbors[self.indptr[v]:self.indptr[v + 1]]

    def expand(self, frontier: np.ndarray) -> np.ndarray:
        """Tous les voisins (avec doublons) des nœuds de la frontière, vectorisé."""
        return self.expand_with_owner(frontier)[1]

    def expand_with_owner(self, frontier: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(owner, voisin) pour chaque arête sortant de la frontière."""
        starts = self.indptr[frontier]
        lengths = self.indptr[frontier + 1] - starts
        total = int(lengths.sum())
        if total == 0:
            return np.empty(0, dtype=frontier.dtype), np.empty(0, dtype=self.neighbors.dtype)
        offsets = np.repeat(starts - np.cumsum(lengths) + lengths, lengths) + np.arange(total)
        return np.repeat(frontier, lengths), self.neighbors[offsets]

    def frontier_cost(self, frontier: np.ndarray) -> int:
        return int((self.indptr[frontier + 1] - self.indptr[frontier]).sum())


def build_csr(n: int, a: np.ndarray, b: np.ndarray) -> CSR:
    """CSR non orienté à partir d'arêtes (a, b)."""
    src = np.concatenate([a, b])
    dst = np.concatenate([b, a]).astype(np.int32)
    order = np.argsort(src, kind="stable")
    counts = np.bincount(src, minlength=n)
    indptr = np.zeros(n + 1, dtype=np.int64)
    np.cumsum(counts, out=indptr[1:])
    return CSR(indptr=indptr, neighbors=dst[order])


@dataclass
class PathResult:
    length: int | None          # nombre de liens (None : pas de chemin)
    n_paths: int                # nombre total de plus courts chemins
    paths: list[list[int]]      # au plus `limit` chemins, du plus « connu » au moins connu


class PersonGraph:
    def __init__(self, n: int, a: np.ndarray, b: np.ndarray, kinds: np.ndarray, popularity: np.ndarray):
        self.n = n
        self.popularity = popularity.astype(np.float32)
        self.csr = {}
        for mode, select in MODES.items():
            mask = select(kinds)
            self.csr[mode] = build_csr(n, a[mask], b[mask])

    def shortest_paths(self, s: int, t: int, mode: str = "all", limit: int = 5, max_depth: int = 12) -> PathResult:
        g = self.csr[mode]
        if s == t:
            return PathResult(0, 1, [[s]])

        dist_s = np.full(self.n, -1, dtype=np.int16)
        dist_t = np.full(self.n, -1, dtype=np.int16)
        dist_s[s], dist_t[t] = 0, 0
        front_s, front_t = np.array([s], dtype=np.int64), np.array([t], dtype=np.int64)
        ds = dt = 0

        meet = None
        while len(front_s) and len(front_t) and ds + dt < max_depth:
            # On avance le côté le moins coûteux.
            if g.frontier_cost(front_s) <= g.frontier_cost(front_t):
                nxt = np.unique(g.expand(front_s))
                nxt = nxt[dist_s[nxt] < 0]
                ds += 1
                dist_s[nxt] = ds
                front_s = nxt.astype(np.int64)
                hit = nxt[dist_t[nxt] >= 0]
            else:
                nxt = np.unique(g.expand(front_t))
                nxt = nxt[dist_t[nxt] < 0]
                dt += 1
                dist_t[nxt] = dt
                front_t = nxt.astype(np.int64)
                hit = nxt[dist_s[nxt] >= 0]
            if len(hit):
                total = dist_s[hit].astype(np.int32) + dist_t[hit]
                meet = hit[total == total.min()]
                break

        if meet is None:
            return PathResult(None, 0, [])

        length = int(dist_s[meet[0]]) + int(dist_t[meet[0]])
        # Tout plus court chemin passe par exactement un nœud à distance dist_s[meet[0]] de s :
        # la couche de rencontre. On remonte vers s via dist_s et vers t via dist_t.
        layer = int(dist_s[meet[0]])
        candidates = np.flatnonzero(dist_s == layer)
        meet = candidates[dist_t[candidates] == length - layer]

        n_paths = int(round(float((self._count(g, dist_s, meet) * self._count(g, dist_t, meet)).sum())))

        paths = []
        for m in sorted(meet.tolist(), key=lambda v: -self.popularity[v]):
            for left in self._walk(g, dist_s, m, limit):
                for right in self._walk(g, dist_t, m, limit):
                    paths.append(left[::-1] + right[1:])
            if len(paths) >= limit * 4:
                break
        # Les chemins par des intermédiaires connus d'abord (plus jouables).
        paths.sort(key=lambda p: -float(self.popularity[p[1:-1]].mean()) if len(p) > 2 else 0)
        return PathResult(length, n_paths, paths[:limit])

    @staticmethod
    def _predecessors(g: CSR, dist: np.ndarray, v: int) -> np.ndarray:
        nb = g.neighbors_of(v)
        return nb[dist[nb] == dist[v] - 1]

    @staticmethod
    def _count(g: CSR, dist: np.ndarray, targets: np.ndarray) -> np.ndarray:
        """Nombre de plus courts chemins entre l'origine de `dist` et chaque nœud de `targets`.

        On remonte d'abord les couches utiles (ancêtres de `targets`), puis on propage
        les comptes de l'origine vers `targets`, une couche à la fois (vectorisé).
        """
        layers = [np.unique(targets)]
        while dist[layers[-1][0]] > 0:
            owners, nb = g.expand_with_owner(layers[-1].astype(np.int64))
            layers.append(np.unique(nb[dist[nb] == dist[layers[-1][0]] - 1]))
        counts = np.zeros(len(dist), dtype=np.float64)
        counts[layers[-1]] = 1.0
        for layer in reversed(layers[:-1]):
            owners, nb = g.expand_with_owner(layer.astype(np.int64))
            ok = dist[nb] == dist[layer[0]] - 1
            np.add.at(counts, owners[ok], counts[nb[ok]])
        return counts[targets]

    def _walk(self, g: CSR, dist: np.ndarray, v: int, limit: int) -> list[list[int]]:
        """Jusqu'à `limit` chemins de v vers l'origine de `dist`, en préférant les nœuds connus."""
        if dist[v] == 0:
            return [[v]]
        out = []
        preds = self._predecessors(g, dist, v)
        for u in preds[np.argsort(-self.popularity[preds])][:limit]:
            for tail in self._walk(g, dist, int(u), limit):
                out.append([v] + tail)
                if len(out) >= limit:
                    return out
        return out
