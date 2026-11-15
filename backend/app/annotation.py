"""Outil d'annotation du Lab : page /annoter et routes /annot/* (jeu d'or du classifieur de liens).

Chaque annotateur a un jeton (ANNOT_TOKENS). Portée « tout » : toutes les phrases, d'abord celles hors accord
(avec la proposition du modèle), puis les 300 de l'accord à l'aveugle. Portée « accord » : ces 300 seulement.
Les phrases sont chargées et les annotations exportées en ligne de commande (python -m app.annotation).
"""
import argparse
import json
import secrets
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from .config import ANNOT_TOKENS
from .core import pool
from .policy import RateLimiter

router = APIRouter()
token_limiter = RateLimiter(30, 600)  # essais de jeton invalides, par IP
PAGE = Path(__file__).resolve().parent / "static" / "annoter.html"

# Grille du guide (lab/annotation/guide.md), dans l'ordre d'affichage.
FAMILIES = {
    "Personnel": ["famille", "couple", "proches"],
    "Travail": ["formation", "collaboration", "hierarchie"],
    "Conflit": ["competition", "lutte", "critique"],
    "Par les œuvres": ["sujet", "materiau"],
    "Mention": ["source", "comparaison", "co_mention"],
    "Inclassable": ["inclassable"],
}
LABELS = [l for ls in FAMILIES.values() for l in ls]
ALONE = {"co_mention", "inclassable"}
COTOYES = {"oui", "non", "incertain"}


def check_label(labels: list[str], cotoyes: str | None, wrong: bool) -> str | None:
    """Message d'erreur si l'annotation ne respecte pas le guide, sinon None."""
    if wrong:
        return None  # mauvaise personne ou phrase cassée : rien d'autre à remplir
    if not labels:
        return "Choisis au moins un type de lien."
    if any(l not in LABELS for l in labels) or len(set(labels)) != len(labels):
        return "Type de lien inconnu."
    if len(labels) > 1 and ALONE & set(labels):
        return "« co-mention » et « inclassable » s'emploient seuls."
    if len(labels) > 3:
        return "Trois types au plus."
    if cotoyes not in COTOYES:
        return "Réponds à « se sont-ils côtoyés ? »."
    return None


def annotator(request: Request, token: str) -> dict:
    who = ANNOT_TOKENS.get(token)
    if not who:
        token_limiter.check(request)
        raise HTTPException(401, "Lien d'annotation invalide.")
    return who


def _order(scope: str) -> str:
    # Hors accord d'abord (on se fait la main avec les propositions), puis l'accord à l'aveugle.
    return "WHERE accord" if scope == "accord" else ""


@router.get("/annoter", include_in_schema=False)
def page():
    return FileResponse(PAGE, headers={"Cache-Control": "no-cache", "X-Robots-Tag": "noindex"})


@router.get("/annot/item")
def item(request: Request, t: str = Query(..., max_length=100), id: int | None = None):
    """Une phrase (la première non annotée par défaut), avec la progression et l'annotation existante."""
    who = annotator(request, t)
    where = _order(who["scope"])
    with pool.connection() as conn:
        ids = [r[0] for r in conn.execute(f"SELECT id FROM app.annot_item {where} ORDER BY accord, id").fetchall()]
        done = {r[0]: r for r in conn.execute(
            "SELECT item_id, labels, cotoyes, wrong, doubt, comment FROM app.annot_label WHERE annotator = %s",
            (who["name"],)).fetchall()}
        if not ids:
            raise HTTPException(404, "Aucune phrase à annoter pour l'instant.")
        if id is None:
            id = next((i for i in ids if i not in done), None)
            if id is None:
                return {"finished": True, "total": len(ids), "done": len(ids), "annotator": who["name"]}
        if id not in ids:
            raise HTTPException(404, "Phrase introuvable.")
        accord, data, suggestion = conn.execute(
            "SELECT accord, data, suggestion FROM app.annot_item WHERE id = %s", (id,)).fetchone()
    pos = ids.index(id)
    prev = done.get(id)
    return {
        "id": id, "annotator": who["name"], "total": len(ids), "done": len(done), "position": pos + 1,
        "prev_id": ids[pos - 1] if pos else None, "next_id": ids[pos + 1] if pos + 1 < len(ids) else None,
        "item": data, "accord": accord,
        "suggestion": None if accord else suggestion,
        "label": dict(zip(["labels", "cotoyes", "wrong", "doubt", "comment"], prev[1:])) if prev else None,
        "families": FAMILIES,
    }


