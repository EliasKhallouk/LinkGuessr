import { useCallback, useEffect, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";

export default function Leaderboard() {
  const { t } = useI18n();
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("http://127.0.0.1:8000/leaderboard?limit=10");
      const data = await res.json();
      setEntries(Array.isArray(data.entries) ? data.entries : []);
    } catch (e) {
        setError(t("leaderboard.error"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const handler = () => load();
    window.addEventListener("leaderboard:refresh", handler);
    return () => window.removeEventListener("leaderboard:refresh", handler);
  }, [load]);

  const fmtDate = (ts) => {
    try {
      const d = new Date(ts * 1000);
      // Only the date part in user's locale
      return d.toLocaleDateString();
    } catch {
      return "";
    }
  };

  return (
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">{t("leaderboard.title")}</span>
      </div>
      <div className="panel-body">
        {loading && <p className="muted" style={{ margin: 0 }}>{t("leaderboard.loading")}</p>}
        {error && (
          <div className="error-box"><p style={{ margin: 0 }}>{error}</p></div>
        )}
        {!loading && !error && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                  <th style={{ padding: "8px" }}>{t("leaderboard.rankHeader")}</th>
                  <th style={{ padding: "8px" }}>{t("leaderboard.playerHeader")}</th>
                  <th style={{ padding: "8px" }}>{t("leaderboard.scoreHeader")}</th>
                  <th style={{ padding: "8px" }}>{t("leaderboard.durationHeader")}</th>
                  <th style={{ padding: "8px" }}>{t("leaderboard.dateHeader")}</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => (
                  <tr key={`${e.rank}-${e.ts}-${e.name}`} style={{ borderTop: "1px solid var(--border)" }}>
                    <td style={{ padding: "8px" }}>{e.rank}</td>
                    <td style={{ padding: "8px" }}>{e.name}</td>
                    <td style={{ padding: "8px" }}><strong>{e.score}</strong></td>
                    <td style={{ padding: "8px" }}>{e.duration}</td>
                    <td style={{ padding: "8px" }}>{fmtDate(e.ts)}</td>
                  </tr>
                ))}
                {entries.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ padding: "8px" }} className="muted">{t("leaderboard.empty")}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
