// Adresse de l'API. Par défaut « /v1 » : Vercel la relaie vers la VM et met en cache les réponses
// identiques pour tous (voir vercel.json). En local, Vite fait le même relais (vite.config.js).
// Pour viser une autre API : VITE_API_BASE_URL dans frontend/.env.local.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "/v1";

// Salons en direct : WebSocket directement vers la VM (Vercel ne relaie pas les WebSockets), par
// live.linkguessr.com (CNAME) : jamais duckdns.org dans le code du site, dont les pare-feu se méfient.
export const LIVE_URL = import.meta.env.VITE_LIVE_URL?.replace(/\/$/, "") || "wss://live.linkguessr.com/live";

export const apiUrl = (path) => `${API_BASE_URL}${path.startsWith("/") ? "" : "/"}${path}`;
