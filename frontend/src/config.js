// Adresse de l'API. Par défaut celle de la VM, y compris en développement local.
// Pour une API lancée sur le PC : créer frontend/.env.local avec
// VITE_API_BASE_URL=http://127.0.0.1:8000
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "https://linkguessr.duckdns.org";

export const apiUrl = (path) => `${API_BASE_URL}${path.startsWith("/") ? "" : "/"}${path}`;
