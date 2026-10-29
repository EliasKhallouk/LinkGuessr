// Partage d'un résultat : menu natif (téléphone) sinon presse-papiers.
// Retourne "shared", "copied", "cancelled" ou "failed".
export const SITE_URL = "https://linkguessr.com";

// Paramètres de campagne des liens partagés (docs/tracking.md) : utm_medium dépend de la méthode.
export function withUtm(url, { source, campaign }, medium) {
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}utm_source=${source}&utm_medium=${medium}&utm_campaign=${campaign}`;
}

const canWebShare = () => Boolean(navigator.share) && /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);

// `sep` : entre le texte et le lien (retour à la ligne, ou espace pour un lien en fin de phrase).
export async function shareText(text, url, utm, sep = "\n") {
  const link = (medium) => (url && utm ? withUtm(url, utm, medium) : url);
  const join = (u) => (u ? `${text}${sep}${u}` : text);
  try {
    if (canWebShare()) {
      await navigator.share({ text: join(link("webshare")) });
      return "shared";
    }
  } catch (e) {
    if (e?.name === "AbortError") return "cancelled";
  }
  const full = join(link("copie"));
  try {
    await navigator.clipboard.writeText(full);
    return "copied";
  } catch {
    // Anciens navigateurs : sélection d'une zone de texte temporaire.
    const area = Object.assign(document.createElement("textarea"), { value: full });
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand?.("copy");
    area.remove();
    return ok ? "copied" : "failed";
  }
}

// Cases façon Wordle : 🟥 erreur, 🟩 trouvé, ⬛ essai non utilisé.
export function dailyGrid(wrongCount, solved, maxTries) {
  const cells = [...Array(wrongCount).fill("🟥"), ...(solved ? ["🟩"] : [])];
  return cells.concat(Array(Math.max(0, maxTries + 1 - cells.length)).fill("⬛")).join("");
}

// Relais : une case par coup, 🟩 dans le chemin optimal, 🟨 détour au-delà.
export function relayGrid(steps, best) {
  return Array.from({ length: steps }, (_, i) => (best && i < best ? "🟩" : "🟨")).join("");
}

// Lien de duel et sa campagne (nom du jeu dans l'URL du site), à passer à <ShareButton {...duelShare(…)} />.
const DUEL_CAMPAIGNS = { qui: "qui-est-cache", serie: "qui-est-cache", relais: "relier", nombre: "combien" };

// Graine d'une série (partie de « Combien ? », 10 énigmes de « Qui est caché ? ») : transmise par le lien de
// duel en base 36 (6 caractères au plus) pour que l'ami joue la même série, dans le même ordre.
export const newSeed = () => Math.floor(Math.random() * 2 ** 31);
export const parseSeed = (g) => (/^[0-9a-z]{1,6}$/.test(g || "") ? parseInt(g, 36) : null);
export function duelShare(params) {
  return { url: `${SITE_URL}/defi?${new URLSearchParams(params)}`, utm: { source: "duel", campaign: DUEL_CAMPAIGNS[params.jeu] } };
}

// Chemin partagé depuis Explorer : seulement les deux bouts (le chemin est recalculé à l'ouverture),
// et le type de liens s'il n'est pas celui par défaut.
export const EXPLORE_MODES = ["all", "strong", "wikidata"];
export function explorerShare(de, a, mode = "all") {
  const q = new URLSearchParams({ de, a, ...(mode !== "all" && { mode }) });
  return { url: `${SITE_URL}/explorer?${q}`, utm: { source: "partage", campaign: "explorer" } };
}

// Requête /path d'un chemin partagé : la même partout (page, aperçu, image), donc une seule entrée
// dans le cache Vercel par paire. Même ordre de paramètres que api.path().
export const EXPLORE_LIMIT = 6;
export function sharedPathQuery(de, a, mode) {
  return `/path?${new URLSearchParams({ from: de, to: a, mode: EXPLORE_MODES.includes(mode) ? mode : "all", limit: EXPLORE_LIMIT })}`;
}
