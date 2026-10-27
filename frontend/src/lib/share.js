// Partage d'un résultat : menu natif (téléphone) sinon presse-papiers.
// Retourne "shared", "copied", "cancelled" ou "failed".
export const SITE_URL = "https://linkguessr.com";

// Paramètres de campagne des liens partagés (docs/tracking.md) : utm_medium dépend de la méthode.
export function withUtm(url, { source, campaign }, medium) {
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}utm_source=${source}&utm_medium=${medium}&utm_campaign=${campaign}`;
}

const canWebShare = () => Boolean(navigator.share) && /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);

export async function shareText(text, url, utm) {
  const link = (medium) => (url && utm ? withUtm(url, utm, medium) : url);
  const join = (u) => (u ? `${text}\n${u}` : text);
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
const DUEL_CAMPAIGNS = { cache: "qui-est-cache", relais: "relier", nombre: "combien" };
export function duelShare(params) {
  return { url: `${SITE_URL}/defi?${new URLSearchParams(params)}`, utm: { source: "duel", campaign: DUEL_CAMPAIGNS[params.jeu] } };
}
