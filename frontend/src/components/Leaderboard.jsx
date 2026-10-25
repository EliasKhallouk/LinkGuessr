import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useI18n } from "../i18n/I18nProvider";

export default function Leaderboard({ game = "guess_count" }) {
  const { t } = useI18n();
  const [entries, setEntries] = useState([]);
  const [period, setPeriod] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setEntries(await api.leaderboard(game, period));
    } catch {
      setError(t("leaderboard.error"));
    } finally {
      setLoading(false);
    }
  }, [game, period, t]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    window.addEventListener("leaderboard:refresh", load);
    return () => window.removeEventListener("leaderboard:refresh", load);
  }, [load]);

  return (
    <section className="panel fade-in" style={{ marginTop: 12 }}>
      <div className="panel-header">
        <span className="panel-title">{t("leaderboard.title")}</span>
        <select value={period} onChange={(e) => setPeriod(e.target.value)} aria-label={t("leaderboard.period")}>
          <option value="7">{t("period.7")}</option>
          <option value="30">{t("period.30")}</option>
          <option value="all">{t("period.all")}</option>
        </select>
      </div>
      <div className="panel-body">
        {loading && <p className="muted" style={{ margin: 0 }}>{t("leaderboard.loading")}</p>}
        {error && <div className="error-box"><p style={{ margin: 0 }}>{error}</p></div>}
        {!loading && !error && (
          <table className="table">
            <thead>
              <tr>
                <th>{t("leaderboard.rankHeader")}</th>
                <th>{t("leaderboard.playerHeader")}</th>
                <th>{t("leaderboard.scoreHeader")}</th>
                <th>{t("leaderboard.dateHeader")}</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={`${e.rank}-${e.created_at}-${e.name}`}>
                  <td>{e.rank}</td>
                  <td>{e.name}</td>
                  <td><strong>{e.score}</strong></td>
                  <td>{new Date(e.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr><td colSpan={4} className="muted">{t("leaderboard.empty")}</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
