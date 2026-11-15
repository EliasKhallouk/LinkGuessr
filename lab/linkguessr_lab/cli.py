import argparse
import sys
from pathlib import Path

from . import etalonnage


def main() -> None:
    parser = argparse.ArgumentParser(prog="lab", description="Analyses du Lab LinkGuessr")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("etalonnage", help="étape 0 : vrais volumes des données et temps d'un parcours en largeur")
    p.add_argument("--dump", default="20261001", help="date du dump (dossier pipeline/data/work/<dump>)")
    p.add_argument("--sources", type=int, default=20, help="parcours chronométrés par bibliothèque")

    p = sub.add_parser("tirage", help="tirage stratifié des phrases du jeu d'or (annotation)")
    p.add_argument("--dump", default="20261001")

    p = sub.add_parser("dataset", help="jeu de données d'entraînement (après pull_annotations.sh)")
    p.add_argument("--dump", default="20261001")

    p = sub.add_parser("score", help="note un fichier de prédictions (JSONL) sur val, ou test à la fin")
    p.add_argument("predictions", type=Path)
    p.add_argument("--dump", default="20261001")
    p.add_argument("--split", default="val", choices=["train", "val", "test"])
    p.add_argument("--pondere", action="store_true", help="pondère par les poids du tirage (estimation sur les 6 M)")

    p = sub.add_parser("accord", help="accord entre les deux annotateurs sur les 300 phrases de l'accord")
    p.add_argument("--dump", default="20261001")

    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # console Windows en cp1252
    if args.command == "etalonnage":
        etalonnage.run(args.dump, args.sources)
    elif args.command == "tirage":
        from .typing import sample
        sample.run(args.dump)
    elif args.command == "dataset":
        from .typing import dataset
        dataset.run(args.dump)
    elif args.command == "score":
        from .typing import scores
        scores.run(args.dump, args.predictions, args.split, args.pondere)
    elif args.command == "accord":
        from .typing import accord
        accord.run(args.dump)
