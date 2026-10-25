// Stockage local tolérant : navigation privée, stockage bloqué ou plein ne doivent jamais casser le jeu.
const memory = new Map();

export function load(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key);
    if (raw !== null) return JSON.parse(raw);
  } catch { /* stockage indisponible ou valeur illisible */ }
  return memory.has(key) ? memory.get(key) : fallback;
}

export function save(key, value) {
  memory.set(key, value);
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch { /* on garde la valeur en mémoire pour la session */ }
}

function randomId() {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
  }
}

// Identifiant anonyme de l'appareil : aucune donnée personnelle, juste un tirage aléatoire.
export function deviceId() {
  let id = load("lg-device");
  if (!id) {
    id = randomId();
    save("lg-device", id);
  }
  return id;
}
