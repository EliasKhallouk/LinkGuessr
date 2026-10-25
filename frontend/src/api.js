// Client de l'API LinkGuessr : un seul endroit pour les URL et le format des réponses.
import { apiUrl } from "./config";

async function get(path, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ""));
  const res = await fetch(apiUrl(qs.toString() ? `${path}?${qs}` : path));
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Erreur ${res.status}`);
  }
  return res.json();
}

async function post(path, body) {
  const res = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Erreur ${res.status}`);
  return data;
}

// Identifiant de session anonyme (pour regrouper les manches d'une même partie dans les logs).
function sessionId() {
  try {
    let id = sessionStorage.getItem("lg-session");
    if (!id) {
      id = crypto.randomUUID();
      sessionStorage.setItem("lg-session", id);
    }
    return id;
  } catch {
    return null;
  }
}

export const api = {
  stats: () => get("/stats"),
  domains: () => get("/domains").then((d) => d.results),
  search: (q, limit = 8) => get("/search", { q, limit }).then((d) => d.results),
  person: (qid) => get(`/person/${qid}`),
  path: (from, to, { mode, limit, track } = {}) => get("/path", { from, to, mode, limit, track }),
  neighbors: (qid, limit = 500) => get(`/neighbors/${qid}`, { limit }).then((d) => d.results),
  randomPair: (opts = {}) => get("/random_pair", opts),
  randomPath: (opts = {}) => get("/random_path", opts),
  top: (by = "popularity", opts = {}) => get("/top", { by, ...opts }).then((d) => d.results),
  popularPairs: (period = "7", limit = 10) => get("/popular_pairs", { period, limit }).then((d) => d.results),
  leaderboard: (game, period = "all", limit = 10) => get("/leaderboard", { game, period, limit }).then((d) => d.entries),
  submitScore: (game, name, score, duration) => post("/scores", { game, name, score, duration }),
  daily: () => get("/daily"),
  dailyGuess: (device, qid = null) => post("/daily/guess", { device, qid }),
  // Les logs ne doivent jamais gêner le jeu : erreurs ignorées.
  logEvent: (game, payload) => post("/events", { game, session: sessionId(), payload }).catch(() => {}),
};

// Miniature d'une image Wikimedia Commons (nom de fichier tel que stocké dans Wikidata).
export function commonsThumb(file, width = 96) {
  if (!file) return null;
  return `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(file)}?width=${width}`;
}

export function wikiUrl(title) {
  return `https://fr.wikipedia.org/wiki/${encodeURIComponent(title || "")}`;
}

export function lifespan(p) {
  if (!p?.birth_year) return "";
  const fmt = (y) => (y < 0 ? `${-y} av. J.-C.` : `${y}`);
  return p.death_year ? `${fmt(p.birth_year)} – ${fmt(p.death_year)}` : `né(e) en ${fmt(p.birth_year)}`;
}
