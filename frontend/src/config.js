// Single source of truth for backend API base URL
// Override via environment variable REACT_APP_API_BASE_URL
// Example: create .env in frontend folder with:
// REACT_APP_API_BASE_URL=https://your-backend.example.com

// Heuristic: if no explicit base URL is provided and we're on localhost, default to local FastAPI
let defaultBase = "https://linkguessr.onrender.com";
try {
  const host = window?.location?.hostname;
  if (host === "localhost" || host === "127.0.0.1") {
    defaultBase = "http://127.0.0.1:8000";
  }
} catch {}

export const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL?.replace(/\/$/, "") || defaultBase;

export const apiUrl = (path) => `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
