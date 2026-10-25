from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import policy


def make_client():
    app = FastAPI()
    app.middleware("http")(policy.http_policy)

    @app.get("/search")
    def search():
        return {"ok": True}

    @app.get("/path")
    def path():
        return {"ok": True}

    @app.get("/random_pair")
    def random_pair():
        return {"ok": True}

    @app.get("/person/{qid}")
    def person(qid: str):
        raise HTTPException(404, "inconnu")

    return TestClient(app)


def test_cache_selon_le_prefixe():
    c = make_client()
    assert "s-maxage=86400" in c.get("/search").headers["cache-control"]
    assert c.get("/path?track=true").headers["cache-control"] == "no-store"
    assert c.get("/random_pair").headers["cache-control"] == "no-store"
    assert c.get("/person/Q1").headers["cache-control"] == "no-store"  # erreurs jamais en cache


def test_limite_par_ip_transmise_par_vercel(monkeypatch):
    limiter = policy.RateLimiter(3, 60)
    monkeypatch.setattr(policy, "LIMITS", [("/random_", limiter)])
    c = make_client()
    joueur_a = {"x-vercel-forwarded-for": "1.1.1.1"}
    joueur_b = {"x-vercel-forwarded-for": "2.2.2.2"}
    assert [c.get("/random_pair", headers=joueur_a).status_code for _ in range(4)] == [200, 200, 200, 429]
    assert c.get("/random_pair", headers=joueur_b).status_code == 200  # quota séparé par joueur
