// Le défi change à minuit, heure de Paris, quel que soit le fuseau du joueur.
export function msUntilParisMidnight(now = new Date()) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("fr-FR", { timeZone: "Europe/Paris", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" })
      .formatToParts(now).filter((p) => p.type !== "literal").map((p) => [p.type, Number(p.value)]),
  );
  const elapsed = parts.hour * 3600 + parts.minute * 60 + parts.second;
  return (86400 - elapsed) * 1000;
}

export function formatCountdown(ms) {
  const s = Math.max(0, Math.round(ms / 1000));
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
}
