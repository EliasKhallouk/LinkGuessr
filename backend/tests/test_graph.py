import random

import igraph as ig
import numpy as np
import pytest

from app.graph import PersonGraph


def random_graph(n: int, m: int, seed: int):
    rng = random.Random(seed)
    edges = set()
    while len(edges) < m:
        a, b = rng.randrange(n), rng.randrange(n)
        if a != b:
            edges.add((min(a, b), max(a, b)))
    a, b = map(np.array, zip(*sorted(edges)))
    kinds = np.array([rng.choice([1, 2, 3, 4, 5, 7]) for _ in range(len(a))], dtype=np.int16)
    return a.astype(np.int32), b.astype(np.int32), kinds


@pytest.mark.parametrize("seed", range(20))
def test_matches_igraph(seed):
    n = 400
    a, b, kinds = random_graph(n, 900, seed)
    pop = np.random.default_rng(seed).random(n)
    graph = PersonGraph(n, a, b, kinds, pop)
    ref = ig.Graph(n=n, edges=list(zip(a.tolist(), b.tolist())))
    edge_set = {(x, y) for x, y in zip(a.tolist(), b.tolist())} | {(y, x) for x, y in zip(a.tolist(), b.tolist())}

    rng = random.Random(seed)
    for _ in range(30):
        s, t = rng.randrange(n), rng.randrange(n)
        res = graph.shortest_paths(s, t, limit=5)
        expected = ref.get_all_shortest_paths(s, to=t)
        if not expected:
            assert res.length is None
            continue
        assert res.length == len(expected[0]) - 1
        assert res.n_paths == len(expected)
        assert 1 <= len(res.paths) <= 5
        for p in res.paths:
            assert p[0] == s and p[-1] == t and len(p) == res.length + 1
            assert all((u, v) in edge_set for u, v in zip(p, p[1:]))
        assert len({tuple(p) for p in res.paths}) == len(res.paths)


def test_modes_filter_edges():
    # 0-1 texte dans un seul sens, 1-2 relation Wikidata, 0-2 lien réciproque
    a, b = np.array([0, 1, 0]), np.array([1, 2, 2])
    graph = PersonGraph(3, a, b, np.array([1, 4, 3], dtype=np.int16), np.zeros(3))
    assert graph.shortest_paths(0, 1, "all").length == 1
    assert graph.shortest_paths(0, 1, "strong").length == 2   # via 2
    assert graph.shortest_paths(0, 1, "wikidata").length is None
