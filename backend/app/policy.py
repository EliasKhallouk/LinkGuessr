"""Politique HTTP commune : identification du client, limitation de débit et cache CDN.

Le site appelle l'API via Vercel (link-guessr.vercel.app/v1/…) : Vercel garde en cache les
réponses qui portent un `s-maxage`, ce qui protège la VM (1 cœur) en cas d'affluence.
"""
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse


def client_ip(request: Request) -> str:
    """IP du joueur. Derrière Vercel puis Nginx, l'adresse vue est celle de Vercel : on lit
    l'en-tête transmis par Vercel (ou le premier maillon de X-Forwarded-For).
    Un appel direct à la VM peut falsifier ces en-têtes : il ne fait alors que se répartir
    son propre quota, ce qui reste acceptable pour un simple limiteur."""
    for header in ("x-vercel-forwarded-for", "x-forwarded-for"):
        if value := request.headers.get(header):
            return value.split(",")[0].strip()
    return request.client.host if request.client else "?"


class RateLimiter:
    """Fenêtre glissante en mémoire, par IP (rien n'est stocké sur disque)."""

    def __init__(self, max_calls: int, per_seconds: int):
        self.max_calls, self.per_seconds = max_calls, per_seconds
        self.calls: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        calls = self.calls[key]
        while calls and now - calls[0] > self.per_seconds:
            calls.popleft()
        if len(calls) >= self.max_calls:
            return False
        calls.append(now)
        if len(self.calls) > 50_000:  # garde-fou mémoire : on oublie les IP inactives
            for k in [k for k, v in self.calls.items() if not v or now - v[-1] > self.per_seconds]:
                del self.calls[k]
        return True

    def check(self, request: Request) -> None:
        from fastapi import HTTPException
        if not self.allow(client_ip(request)):
            raise HTTPException(429, "Trop de requêtes, réessayez dans un instant.")


# Routes coûteuses (calcul de graphe ou requêtes lourdes) : par IP et par minute.
LIMITS = [
    ("/random_", RateLimiter(60, 60)),
    ("/path", RateLimiter(120, 60)),
    ("/neighbors/", RateLimiter(120, 60)),
    ("/person/", RateLimiter(120, 60)),
    ("/search", RateLimiter(300, 60)),
]

# Cache CDN (Vercel) des GET identiques pour tous. Les routes qui fixent elles-mêmes
# leur Cache-Control (défi du jour, carte, archive) sont laissées telles quelles.
DAY = "public, max-age=300, s-maxage=86400, stale-while-revalidate=86400"
HOUR = "public, max-age=60, s-maxage=3600, stale-while-revalidate=3600"
CACHE = [
    ("/random_", "no-store"),
    ("/admin", "no-store"),
    ("/health", "no-store"),
    ("/daily/guess", "no-store"),
    ("/person/", DAY),
    ("/neighbors/", DAY),
    ("/domains", DAY),
    ("/search", DAY),
    ("/path", DAY),
    ("/stats", HOUR),
    ("/top", HOUR),
    ("/popular_pairs", "public, max-age=60, s-maxage=300"),
    ("/leaderboard", "public, max-age=30, s-maxage=30"),
]


async def http_policy(request: Request, call_next):
    path = request.url.path
    for prefix, limiter in LIMITS:
        if path.startswith(prefix) and not limiter.allow(client_ip(request)):
            return JSONResponse({"detail": "Trop de requêtes, réessayez dans un instant."}, status_code=429,
                                headers={"Retry-After": "30", "Cache-Control": "no-store"})
    response = await call_next(request)
    if request.method == "GET" and "cache-control" not in response.headers and response.status_code < 400:
        # Une exploration comptée dans les « paires les plus demandées » ne doit pas être servie par le cache.
        rule = "no-store" if request.query_params.get("track") == "true" else next(
            (value for prefix, value in CACHE if path.startswith(prefix)), None)
        if rule:
            response.headers["Cache-Control"] = rule
    elif response.status_code >= 400 and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    return response
