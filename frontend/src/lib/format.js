// Mises en forme d'affichage (sans effet sur les données).

// « 26 octobre 2026 » ; le premier du mois s'écrit « 1er octobre ».
export function formatLongDate(date, lang) {
  const text = date.toLocaleDateString(lang === "en" ? "en-GB" : "fr-FR", { day: "numeric", month: "long", year: "numeric" });
  return lang !== "en" && date.getDate() === 1 ? text.replace(/^1(?=\s)/, "1er") : text;
}

// « 2026-10-26 » (jour civil, sans fuseau) → Date locale à minuit.
export function parseDay(isoDay) {
  return new Date(`${isoDay}T00:00:00`);
}

// Majuscule initiale à l'affichage (« affaires » → « Affaires »).
export function capitalize(text) {
  return text ? text.charAt(0).toLocaleUpperCase("fr-FR") + text.slice(1) : text;
}
