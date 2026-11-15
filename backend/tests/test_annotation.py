import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import annotation
from app.annotation import check_label


def test_grille_du_guide():
    assert len(annotation.LABELS) == 15  # 14 sous-types + inclassable
    assert len(set(annotation.LABELS)) == 15


@pytest.mark.parametrize("labels,cotoyes", [(["couple"], "oui"), (["famille", "hierarchie"], "incertain"),
                                            (["co_mention"], "incertain"), (["inclassable"], "non")])
def test_annotations_valides(labels, cotoyes):
    assert check_label(labels, cotoyes, False) is None


@pytest.mark.parametrize("labels,cotoyes", [([], "oui"), (["inconnu"], "oui"), (["couple", "couple"], "oui"),
                                            (["co_mention", "couple"], "oui"), (["inclassable", "source"], "non"),
                                            (["famille", "couple", "proches", "lutte"], "oui"), (["couple"], None),
                                            (["couple"], "peut-être")])
def test_annotations_refusees(labels, cotoyes):
    assert check_label(labels, cotoyes, False)


def test_mauvaise_personne_sans_rien_d_autre():
    assert check_label([], None, True) is None


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(annotation.router)
    return TestClient(app)


def test_jeton_invalide_refuse(client, monkeypatch):
    monkeypatch.setattr(annotation, "ANNOT_TOKENS", {"bon": {"name": "x", "scope": "tout"}})
    assert client.get("/annot/item", params={"t": "mauvais"}).status_code == 401
    r = client.post("/annot/label", json={"t": "mauvais", "id": 0, "labels": ["couple"], "cotoyes": "oui"})
    assert r.status_code == 401


def test_page_servie_sans_indexation(client):
    r = client.get("/annoter")
    assert r.status_code == 200 and "Annotation des liens" in r.text
    assert r.headers["x-robots-tag"] == "noindex"


class FakeConn:
    """Base en mémoire qui répond aux requêtes de app.annotation (et seulement à elles)."""

    def __init__(self, items, labels):
        self.items, self.labels = items, labels

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        rows = []
        if sql.startswith("SELECT id FROM app.annot_item"):
            ids = [i for i, it in self.items.items() if "WHERE accord" not in sql or it["accord"]]
            rows = [(i,) for i in sorted(ids, key=lambda i: (self.items[i]["accord"], i))]
        elif sql.startswith("SELECT item_id, labels"):
            rows = [(i, *v) for (i, who), v in self.labels.items() if who == params[0]]
        elif sql.startswith("SELECT accord, data, suggestion"):
            it = self.items[params[0]]
            rows = [(it["accord"], it["data"], it["suggestion"])]
        elif sql.startswith("SELECT accord FROM"):
            rows = [(self.items[params[0]]["accord"],)] if params[0] in self.items else []
        elif sql.lstrip().startswith("INSERT INTO app.annot_label"):
            i, who, labels, cotoyes, wrong, doubt, comment, _ = params
            self.labels[(i, who)] = (labels, cotoyes, wrong, doubt, comment)
        return type("R", (), {"fetchall": lambda s: rows, "fetchone": lambda s: rows[0] if rows else None})()


@pytest.fixture
def base(monkeypatch):
    items = {i: {"accord": i < 2, "data": {"sentence": f"phrase {i}"}, "suggestion": {"labels": ["couple"]}}
             for i in range(5)}
    conn = FakeConn(items, {})
    monkeypatch.setattr(annotation, "pool", type("P", (), {"connection": lambda s: conn})())
    monkeypatch.setattr(annotation, "ANNOT_TOKENS", {"t1": {"name": "elias", "scope": "tout"},
                                                     "t2": {"name": "second", "scope": "accord"}})
    return conn


def test_parcours_complet(client, base):
    r = client.get("/annot/item", params={"t": "t1"}).json()
    assert r["id"] == 2 and not r["accord"] and r["suggestion"] == {"labels": ["couple"]}  # hors accord d'abord
    assert client.post("/annot/label", json={"t": "t1", "id": 2, "labels": ["couple"], "cotoyes": "oui"}).status_code == 200
    assert client.get("/annot/item", params={"t": "t1"}).json()["id"] == 3
    r = client.get("/annot/item", params={"t": "t1", "id": 2}).json()
    assert r["label"]["labels"] == ["couple"] and r["done"] == 1
    r = client.get("/annot/item", params={"t": "t1", "id": 0}).json()
    assert r["accord"] and r["suggestion"] is None  # accord : jamais de proposition


def test_second_annotateur_ne_voit_que_l_accord(client, base):
    r = client.get("/annot/item", params={"t": "t2"}).json()
    assert r["id"] == 0 and r["total"] == 2 and r["suggestion"] is None
    assert client.get("/annot/item", params={"t": "t2", "id": 3}).status_code == 404
    r = client.post("/annot/label", json={"t": "t2", "id": 3, "labels": ["couple"], "cotoyes": "oui"})
    assert r.status_code == 404
    for i in (0, 1):
        client.post("/annot/label", json={"t": "t2", "id": i, "labels": ["source"], "cotoyes": "incertain"})
    assert client.get("/annot/item", params={"t": "t2"}).json()["finished"]
