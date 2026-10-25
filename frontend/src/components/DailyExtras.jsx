import { useEffect, useState } from "react";
import { api } from "../api";
import { useI18n } from "../i18n/I18nProvider";
import { dailyStats } from "../lib/dailyStats";
import { deviceId, load, save } from "../lib/storage";
import { ShowMoreButton, useShowMore } from "./ShowMore";

// Statistiques personnelles (locales) après la partie du jour.
export function DailyStats({ history, highlight }) {
  const { t } = useI18n();
  const s = dailyStats(history);
  const max = Math.max(1, ...s.distribution);
  return (
    <div className="daily-stats">
      <div className="stats-row">
        <div><strong>{s.played}</strong><span>{t("daily.played")}</span></div>
        <div><strong>{s.winRate} %</strong><span>{t("daily.winRate")}</span></div>
        <div><strong>{s.current} 🔥</strong><span>{t("daily.streak")}</span></div>
        <div><strong>{s.best}</strong><span>{t("daily.bestStreak")}</span></div>
      </div>
      <div className="distribution">
        {s.distribution.map((count, i) => (
          <div key={i} className="dist-row">
            <span>{i + 1}</span>
            <div className={`dist-bar ${highlight === i + 1 ? "is-today" : ""}`} style={{ width: `${8 + (92 * count) / max}%` }}>{count}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Classement du jour + pseudo facultatif (réservé à ceux qui ont trouvé).
export function DailyLeaderboard({ solved }) {
  const { t } = useI18n();
  const [entries, setEntries] = useState([]);
  const [pseudo, setPseudo] = useState(() => load("lg-pseudo", ""));
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const shown = useShowMore(entries);

  const refresh = () => api.dailyLeaderboard().then(setEntries).catch(() => {});
  useEffect(() => { refresh(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await api.dailyPseudo(deviceId(), pseudo);
      save("lg-pseudo", res.pseudo);
      setPseudo(res.pseudo);
      setSaved(true);
      refresh();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div style={{ marginTop: 12 }}>
      {solved && !saved && (
        <form className="toolbar" onSubmit={submit}>
          <input type="text" maxLength={16} value={pseudo} placeholder={t("daily.pseudoPlaceholder")}
            onChange={(e) => setPseudo(e.target.value)} aria-label={t("daily.pseudoPlaceholder")} />
          <button className="btn" type="submit" disabled={!pseudo.trim()}>{t("daily.joinBoard")}</button>
        </form>
      )}
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      {entries.length > 0 && (
        <table className="table" style={{ marginTop: 8 }}>
          <thead><tr><th>#</th><th>{t("leaderboard.playerHeader")}</th><th>{t("daily.triesHeader")}</th><th>{t("daily.timeHeader")}</th></tr></thead>
          <tbody>
            {shown.visible.map((e, i) => (
              <tr key={e.pseudo}><td>{i + 1}</td><td>{e.pseudo}</td><td>{e.tries}</td><td>{e.seconds} s</td></tr>
            ))}
          </tbody>
        </table>
      )}
      <ShowMoreButton list={shown} />
    </div>
  );
}