class LabelIn(BaseModel):
    t: str = Field(..., max_length=100)
    id: int
    labels: list[str] = Field(default_factory=list, max_length=5)
    cotoyes: str | None = None
    wrong: bool = False
    doubt: bool = False
    comment: str | None = Field(None, max_length=1000)
    seconds: int | None = Field(None, ge=0, le=86_400)


@router.post("/annot/label")
def save(body: LabelIn, request: Request):
    who = annotator(request, body.t)
    error = check_label(body.labels, body.cotoyes, body.wrong)
    if error:
        raise HTTPException(400, error)
    with pool.connection() as conn:
        row = conn.execute("SELECT accord FROM app.annot_item WHERE id = %s", (body.id,)).fetchone()
        if not row or (who["scope"] == "accord" and not row[0]):
            raise HTTPException(404, "Phrase introuvable.")
        conn.execute(
            """INSERT INTO app.annot_label (item_id, annotator, labels, cotoyes, wrong, doubt, comment, seconds)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (item_id, annotator) DO UPDATE SET labels = EXCLUDED.labels, cotoyes = EXCLUDED.cotoyes,
                 wrong = EXCLUDED.wrong, doubt = EXCLUDED.doubt, comment = EXCLUDED.comment,
                 seconds = coalesce(app.annot_label.seconds, 0) + coalesce(EXCLUDED.seconds, 0), updated_at = now()""",
            (body.id, who["name"], [] if body.wrong else body.labels, None if body.wrong else body.cotoyes,
             body.wrong, body.doubt, (body.comment or "").strip() or None, body.seconds),
        )
    return {"ok": True}


# --- Ligne de commande (sur la VM) ---------------------------------------------------------

def load(path: Path) -> None:
    """Charge les phrases (items.jsonl du Lab). Recharger garde les annotations des phrases déjà là."""
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    with pool.connection() as conn:
        for r in rows:
            conn.execute(
                """INSERT INTO app.annot_item (id, accord, data) VALUES (%s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET accord = EXCLUDED.accord, data = EXCLUDED.data""",
                (r["ordre"], r["accord"], Jsonb(r)))
    print(f"{len(rows)} phrases chargées")


def suggest(path: Path) -> None:
    """Propositions du modèle : une ligne JSON par phrase, {"ordre", "labels", "cotoyes"}."""
    n = 0
    with pool.connection() as conn:
        for l in path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                s = json.loads(l)
                n += conn.execute("UPDATE app.annot_item SET suggestion = %s WHERE id = %s AND NOT accord",
                                  (Jsonb({"labels": s["labels"], "cotoyes": s.get("cotoyes")}), s["ordre"])).rowcount
    print(f"{n} propositions enregistrées")


def export() -> None:
    with pool.connection() as conn:
        for r in conn.execute(
                """SELECT l.item_id, l.annotator, l.labels, l.cotoyes, l.wrong, l.doubt, l.comment, l.seconds,
                          l.updated_at, i.accord, i.suggestion
                   FROM app.annot_label l JOIN app.annot_item i ON i.id = l.item_id ORDER BY l.item_id, l.annotator"""):
            keys = ["ordre", "annotator", "labels", "cotoyes", "wrong", "doubt", "comment", "seconds",
                    "updated_at", "accord", "suggestion"]
            sys.stdout.write(json.dumps(dict(zip(keys, r)), ensure_ascii=False, default=str) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.annotation", description="Annotation du Lab")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("load", help="charge les phrases").add_argument("file", type=Path)
    sub.add_parser("suggest", help="charge les propositions du modèle").add_argument("file", type=Path)
    sub.add_parser("export", help="annotations en JSON, une ligne par annotation")
    sub.add_parser("jeton", help="génère un jeton d'annotateur")
    args = parser.parse_args()
    if args.cmd == "jeton":
        print(secrets.token_urlsafe(24))
        return
    pool.open()
    {"load": lambda: load(args.file), "suggest": lambda: suggest(args.file), "export": export}[args.cmd]()


if __name__ == "__main__":
    main()
