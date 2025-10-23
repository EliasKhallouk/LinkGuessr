import { useEffect, useState } from "react";

export default function Leaderboard() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("http://127.0.0.1:8000/leaderboard?limit=20");
        const data = await res.json();
        setEntries(Array.isArray(data.entries) ? data.entries : []);
      } catch (e) {
        setError("Impossible de charger le classement.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const fmtDate = (ts) => {
    try { return new Date(ts * 1000).toLocaleString(); } catch { return ""; }
  };

  return (
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">Classement mondial</span>
      </div>
      <div className="panel-body">
        {loading && <p className="muted" style={{ margin: 0 }}>Chargement…</p>}
        {error && (
          <div className="error-box"><p style={{ margin: 0 }}>{error}</p></div>
        )}
        {!loading && !error && (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                  <th style={{ padding: "8px" }}>#</th>
                  <th style={{ padding: "8px" }}>Joueur</th>
                  <th style={{ padding: "8px" }}>Score</th>
                  <th style={{ padding: "8px" }}>Durée (s)</th>
                  <th style={{ padding: "8px" }}>Date</th>
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
                    <td colSpan={5} style={{ padding: "8px" }} className="muted">Aucun score pour le moment.</td>
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
