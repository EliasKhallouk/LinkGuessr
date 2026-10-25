import argparse
from pathlib import Path

from . import build, download, entities, graph, humans, links, pageviews, pages, refs
from .config import work_path


def main() -> None:
    parser = argparse.ArgumentParser(prog="lg", description="Pipeline de données LinkGuessr")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("download", help="télécharge les dumps frwiki")
    p.add_argument("what", choices=["sql", "xml", "all"], nargs="?", default="sql")

    sub.add_parser("pages", help="articles, QID et redirections (dumps SQL)")
    sub.add_parser("humans", help="filtre les articles de personnes (WDQS)")

    p = sub.add_parser("entities", help="fiches Wikidata complètes des personnes")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--limit", type=int, help="ne traiter que les N premiers QID (test)")

    p = sub.add_parser("links", help="liens entre personnes depuis le texte des articles (dump XML)")
    p.add_argument("--workers", type=int, help="processus en parallèle (défaut : tous les cœurs)")

    p = sub.add_parser("refs", help="lieux, professions, clubs, prix... cités par les fiches")
    p.add_argument("--workers", type=int, default=2)

    p = sub.add_parser("pageviews-dump", help="extrait les vues frwiki des fichiers mensuels (à lancer sur la VM)")
    p.add_argument("--out", type=Path, help="dossier de sortie (défaut : work/pageviews_dumps)")
    p = sub.add_parser("pageviews", help="joint les vues mensuelles aux biographies")
    p.add_argument("--dir", type=Path, help="dossier des fichiers mensuels (défaut : work/pageviews_dumps)")
    sub.add_parser("build", help="assemble fiches, faits et relations")
    sub.add_parser("graph", help="identifiants, arêtes pondérées et métriques (tables finales)")

    p = sub.add_parser("load", help="charge les tables finales dans Postgres (DATABASE_URL)")
    p.add_argument("--dir", type=Path, help="dossier des tables finales (défaut : work/final)")

    args = parser.parse_args()
    if args.cmd == "download":
        files = {"sql": download.SQL_DUMPS, "xml": download.XML_DUMPS,
                 "all": download.SQL_DUMPS + download.XML_DUMPS}[args.what]
        download.download(files)
    elif args.cmd == "pages":
        pages.build_pages()
    elif args.cmd == "humans":
        humans.find_humans()
    elif args.cmd == "entities":
        entities.fetch_human_entities(args.workers, args.limit)
    elif args.cmd == "links":
        links.extract_links(args.workers)
    elif args.cmd == "refs":
        refs.fetch_refs(args.workers)
    elif args.cmd == "pageviews-dump":
        pageviews.dump_monthly(args.out)
    elif args.cmd == "pageviews":
        pageviews.build_pageviews(args.dir)
    elif args.cmd == "build":
        build.build()
    elif args.cmd == "graph":
        graph.build_graph()
    elif args.cmd == "load":
        from . import load  # psycopg n'est utile que sur la machine qui charge la base
        load.load(args.dir or work_path("final"))


if __name__ == "__main__":
    main()
