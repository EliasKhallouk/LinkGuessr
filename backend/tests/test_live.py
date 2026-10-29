import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import live, main

ORIGIN = {"origin": "https://linkguessr.com"}
PUZZLE = {"path": ["Q1", "Q2", "Q3"], "masked_index": 1, "persons": {}, "hops": {}, "answer_hops": {},
          "choices": [{"qid": "Q2"}, {"qid": "Q9"}], "answer": {"qid": "Q2"}}


@pytest.fixture
def client(monkeypatch):
    """Salons sans graphe ni base : énigme factice, manches courtes."""
    monkeypatch.setattr(main, "seeded_puzzle", lambda *a, **k: PUZZLE)
    monkeypatch.setattr(live, "ROUNDS", 2)
    monkeypatch.setattr(live, "ROUND_SECONDS", 2)
    monkeypatch.setattr(live, "REVEAL_SECONDS", 0.2)
    live.rooms.clear()
    app = FastAPI()
    app.include_router(live.router)
    with TestClient(app) as c:
        yield c


def until(ws, phase):
    while True:
        msg = ws.receive_json()
        if msg["t"] == "state" and msg["phase"] == phase:
            return msg


def test_partie_a_deux(client):
    code = client.post("/live/rooms", json={"niveau": "moyen"}).json()["code"]
    with client.websocket_connect(f"/live/{code}", headers=ORIGIN) as a, \
         client.websocket_connect(f"/live/{code}", headers=ORIGIN) as b:
        a.send_json({"t": "join", "token": "a" * 16, "pseudo": "Inès"})
        pid_a = a.receive_json()["pid"]
        b.send_json({"t": "join", "token": "b" * 16, "pseudo": "Inès"})
        pid_b = b.receive_json()["pid"]
        lobby = until(b, "lobby")
        assert lobby["host"] == pid_a
        assert sorted(p["pseudo"] for p in lobby["players"]) == ["Ines", "Ines 2"]

        b.send_json({"t": "start"})  # pas l'hôte : ignoré
        a.send_json({"t": "start"})
        question = until(a, "question")
        assert "answer" not in question["puzzle"]  # la réponse reste sur le serveur pendant la manche
        a.send_json({"t": "answer", "qid": "Q2"})
        b.send_json({"t": "answer", "qid": "Q9"})
        reveal = until(a, "reveal")
        last = {p["pid"]: p["last"] for p in reveal["players"]}
        assert last[pid_a]["correct"] and 1000 <= last[pid_a]["points"] <= 2000  # niveau moyen : ×2
        assert last[pid_b] == {"qid": "Q9", "correct": False, "points": 0}
        assert reveal["puzzle"]["answer"]["qid"] == "Q2"

        end = until(a, "end")  # 2e manche sans réponse : fin au bout du temps
        assert end["players"][0]["pid"] == pid_a


def test_points():
    assert live.points("facile", 0) == 1000
    assert live.points("facile", live.ROUND_SECONDS) == 500
    assert live.points("humain", 0) == 10000


def test_refus(client):
    code = client.post("/live/rooms", json={}).json()["code"]
    with client.websocket_connect("/live/ZZZZ", headers=ORIGIN) as ws:
        assert ws.receive_json()["fatal"]
    with client.websocket_connect(f"/live/{code}", headers=ORIGIN) as ws:
        ws.send_json({"t": "join", "token": "c" * 16, "pseudo": "connard"})
        assert "pseudo" in ws.receive_json()["message"]
    with pytest.raises(Exception):
        with client.websocket_connect(f"/live/{code}", headers={"origin": "https://exemple.com"}) as ws:
            ws.receive_json()


def test_retour_apres_rechargement(client):
    code = client.post("/live/rooms", json={}).json()["code"]
    with client.websocket_connect(f"/live/{code}", headers=ORIGIN) as ws:
        ws.send_json({"t": "join", "token": "d" * 16, "pseudo": "Noah"})
        pid = ws.receive_json()["pid"]
    with client.websocket_connect(f"/live/{code}", headers=ORIGIN) as ws:
        ws.send_json({"t": "join", "token": "d" * 16, "pseudo": "autre"})
        assert ws.receive_json()["pid"] == pid  # même joueur, même score, toujours hôte
        state = until(ws, "lobby")
        assert state["host"] == pid and len(state["players"]) == 1
