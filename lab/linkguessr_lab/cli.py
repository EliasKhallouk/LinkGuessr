import argparse

from . import etalonnage


def main() -> None:
    parser = argparse.ArgumentParser(prog="lab", description="Analyses du Lab LinkGuessr")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("etalonnage", help="étape 0 : vrais volumes des données et temps d'un parcours en largeur")
    p.add_argument("--dump", default="20261001", help="date du dump (dossier pipeline/data/work/<dump>)")
    p.add_argument("--sources", type=int, default=20, help="parcours chronométrés par bibliothèque")

    p = sub.add_parser("tirage", help="tirage stratifié des phrases du jeu d'or (annotation)")
    p.add_argument("--dump", default="20261001")

    args = parser.parse_args()
    if args.command == "etalonnage":
        etalonnage.run(args.dump, args.sources)
    elif args.command == "tirage":
        from .typing import sample
        sample.run(args.dump)
