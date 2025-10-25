// Single source of truth for backend API base URL
// Override via environment variable REACT_APP_API_BASE_URL
// Example: create .env in frontend folder with:
// REACT_APP_API_BASE_URL=https://your-backend.example.com

export const API_BASE_URL =
  process.env.REACT_APP_API_BASE_URL?.replace(/\/$/, "") || "https://linkguessr.onrender.com";

export const apiUrl = (path) => `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
