import os
from pathlib import Path

WIKI = "frwiki"
DUMP_DATE = os.getenv("LG_DUMP_DATE", "20261001")

DATA_DIR = Path(os.getenv("LG_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
DUMPS_DIR = DATA_DIR / "dumps" / DUMP_DATE
WORK_DIR = DATA_DIR / "work" / DUMP_DATE

# Politique Wikimedia : User-Agent identifiable avec un moyen de contact.
USER_AGENT = "LinkGuessrPipeline/0.1 (https://linkguessr.duckdns.org)"


def dump_name(suffix: str) -> str:
    return f"{WIKI}-{DUMP_DATE}-{suffix}"


def dump_path(suffix: str) -> Path:
    return DUMPS_DIR / dump_name(suffix)


def work_path(name: str) -> Path:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    return WORK_DIR / name
