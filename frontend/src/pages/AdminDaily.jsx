import { Fragment, useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { commonsThumb } from "../api";
import { apiUrl } from "../config";
import PersonPicker from "../components/PersonPicker";

const KINDS = { rap: "🎤 rap", web: "📱 web", pop: "🎵 pop", foot: "⚽ foot" };
const ERAS = { historique: "🏛️ historique", moderne: "🌍 moderne" };

function readToken() {
  try { return sessionStorage.getItem("lg-admin") || ""; } catch { return ""; }
}

// Appel d'une route d'administration avec le jeton (ADMIN_TOKEN de la VM).
async function adminCall(token, path, { method = "GET", body } = {}) {
  const res = await fetch(apiUrl(`/admin/daily${path}`), {
    method,
    headers: { "X-Admin-Token": token, ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Erreur ${res.status}`);
  return data;
}

function Mini({ person, hidden }) {
  if (!person) return null;
  return (
    <span className={`admin-person ${hidden ? "is-hidden" : ""}`} title={person.description || ""}>
      {person.image
        ? <img src={commonsThumb(person.image, 48)} alt="" width={24} height={24} />
        : <span className="person-avatar placeholder" style={{ width: 24, height: 24 }}>{person.name.charAt(0)}</span>}
      <span>{hidden ? <strong>[{person.name}]</strong> : person.name}</span>
    </span>
  );
}

function Path({ path, masked = 1 }) {
  return (
    <span className="admin-path">
      {path.map((p, i) => (
        <span key={p.qid}>{i > 0 && " → "}<Mini person={p} hidden={i === masked} /></span>
      ))}
    </span>
  );
}

// Choix à la main des trois personnes : star jeune → personne cachée → personnalité sans rapport.
function ManualEditor({ onSave, onCancel }) {
  const [youth, setYouth] = useState(null);
  const [middle, setMiddle] = useState(null);
  const [contrast, setContrast] = useState(null);
  return (
    <div className="admin-editor">
      <div className="row" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
        <PersonPicker id="adm-youth" label="Star (à gauche)" value={youth} onChange={setYouth} />
        <PersonPicker id="adm-middle" label="Personne cachée" value={middle} onChange={setMiddle} />
        <PersonPicker id="adm-contrast" label="Sans rapport (à droite)" value={contrast} onChange={setContrast} />
      </div>
      <div className="toolbar" style={{ marginTop: 8 }}>
        <button className="btn btn-primary" disabled={!youth || !middle || !contrast}
          onClick={() => onSave({ youth: youth.qid, middle: middle.qid, contrast: contrast.qid })}>Enregistrer (verrouillé)</button>
        <button className="btn btn-ghost" onClick={onCancel}>Annuler</button>
      </div>
    </div>
  );
}

export default function AdminDaily() {
  const [token, setToken] = useState(readToken);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);         // jour en cours de modification
  const [open, setOpen] = useState({});           // { "2026-11-02": "candidates" | "edit" }
  const [candidates, setCandidates] = useState({});
  const [selected, setSelected] = useState([]);   // jours cochés pour l'échange

  const load = useCallback(async () => {
    setError(null);
    try {
      setData(await adminCall(token, "?past=7&days=60"));
      try { sessionStorage.setItem("lg-admin", token); } catch { /* sans importance */ }
    } catch (e) {
      setError(e.message);
    }
  }, [token]);

  useEffect(() => { if (token) load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (day, path, options, confirmText) => {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(day);
    setError(null);
    try {
      await adminCall(token, path, options);
      setOpen((o) => ({ ...o, [day]: null }));
      await load();
    } catch (e) {
      setError(`${day} : ${e.message}`);
    } finally {
      setBusy(null);
    }
  };

  const showCandidates = async (day) => {
    setOpen((o) => ({ ...o, [day]: o[day] === "candidates" ? null : "candidates" }));
    if (!candidates[day]) {
      try {
        const res = await adminCall(token, `/${day}/candidates?limit=10`);
        setCandidates((c) => ({ ...c, [day]: res.candidates }));
      } catch (e) {
        setError(e.message);
      }
    }
  };

  const toggleSelect = (day) => setSelected((s) => (s.includes(day) ? s.filter((d) => d !== day) : [...s, day].slice(-2)));

  return (
    <main className="page admin-daily">
      <section className="panel">
        <div className="panel-header">
          <span className="panel-title">Défis du jour</span>
          <Link className="btn btn-ghost" to="/admin">← Tableau de bord</Link>
        </div>
        <div className="panel-body">
          <form className="toolbar" onSubmit={(e) => { e.preventDefault(); load(); }}>
            <input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Jeton admin" />
            <button className="btn" type="submit">Charger</button>
            <button className="btn btn-primary" type="button" disabled={selected.length !== 2}
              onClick={() => act(selected[0], "/swap", { method: "POST", body: { a: selected[0], b: selected[1] } })
                .then(() => setSelected([]))}>
              Interchanger les 2 jours cochés
            </button>
          </form>
          <p className="muted" style={{ marginBottom: 0 }}>
            Recette : star jeune → <strong>[personne cachée]</strong> → personnalité sans rapport. Un défi modifié à la main
            est verrouillé 🔒 : la génération automatique de la nuit n'y touche plus. Le jour en cours et les jours passés
            ne peuvent plus changer.
          </p>
          {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
        </div>
      </section>

      {data && (
        <section className="panel" style={{ marginTop: 12 }}>
          <div className="panel-body" style={{ overflowX: "auto" }}>
            <table className="table admin-table">
              <thead><tr><th></th><th>#</th><th>Jour</th><th>Profil</th><th>Défi</th><th>Joueurs</th><th>Actions</th></tr></thead>
              <tbody>
                {data.days.map((d) => (
                  <Fragment key={d.day}>
                    <tr className={d.current ? "is-current" : !d.editable ? "is-past" : ""}>
                      <td>{d.editable && d.path && (
                        <input type="checkbox" checked={selected.includes(d.day)} onChange={() => toggleSelect(d.day)}
                          aria-label="Sélectionner pour interchanger" />)}</td>
                      <td>{d.number}</td>
                      <td>{new Date(`${d.day}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" })}
                        {d.current && <span className="tag" style={{ marginLeft: 6 }}>en cours</span>}</td>
                      <td className="muted">{KINDS[d.profile.kind]}<br />{ERAS[d.profile.era]}</td>
                      <td>{d.path ? <>{d.locked && "🔒 "}<Path path={d.path} masked={d.masked_index} /></>
                        : <span className="muted">Aucun défi</span>}</td>
                      <td className="muted">{d.players ? `${d.players} (${d.solved} ✔)` : "—"}</td>
                      <td>
                        {d.editable ? (
                          <div className="toolbar admin-actions">
                            <button className="btn" disabled={busy === d.day} onClick={() => act(d.day, `/${d.day}/regenerate`, { method: "POST" })}>Régénérer</button>
                            <button className="btn" onClick={() => showCandidates(d.day)}>Propositions</button>
                            <button className="btn" onClick={() => setOpen((o) => ({ ...o, [d.day]: o[d.day] === "edit" ? null : "edit" }))}>Modifier</button>
                            {d.path && (
                              <button className="btn btn-ghost" onClick={() => act(d.day, `/${d.day}/lock`, { method: "POST", body: { locked: !d.locked } })}>
                                {d.locked ? "Déverrouiller" : "Verrouiller"}
                              </button>
                            )}
                            {d.path && (
                              <button className="btn btn-ghost" onClick={() => act(d.day, `/${d.day}`, { method: "DELETE" },
                                `Supprimer le défi #${d.number} ? La génération de la nuit remplira ce jour.`)}>Supprimer</button>
                            )}
                          </div>
                        ) : <span className="muted">—</span>}
                      </td>
                    </tr>
                    {open[d.day] === "candidates" && (
                      <tr><td colSpan={7}>
                        {!candidates[d.day] ? <span className="muted">Calcul des propositions…</span> : (
                          <ul className="admin-candidates">
                            {candidates[d.day].map((c, i) => (
                              <li key={i}>
                                <Path path={c.path} />
                                <span className="muted"> · {KINDS[c.kind]} · {ERAS[c.era]} · {c.alternatives} possible(s) · score {c.score}</span>
                                <button className="btn" onClick={() => act(d.day, `/${d.day}/set`, { method: "POST",
                                  body: { youth: c.path[0].qid, middle: c.path[1].qid, contrast: c.path[2].qid } })}>Choisir</button>
                              </li>
                            ))}
                            {candidates[d.day].length === 0 && <li className="muted">Aucune proposition.</li>}
                          </ul>
                        )}
                      </td></tr>
                    )}
                    {open[d.day] === "edit" && (
                      <tr><td colSpan={7}>
                        <ManualEditor onCancel={() => setOpen((o) => ({ ...o, [d.day]: null }))}
                          onSave={(body) => act(d.day, `/${d.day}/set`, { method: "POST", body })} />
                      </td></tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
