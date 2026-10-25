// Historique local du défi du jour (navigateur uniquement) : séries et répartition des essais, façon Wordle.
import { load, save } from "./storage";

const KEY = "lg-daily-history"; // { "12": { solved: true, tries: 2 }, … } indexé par numéro de défi

export function recordDaily(number, solved, tries) {
  const history = load(KEY, {});
  if (history[number]) return history;
  const next = { ...history, [number]: { solved, tries } };
  save(KEY, next);
  return next;
}

export function dailyStats(history = load(KEY, {})) {
  const numbers = Object.keys(history).map(Number).sort((a, b) => a - b);
  const played = numbers.length;
  const won = numbers.filter((n) => history[n].solved).length;
  // Série : défis réussis dont les numéros se suivent ; un échec ou un jour sauté la remet à zéro.
  let run = 0;
  let best = 0;
  let previous = null;
  for (const n of numbers) {
    if (!history[n].solved) run = 0;
    else run = previous !== null && n === previous + 1 && run > 0 ? run + 1 : 1;
    best = Math.max(best, run);
    previous = n;
  }
  const current = run;
  const distribution = [1, 2, 3, 4, 5].map((t) => numbers.filter((n) => history[n].solved && history[n].tries === t).length);
  return { played, won, winRate: played ? Math.round((100 * won) / played) : 0, current, best, distribution };
}
