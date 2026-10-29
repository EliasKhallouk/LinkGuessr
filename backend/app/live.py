"""Salons en direct : « Qui est caché ? » en QCM, à plusieurs, en temps réel.

Un joueur crée un salon (POST /live/rooms → code de 4 caractères) et partage /salon/<code> ; chacun s'y
connecte ensuite en WebSocket (/live/<code>), directement sur la VM : Vercel ne relaie pas les WebSockets.
Les salons vivent en mémoire (l'API tourne en un seul processus) : rien n'est enregistré, pas même les
pseudos, et un redémarrage de l'API ferme les salons en cours.

Une partie : 10 manches de 20 s, la même énigme pour tous au même moment, une seule réponse par manche.
Bonne réponse : de 1 000 points (immédiate) à 500 (dernière seconde), multipliés selon le niveau.
Le serveur garde la réponse jusqu'à la fin de la manche et compte les points lui-même.

Messages (JSON). Joueur → serveur : join {token, pseudo} (en premier), settings {niveau, epoque} (hôte),
start (hôte, aussi pour la revanche), answer {qid}. Serveur → joueur : welcome {pid}, state (l'état du
salon, à chaque changement), error {message, fatal}.
"""
import asyncio
import random
import re
import secrets
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .config import CORS_ORIGIN_REGEX, CORS_ORIGINS
from .eras import ERAS
from .game import normalize_name
from .moderation import is_offensive
from .policy import RateLimiter, client_ip

router = APIRouter()

ROUNDS = 10
ROUND_SECONDS = 20
REVEAL_SECONDS = 7
MAX_PLAYERS = 8
MAX_ROOMS = 200
EMPTY_TTL = 120          # salon vide : supprimé après 2 min
IDLE_TTL = 2 * 3600      # salon sans activité : supprimé après 2 h
CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans 0/O ni 1/I, faciles à confondre
MULT = {"facile": 1, "moyen": 2, "difficile": 4, "extreme": 6, "humain": 10}
ORIGINS = {"https://linkguessr.com", "https://www.linkguessr.com", *CORS_ORIGINS}
create_limiter = RateLimiter(10, 60)


def points(level: str, elapsed: float) -> int:
    """Bonne réponse : 1 000 points tout de suite, 500 à la dernière seconde, fois le multiplicateur du niveau."""
    return round(MULT[level] * (1000 - 500 * min(max(elapsed, 0), ROUND_SECONDS) / ROUND_SECONDS))


@dataclass
class Player:
    pid: str                 # identifiant public (montré aux autres)
    token: str               # secret du navigateur, pour revenir dans le salon après un rechargement
    pseudo: str
    score: int = 0
    ws: WebSocket | None = None


@dataclass
class Room:
    code: str
    niveau: str = "moyen"
    epoque: str = "aujourdhui"
    host: str | None = None
    players: dict[str, Player] = field(default_factory=dict)   # par token
    phase: str = "lobby"     # lobby, starting (première énigme en préparation), question, reveal, end
    round: int = 0
    puzzle: dict | None = None
    started: float = 0.0
    deadline: float = 0.0
    answers: dict[str, tuple[str, float]] = field(default_factory=dict)  # pid -> (qid, secondes)
    last: dict[str, dict] = field(default_factory=dict)                  # pid -> résultat de la manche
    error: str | None = None
    task: asyncio.Task | None = None
    all_answered: asyncio.Event = field(default_factory=asyncio.Event)
    touched: float = field(default_factory=time.monotonic)
    empty_since: float | None = field(default_factory=time.monotonic)

    def connected(self) -> list[Player]:
        return [p for p in self.players.values() if p.ws is not None]


rooms: dict[str, Room] = {}


def sweep() -> None:
    now = time.monotonic()
    for code, room in list(rooms.items()):
        if (room.empty_since and now - room.empty_since > EMPTY_TTL) or now - room.touched > IDLE_TTL:
            if room.task:
                room.task.cancel()
            del rooms[code]


class RoomIn(BaseModel):
    niveau: str = Field("moyen", pattern=f"^({'|'.join(MULT)})$")
    epoque: str = Field("aujourdhui", pattern=f"^({'|'.join(ERAS)})$")


