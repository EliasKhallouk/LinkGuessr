// Single source of truth for backend API base URL
// Override via environment variable VITE_API_BASE_URL
// Example: create .env in frontend folder with:
// VITE_API_BASE_URL=https://your-backend.example.com

// Heuristic: if no explicit base URL is provided and we're on localhost, default to local FastAPI
let defaultBase = "https://linkguessr.duckdns.org";
try {
  const host = window?.location?.hostname;
  if (host === "localhost" || host === "127.0.0.1") {
    defaultBase = "http://127.0.0.1:8000";
  }
} catch {}

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || defaultBase;

export const apiUrl = (path) => `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
