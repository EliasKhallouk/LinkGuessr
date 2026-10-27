"""Test de charge de LinkGuessr, sans dépendance (bibliothèque standard uniquement).

Rejoue un mélange de requêtes réalistes à plusieurs niveaux de concurrence et mesure le débit,
les latences (p50/p95/p99) et les erreurs, tout en relevant le CPU et la RAM de la VM.
Écrit un rapport Markdown.

  # Depuis le PC, à travers Vercel (cache CDN compris) :
  python tools/load_test.py --base https://linkguessr.com/v1 --vm-ssh ek-hub
  # Sur la VM, directement sur l'API (capacité brute, sans cache, quotas levés par le jeton) :
  ADMIN_TOKEN=… python3 tools/load_test.py --base http://127.0.0.1:8000 --local-cpu
"""
import argparse
import json
import os
import random
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

try:  # Windows avec un antivirus qui intercepte le TLS : certificats du système (facultatif)
    import truststore

    os.environ.pop("SSLKEYLOGFILE", None)
    truststore.inject_into_ssl()
except ImportError:
    pass

# Personnes connues (QID) pour les chemins et les fiches ; recherches courantes.
QIDS = ["Q3052772", "Q1835", "Q517", "Q937", "Q7186", "Q21621995", "Q157", "Q2105", "Q692", "Q255", "Q1339", "Q7259",
        "Q8023", "Q615", "Q11613", "Q76", "Q22686", "Q9696", "Q5582", "Q762"]
SEARCHES = ["zidane", "macron", "napoleon", "curie", "mozart", "hugo", "einstein", "pele", "mbappe", "obama",
            "beyonce", "picasso", "moliere", "de gaulle", "piaf", "ronaldo", "messi", "jordan", "chaplin", "dali"]

# (poids, nom, fabrique d'URL relative). Le défi du jour domine, comme lors d'un pic de partage.
SCENARIO = [
    (30, "daily", lambda: "/daily"),
    (10, "stats", lambda: "/stats"),
    (20, "search", lambda: f"/search?q={urllib.parse.quote(random.choice(SEARCHES))}&limit=8"),
    (15, "card", lambda: f"/person/{random.choice(QIDS)}/card"),
    (15, "path", lambda: "/path?from={}&to={}&limit=3".format(*random.sample(QIDS, 2))),
    (10, "random_pair", lambda: f"/random_pair?difficulty={random.choice(['facile', 'moyen'])}"),
]


def pick():
    total = sum(w for w, *_ in SCENARIO)
    r = random.uniform(0, total)
    for weight, name, url in SCENARIO:
        r -= weight
        if r <= 0:
            return name, url()
    return SCENARIO[-1][1], SCENARIO[-1][2]()


class CpuSampler(threading.Thread):
    """Relève le CPU (% occupé) et la RAM disponible de la VM chaque seconde, via /proc."""

    def __init__(self, ssh_host):
        super().__init__(daemon=True)
        self.ssh_host, self.samples, self.stop = ssh_host, [], threading.Event()

    def _read(self):
        cmd = "head -1 /proc/stat; grep MemAvailable /proc/meminfo"
        argv = ["ssh", self.ssh_host, cmd] if self.ssh_host else ["sh", "-c", cmd]
        out = subprocess.run(argv, capture_output=True, text=True, timeout=10).stdout
        cpu_line, mem_line = out.splitlines()[:2]
        values = list(map(int, cpu_line.split()[1:]))
        return sum(values), values[3] + values[4], int(mem_line.split()[1]) // 1024

    def run(self):
        previous = self._read()
        while not self.stop.wait(1.0):
            current = self._read()
            total, idle = current[0] - previous[0], current[1] - previous[1]
            self.samples.append((time.time(), 100.0 * (1 - idle / total) if total else 0.0, current[2]))
            previous = current


def hit(base, headers):
    name, url = pick()
    request = urllib.request.Request(base + url, headers=headers)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            return name, response.status, time.perf_counter() - start, response.headers.get("x-vercel-cache", "")
    except urllib.error.HTTPError as e:
        return name, e.code, time.perf_counter() - start, ""
    except Exception:
        return name, 0, time.perf_counter() - start, ""


