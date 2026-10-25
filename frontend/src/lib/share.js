// Partage d'un résultat : menu natif (téléphone) sinon presse-papiers. Retourne "shared", "copied" ou "failed".
export const SITE_URL = "https://link-guessr.vercel.app";

export async function shareText(text, url) {
  const full = url ? `${text}\n${url}` : text;
  try {
    if (navigator.share && /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent)) {
      await navigator.share({ text: full });
      return "shared";
    }
  } catch (e) {
    if (e?.name === "AbortError") return "cancelled";
  }
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

// Les liens partagés portent leur source (?src=), pour mesurer ce que rapporte le partage.
export function duelUrl(params) {
  return `${SITE_URL}/defi?${new URLSearchParams({ ...params, src: "duel" })}`;
}