@router.post("/live/rooms")
async def create_room(body: RoomIn, request: Request):
    create_limiter.check(request)
    sweep()
    if len(rooms) >= MAX_ROOMS:
        raise HTTPException(503, "Trop de salons ouverts en ce moment, réessaie dans quelques minutes.")
    code = "".join(secrets.choice(CODE_CHARS) for _ in range(4))
    while code in rooms:
        code = "".join(secrets.choice(CODE_CHARS) for _ in range(4))
    rooms[code] = Room(code, niveau=body.niveau, epoque=body.epoque)
    return {"code": code}


def public_puzzle(room: Room) -> dict | None:
    """L'énigme sans la réponse pendant la manche ; avec la réponse et ses liens une fois la manche finie."""
    q = room.puzzle
    if q is None or room.phase not in ("question", "reveal"):
        return None
    out = {k: q[k] for k in ("path", "masked_index", "persons", "hops", "choices")}
    if room.phase == "reveal":
        out.update(answer=q["answer"], answer_hops=q["answer_hops"])
    return out


def snapshot(room: Room) -> dict:
    show_last = room.phase in ("reveal", "end")
    players = sorted(room.players.values(), key=lambda p: -p.score)
    return {
        "t": "state", "code": room.code, "phase": room.phase, "host": room.host, "niveau": room.niveau,
        "epoque": room.epoque, "round": room.round, "rounds": ROUNDS, "error": room.error,
        "remaining_ms": max(0, round((room.deadline - time.monotonic()) * 1000)) if room.phase in ("question", "reveal") else 0,
        "round_ms": ROUND_SECONDS * 1000,
        "players": [{"pid": p.pid, "pseudo": p.pseudo, "score": p.score, "connected": p.ws is not None,
                     "answered": p.pid in room.answers, **({"last": room.last.get(p.pid)} if show_last else {})}
                    for p in players],
        "puzzle": public_puzzle(room),
    }


async def broadcast(room: Room) -> None:
    message = snapshot(room)
    for p in room.connected():
        try:
            await p.ws.send_json(message)
        except Exception:  # connexion coupée entre-temps : géré à la déconnexion
            pass


async def run_game(room: Room) -> None:
    """Une partie : 10 manches, l'énigme suivante préparée pendant la manche en cours (hors de la boucle,
    le calcul touche la base)."""
    from .main import seeded_puzzle
    seed, index = random.randrange(2**31), 0

    async def next_puzzle():
        nonlocal index
        for _ in range(5):  # énigme introuvable à ce rang : on passe au suivant
            i, index = index, index + 1
            try:
                return await asyncio.to_thread(seeded_puzzle, room.niveau, room.epoque, seed, i, n_choices=4)
            except HTTPException:
                continue
        raise RuntimeError("aucune énigme")

    for p in room.players.values():
        p.score = 0
    room.last, room.error = {}, None
    try:
        pending = asyncio.create_task(next_puzzle())
        for rnd in range(1, ROUNDS + 1):
            room.puzzle = await pending
            if rnd < ROUNDS:
                pending = asyncio.create_task(next_puzzle())
            room.round, room.answers, room.phase = rnd, {}, "question"
            room.all_answered = asyncio.Event()
            room.started = time.monotonic()
            room.deadline = room.started + ROUND_SECONDS
            await broadcast(room)
            try:
                await asyncio.wait_for(room.all_answered.wait(), ROUND_SECONDS)
            except TimeoutError:
                pass
            answer = room.puzzle["answer"]["qid"]
            room.last = {}
            for p in room.players.values():
                qid, elapsed = room.answers.get(p.pid, (None, None))
                gained = points(room.niveau, elapsed) if qid == answer else 0
                p.score += gained
                room.last[p.pid] = {"qid": qid, "correct": qid == answer, "points": gained}
            room.phase, room.deadline = "reveal", time.monotonic() + REVEAL_SECONDS
            await broadcast(room)
            await asyncio.sleep(REVEAL_SECONDS)
        room.phase = "end"
    except asyncio.CancelledError:
        raise
    except Exception:
        room.phase, room.error = "end", "Impossible de préparer les énigmes, relance une partie."
    room.puzzle, room.touched = None, time.monotonic()
    await broadcast(room)


def origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    if origin in ORIGINS:
        return True
    return bool(CORS_ORIGIN_REGEX and re.fullmatch(CORS_ORIGIN_REGEX, origin))


async def handle(room: Room, player: Player, msg: dict) -> None:
    """Un message d'un joueur ; les messages hors de propos (pas l'hôte, mauvaise phase…) sont ignorés."""
    kind, is_host = msg.get("t"), player.pid == room.host
    if kind == "settings" and is_host and room.phase in ("lobby", "end"):
        if msg.get("niveau") in MULT:
            room.niveau = msg["niveau"]
        if msg.get("epoque") in ERAS:
            room.epoque = msg["epoque"]
    elif kind == "start" and is_host and room.phase in ("lobby", "end"):
        room.phase, room.round = "starting", 0
        room.task = asyncio.create_task(run_game(room))
    elif kind == "answer" and room.phase == "question" and player.pid not in room.answers:
        qid = msg.get("qid")
        if not any(c["qid"] == qid for c in room.puzzle["choices"]):
            return
        room.answers[player.pid] = (qid, time.monotonic() - room.started)
        if all(p.pid in room.answers for p in room.connected()):
            room.all_answered.set()
    else:
        return
    room.touched = time.monotonic()
    await broadcast(room)


@router.websocket("/live/{code}")
async def live(ws: WebSocket, code: str):
    if not origin_allowed(ws.headers.get("origin")):
        await ws.close(code=1008)
        return
    await ws.accept()
    sweep()
    room = rooms.get(code.upper())
    if room is None:
        await ws.send_json({"t": "error", "fatal": True, "message": "Ce salon n'existe pas ou est fermé."})
        await ws.close()
        return
    try:
        join = await asyncio.wait_for(ws.receive_json(), 10)
    except (TimeoutError, WebSocketDisconnect, ValueError):
        await ws.close()
        return
    token = str(join.get("token", ""))[:64]
    player = room.players.get(token) if len(token) >= 16 else None
    if player is None:
        pseudo = normalize_name(str(join.get("pseudo", "")))
        error = ("Ce pseudo n'est pas accepté, choisis-en un autre." if is_offensive(pseudo)
                 else "Le salon est complet (8 joueurs)." if len(room.players) >= MAX_PLAYERS
                 else "Pseudo invalide." if len(token) < 16 else None)
        if error:
            await ws.send_json({"t": "error", "fatal": True, "message": error})
            await ws.close()
            return
        taken = {p.pseudo for p in room.players.values()}
        base, n = pseudo, 2
        while pseudo in taken:
            pseudo, n = f"{base[:13]} {n}", n + 1
        player = Player(pid=secrets.token_hex(4), token=token, pseudo=pseudo)
        room.players[token] = player
    elif player.ws is not None:  # même joueur dans un autre onglet : l'ancien est prévenu et remplacé
        try:
            await player.ws.send_json({"t": "error", "fatal": True,
                                       "message": "Tu as ouvert ce salon dans un autre onglet : la partie continue là-bas."})
            await player.ws.close()
        except Exception:
            pass
    player.ws, room.empty_since, room.touched = ws, None, time.monotonic()
    if room.host is None or all(p.pid != room.host or p.ws is None for p in room.players.values()):
        room.host = player.pid
    await ws.send_json({"t": "welcome", "pid": player.pid})
    await broadcast(room)
    try:
        while True:
            msg = await ws.receive_json()
            if isinstance(msg, dict):
                await handle(room, player, msg)
    except (WebSocketDisconnect, ValueError, RuntimeError):
        pass
    finally:
        if player.ws is ws:
            player.ws = None
            if not room.connected():
                room.empty_since = time.monotonic()
            elif room.host == player.pid:  # l'hôte est parti : le joueur connecté suivant prend la main
                room.host = room.connected()[0].pid
            if room.phase == "question" and room.connected() and all(p.pid in room.answers for p in room.connected()):
                room.all_answered.set()
            await broadcast(room)