def run_level(base, headers, concurrency, seconds):
    results, deadline = [], time.time() + seconds

    def worker():
        while time.time() < deadline:
            results.append(hit(base, headers))

    with ThreadPoolExecutor(concurrency) as pool:
        for _ in range(concurrency):
            pool.submit(worker)
    return results


def pct(values, q):
    if len(values) >= 2:
        return statistics.quantiles(values, n=100)[q - 1] * 1000
    return values[0] * 1000 if values else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", required=True, help="adresse de l'API, ex. https://linkguessr.com/v1")
    parser.add_argument("--levels", default="5,20,50", help="niveaux de concurrence")
    parser.add_argument("--seconds", type=int, default=20, help="durée de chaque niveau")
    parser.add_argument("--vm-ssh", help="hôte ssh de la VM pour relever son CPU (ex. ek-hub)")
    parser.add_argument("--local-cpu", action="store_true", help="relever le CPU local (test lancé sur la VM)")
    parser.add_argument("--out", default=f"load-test-{datetime.now():%Y%m%d-%H%M}.md")
    args = parser.parse_args()

    headers = {"User-Agent": "LinkGuessr-load-test"}
    token = os.environ.get("ADMIN_TOKEN")
    if token:
        headers["X-Admin-Token"] = token  # quotas levés pour mesurer la capacité réelle

    lines = [f"# Test de charge LinkGuessr — {datetime.now():%Y-%m-%d %H:%M}", "",
             f"Cible : `{args.base}` · {args.seconds} s par niveau · quotas levés : {'oui' if token else 'non'}", "",
             "| Concurrence | Requêtes | Req/s | p50 | p95 | p99 | Erreurs | 429 | Cache HIT | CPU VM moyen / max | RAM dispo min |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    details = []
    for level in map(int, args.levels.split(",")):
        sampler = CpuSampler(args.vm_ssh) if (args.vm_ssh or args.local_cpu) else None
        if sampler:
            sampler.start()
        t0 = time.time()
        results = run_level(args.base, headers, level, args.seconds)
        elapsed = time.time() - t0
        if sampler:
            sampler.stop.set()
            sampler.join(timeout=5)
        lat = [r[2] for r in results if 200 <= r[1] < 400]
        errors = sum(1 for r in results if r[1] == 0 or r[1] >= 500)
        limited = sum(1 for r in results if r[1] == 429)
        hits = sum(1 for r in results if r[3] in ("HIT", "STALE"))
        cpu = [s[1] for s in sampler.samples] if sampler else []
        mem = [s[2] for s in sampler.samples] if sampler else []
        vm = f"{statistics.mean(cpu):.0f} % / {max(cpu):.0f} % | {min(mem)} Mo" if cpu else "— | —"
        lines.append(
            f"| {level} | {len(results)} | {len(results) / elapsed:.1f} | {pct(lat, 50):.0f} ms | {pct(lat, 95):.0f} ms "
            f"| {pct(lat, 99):.0f} ms | {errors} | {limited} | {100 * hits / max(1, len(results)):.0f} % | {vm} |")
        by_route = {}
        for name, status, latency, _ in results:
            by_route.setdefault(name, []).append((status, latency))
        details.append(f"\n## Concurrence {level} : détail par route\n\n| Route | Requêtes | p50 | p95 | Codes |\n|---|---|---|---|---|")
        for name, rows in sorted(by_route.items()):
            lats = [lt for st, lt in rows if 200 <= st < 400]
            codes = json.dumps({str(c): sum(1 for st, _ in rows if st == c) for c in sorted({st for st, _ in rows})})
            details.append(f"| {name} | {len(rows)} | {pct(lats, 50):.0f} ms | {pct(lats, 95):.0f} ms | {codes} |")
        print(lines[-1], flush=True)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines + details) + "\n")
    print(f"\nRapport : {args.out}")


if __name__ == "__main__":
    main()
