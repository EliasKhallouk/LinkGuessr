// Mesure d'audience sans cookie : événements de jeu envoyés à notre API (tableau de bord /admin)
// et à Umami (fréquentation). Aucune donnée personnelle ; la source d'arrivée (utm_source) est rattachée.
// Convention des paramètres et liste des événements : docs/tracking.md.
import { api } from "../api";
import { load, save } from "./storage";

const SRC_KEY = "lg-src";

// Source d'arrivée : premier utm_source vu pendant la session (ex. reddit, partage, duel).
// ?src= : ancienne convention, encore présente dans les liens déjà partagés.
export function captureSource() {
  try {
    const params = new URLSearchParams(window.location.search);
    const src = params.get("utm_source") || params.get("src");
    if (src && !sessionStorage.getItem(SRC_KEY)) sessionStorage.setItem(SRC_KEY, src.slice(0, 40));
  } catch { /* stockage indisponible : pas de source */ }
  cleanUrlAfterPageview();
}

// Retire utm_* (et l'ancien src) de la barre d'adresse, pour qu'une adresse copiée et renvoyée à un ami
// ne compte pas une seconde fois pour la même source. History.prototype : Umami intercepte
// history.replaceState et compterait sinon une nouvelle page vue.
function cleanUrl() {
  const url = new URL(window.location.href);
  const keys = [...url.searchParams.keys()].filter((k) => k.startsWith("utm_") || k === "src");
  if (!keys.length) return;
  keys.forEach((k) => url.searchParams.delete(k));
  History.prototype.replaceState.call(window.history, window.history.state, "", url);
}

// On attend qu'Umami ait envoyé la première page vue (data-before-send dans index.html : la charge
// utile, URL comprise, est alors figée). Umami bloqué ou désactivé : on nettoie quand même, 3 s après le chargement.
function cleanUrlAfterPageview() {
  window.lgBeforeSend = (type, payload) => {
    if (type === "event" && !payload?.name) setTimeout(cleanUrl, 0);
    return payload;
  };
  const fallback = () => setTimeout(cleanUrl, 3000);
  if (document.readyState === "complete") fallback();
  else window.addEventListener("load", fallback, { once: true });
}

export function source() {
  try {
    return sessionStorage.getItem(SRC_KEY) || null;
  } catch {
    return null;
  }
}

// Une fois par partie : évite de compter deux « start » si le joueur clique deux fois.
const started = new Set();

// Événements Umami : noms fixes, le jeu en propriété (mêmes valeurs que utm_campaign). Voir docs/tracking.md.
export const CAMPAIGNS = { explore: "explorer", guess_who: "qui-est-cache", relay: "relier", guess_count: "combien",
  daily: "defi-du-jour" };
const UMAMI_EVENTS = { start: "partie_debut", finish: "partie_fin", duel_open: "duel_ouvert" };

// Résultat et nombre d'essais d'une fin de partie, à partir des données envoyées à l'API.
function outcome(game, data) {
  if (game === "relay") return { resultat: "gagne", essais: data.steps };
  if (game === "guess_count") return { resultat: "termine", essais: data.answered };
  return { resultat: (data.found ?? data.solved) ? "gagne" : "perdu", essais: data.tries };
}

// Seulement des valeurs de la liste de docs/tracking.md : ni identifiant, ni personne jouée.
export function trackUmami(game, name, data = {}) {
  try {
    window.umami?.track(name, { jeu: CAMPAIGNS[game] || game, source: source() || "direct", ...data });
  } catch { /* Umami bloqué ou absent : sans importance */ }
}

export function track(game, event, data = {}) {
  const payload = { event, src: source(), ...data };
  if (event === "start") {
    const key = `${game}:${data.round ?? ""}`;
    if (started.has(key)) return;
    started.add(key);
  }
  api.logEvent(game, payload);
  // Partages : envoyés à Umami par ShareButton (partage_clic), avec la méthode.
  if (UMAMI_EVENTS[event]) trackUmami(game, UMAMI_EVENTS[event], event === "finish" ? outcome(game, data) : {});
}

export function newRound(game) {
  for (const key of started) if (key.startsWith(`${game}:`)) started.delete(key);
}

// Un seul retour par jeu et par jour, pour ne pas solliciter le joueur à chaque partie.
export function shouldAskFeedback(game) {
  const today = new Date().toISOString().slice(0, 10);
  return load(`lg-feedback-${game}`) !== today;
}

export function markFeedbackAsked(game) {
  save(`lg-feedback-${game}`, new Date().toISOString().slice(0, 10));
}
