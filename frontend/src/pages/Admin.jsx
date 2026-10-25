import { useState } from "react";
import { apiUrl } from "../config";

const GAME_NAMES = { daily: "Défi du jour", guess_who: "Qui est caché ?", relay: "Relier", guess_count: "Nombre de liens", explore: "Explorer" };

// Tableau de bord privé : le jeton (ADMIN_TOKEN de la VM) reste dans l'onglet (sessionStorage).
export default function Admin() {
  const [token, setToken] = useState(() => { try { return sessionStorage.getItem("lg-admin") || ""; } catch { return ""; } });
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = async (e) => {
    e?.preventDefault();
    setError(null);
    try {
      const res = await fetch(apiUrl(`/admin/metrics?days=${days}`), { headers: { "X-Admin-Token": token } });
      if (!res.ok) throw new Error(res.status === 401 ? "Jeton invalide" : `Erreur ${res.status}`);
      setData(await res.json());
      try { sessionStorage.setItem("lg-admin", token); } catch { /* sans importance */ }
    } catch (err) {
      setError(err.message);
    }
  };

  const pct = (v) => (v == null ? "—" : `${v} %`);
  return (
    <main className="page">
      <section className="panel">
        <div className="panel-header"><span className="panel-title">Tableau de bord</span></div>
        <div className="panel-body">
          <form className="toolbar" onSubmit={load}>
            <input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Jeton admin" />
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {[1, 7, 30, 90].map((d) => <option key={d} value={d}>{d} jour(s)</option>)}
            </select>
            <button className="btn" type="submit">Afficher</button>
            <a className="btn" href="https://linkguessr.duckdns.org/umami/" target="_blank" rel="noreferrer">Fréquentation (Umami)</a>
          </form>
          {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
        </div>
      </section>

      {data && (
        <>
          <section className="panel" style={{ marginTop: 12 }}>
            <div className="panel-header"><span className="panel-title">Parties par jeu et par source ({data.days} j)</span></div>
            <div className="panel-body" style={{ overflowX: "auto" }}>
              <table className="table">
                <thead><tr><th>Jeu</th><th>Source</th><th>Sessions</th><th>Débuts</th><th>Fins</th><th>Taux de fin</th><th>Partages</th><th>Taux de partage</th><th>Duels ouverts</th></tr></thead>
                <tbody>
                  {data.funnel.map((r) => (
                    <tr key={`${r.game}-${r.src}`}>
                      <td>{GAME_NAMES[r.game] || r.game}</td><td>{r.src}</td><td>{r.sessions}</td><td>{r.starts}</td><td>{r.finishes}</td>
                      <td><strong>{pct(r.finish_rate)}</strong></td><td>{r.shares}</td><td><strong>{pct(r.share_rate)}</strong></td><td>{r.duels}</td>
                    </tr>
                  ))}
                  {data.funnel.length === 0 && <tr><td colSpan={9} className="muted">Aucune partie sur la période.</td></tr>}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel" style={{ marginTop: 12 }}>
            <div className="panel-header"><span className="panel-title">Défi du jour</span></div>
            <div className="panel-body">
              <table className="table">
                <thead><tr><th>Jour</th><th>Joueurs</th><th>Trouvé</th></tr></thead>
                <tbody>{data.daily.map((d) => <tr key={d.day}><td>{d.day}</td><td>{d.players}</td><td>{d.solved}</td></tr>)}</tbody>
              </table>
            </div>
          </section>

          <section className="panel" style={{ marginTop: 12 }}>
            <div className="panel-header"><span className="panel-title">Retours des joueurs</span></div>
            <div className="panel-body">
              <table className="table">
                <thead><tr><th>Jeu</th><th>Réponses</th><th>👍</th></tr></thead>
                <tbody>{data.feedback.map((f) => <tr key={f.game}><td>{GAME_NAMES[f.game] || f.game}</td><td>{f.answers}</td><td>{pct(f.positive_pct)}</td></tr>)}</tbody>
              </table>
              <ul className="link-list" style={{ marginTop: 12 }}>
                {data.comments.map((c, i) => (
                  <li key={i}>
                    <span>{c.rating > 0 ? "👍" : "👎"} <strong>{GAME_NAMES[c.game] || c.game}</strong>
                      <span className="muted"> · {new Date(c.created_at).toLocaleString()} · {c.src || "(direct)"}</span></span>
                    <span>{c.comment}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </>
      )}
    </main>
  );
}
