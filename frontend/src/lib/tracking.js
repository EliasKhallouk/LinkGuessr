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

export function track(game, event, data = {}) {
  const payload = { event, src: source(), ...data };
  if (event === "start") {
    const key = `${game}:${data.round ?? ""}`;
    if (started.has(key)) return;
    started.add(key);
  }
  api.logEvent(game, payload);
  try {
    window.umami?.track(`${game}_${event}`, { src: payload.src || "(direct)" });
  } catch { /* Umami bloqué ou absent : sans importance */ }
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
