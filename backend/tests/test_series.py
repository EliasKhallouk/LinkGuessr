import numpy as np

from app import main
from app.core import state
from app.graph import PersonGraph
from tests.test_graph import random_graph


def test_meme_graine_meme_serie(monkeypatch):
    """Duel « Combien ? » : même graine et même rang donnent la même paire ; une autre graine, une autre série."""
    n = 400
    a, b, kinds = random_graph(n, 900, 7)
    monkeypatch.setitem(state, "graph", PersonGraph(n, a, b, kinds, np.random.default_rng(7).random(n)))
    monkeypatch.setitem(state, "eras", {"tous": {"order": np.arange(n)}})

    def series(seed):
        return [main._pick_balanced("moyen", None, "all", 2, 6, rng=np.random.default_rng([seed, i]))[:2] for i in range(8)]

    assert series(12345) == series(12345)
    assert series(12345) != series(54321)


def test_meme_graine_memes_enigmes(monkeypatch):
    """Partie de 10 énigmes rejouée par un ami : même graine et même rang, même chemin et même personne cachée."""
    n = 400
    a, b, kinds = random_graph(n, 1600, 3)
    monkeypatch.setitem(state, "graph", PersonGraph(n, a, b, kinds, np.random.default_rng(3).random(n)))
    monkeypatch.setitem(state, "eras", {"tous": {"order": np.arange(n), "rank": np.arange(n) + 1}})
    monkeypatch.setitem(state, "domain_names", [])

    def series(seed):
        return [main._pick_around("difficile", None, "tous", 3, rng=np.random.default_rng([seed, i])) for i in range(5)]

    assert series(42) == series(42)
    assert series(42) != series(43)
