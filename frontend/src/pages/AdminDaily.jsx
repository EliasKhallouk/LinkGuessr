import { Fragment, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import CommonsImg from "../components/CommonsImg";
import { apiUrl } from "../config";
import PersonPicker from "../components/PersonPicker";

const KINDS = { rap: ["🎤", "rap"], web: ["📱", "web"], pop: ["🎵", "pop"], foot: ["⚽", "foot"] };
const ERAS = { historique: ["🏛️", "personnalité historique"], moderne: ["🌍", "personnalité moderne d'un autre univers"] };

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

// Une personne : avatar + nom tronqué, dans une colonne de largeur fixe pour que tout s'aligne d'une ligne à l'autre.
function Person({ person, hidden }) {
  if (!person) return <span className="muted">—</span>;
  return (
    <span className={`admin-person ${hidden ? "is-hidden" : ""}`} title={`${person.name}${person.description ? ` — ${person.description}` : ""}`}>
      {person.image
        ? <CommonsImg file={person.image} width={28} height={28} loading="lazy" />
        : <span className="person-avatar placeholder" style={{ width: 28, height: 28 }}>{person.name.charAt(0)}</span>}
      <span className="admin-person-name">{person.name}</span>
    </span>
  );
}

// Menu « ⋯ » : affiché par-dessus la page (portail) pour ne pas être coupé par le défilement du tableau.
function RowMenu({ items }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState(null);
  const button = useRef(null);
  const menu = useRef(null);

  useLayoutEffect(() => {
    if (!open) return;
    const r = button.current.getBoundingClientRect();
    setPosition({ top: r.bottom + 4, right: window.innerWidth - r.right });
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (!menu.current?.contains(e.target) && !button.current?.contains(e.target)) setOpen(false); };
    const closeOnKey = (e) => { if (e.key === "Escape") setOpen(false); };
    const closeOnScroll = () => setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", closeOnKey);
    window.addEventListener("scroll", closeOnScroll, true);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", closeOnKey);
      window.removeEventListener("scroll", closeOnScroll, true);
    };
  }, [open]);

  return (
    <>
      <button ref={button} className="btn btn-ghost admin-more" aria-label="Plus d'actions" aria-expanded={open}
        onClick={() => setOpen((o) => !o)}>⋯</button>
      {open && position && createPortal(
        <ul ref={menu} className="admin-menu" style={{ top: position.top, right: position.right }}>
          {items.filter(Boolean).map((item) => (
            <li key={item.label}>
              <button className={item.danger ? "is-danger" : ""} disabled={item.disabled}
                onClick={() => { setOpen(false); item.onClick(); }}>{item.label}</button>
            </li>
          ))}
        </ul>,
        document.body,
      )}
    </>
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
        <PersonPicker id="adm-youth" label="Star" value={youth} onChange={setYouth} />
        <PersonPicker id="adm-middle" label="Personne cachée" value={middle} onChange={setMiddle} />
        <PersonPicker id="adm-contrast" label="Sans rapport" value={contrast} onChange={setContrast} />
      </div>
      <div className="toolbar" style={{ marginTop: 8 }}>
        <button className="btn btn-primary" disabled={!youth || !middle || !contrast}
          onClick={() => onSave({ youth: youth.qid, middle: middle.qid, contrast: contrast.qid })}>Enregistrer (verrouillé)</button>
        <button className="btn btn-ghost" onClick={onCancel}>Annuler</button>
      </div>
    </div>
  );
}

const COLUMNS = 7; // poignée, n°, jour, star, cachée, sans rapport, actions

export default function AdminDaily() {
  const [token, setToken] = useState(readToken);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(null);         // jour en cours de modification
  const [open, setOpen] = useState({});           // { "2026-11-02": "candidates" | "edit" }
  const [candidates, setCandidates] = useState({});

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
      setCandidates({});
      await load();
    } catch (e) {
      setError(`${day} : ${e.message}`);
    } finally {
      setBusy(null);
    }
  };

  const toggle = (day, panel) => setOpen((o) => ({ ...o, [day]: o[day] === panel ? null : panel }));

  const showCandidates = async (day) => {
    toggle(day, "candidates");
    if (!candidates[day]) {
      try {
        const res = await adminCall(token, `/${day}/candidates?limit=10`);
        setCandidates((c) => ({ ...c, [day]: res.candidates }));
      } catch (e) {
        setError(e.message);
      }
    }
  };

  // Glisser-déposer : on attrape la ligne par sa poignée ⠿ et on la dépose sur un autre jour à venir ;
  // les défis intermédiaires se décalent d'un jour (route /move).
  const [armed, setArmed] = useState(null);   // poignée tenue : la ligne devient déplaçable
  const [dragged, setDragged] = useState(null);
  const [over, setOver] = useState(null);
  const movable = (d) => d.editable && d.path;
  const move = (source, target) => act(source, "/move", { method: "POST", body: { source, target } });
  const drop = (target) => {
    const source = dragged;
    setDragged(null);
    setOver(null);
    setArmed(null);
    if (source && source !== target) move(source, target);
  };
  // Avancer / reculer d'un jour (menu ⋯, utile sur téléphone où le glisser-déposer n'existe pas).
  const neighbor = (index, step) => {
    const other = data?.days[index + step];
    return other && movable(other) ? other.day : null;
  };

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
          </form>
          <p className="muted" style={{ marginBottom: 0 }}>
            Glisse une ligne par sa poignée ⠿ pour la déplacer. 🔒 : verrouillé, la génération de la nuit n'y touche pas.
            Le jour en cours et les jours passés ne peuvent plus changer.
          </p>
          {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
        </div>
      </section>

      {data && (
        <section className="panel" style={{ marginTop: 12 }}>
          <div className="panel-body admin-scroll">
            <table className="table admin-table">
              <colgroup>
                <col className="col-handle" /><col className="col-number" /><col className="col-day" />
                <col className="col-person" /><col className="col-person" /><col className="col-person" /><col className="col-actions" />
              </colgroup>
              <thead>
                <tr><th></th><th>#</th><th>Jour</th><th>Star</th><th>Personne cachée</th><th>Sans rapport</th><th></th></tr>
              </thead>
              <tbody>
                {data.days.map((d, index) => {
                  const [kindIcon, kindLabel] = KINDS[d.profile.kind];
                  const [eraIcon, eraLabel] = ERAS[d.profile.era];
                  const rowClass = [d.current ? "is-current" : !d.editable ? "is-past" : "",
                    dragged === d.day ? "is-dragged" : "",
                    over === d.day && dragged && dragged !== d.day ? (dragged < d.day ? "drop-after" : "drop-before") : ""].join(" ");
                  return (
                    <Fragment key={d.day}>
                      <tr className={rowClass}
                        draggable={armed === d.day}
                        onDragStart={(e) => { setDragged(d.day); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", d.day); }}
                        onDragOver={(e) => { if (dragged && movable(d)) { e.preventDefault(); setOver(d.day); } }}
                        onDrop={(e) => { e.preventDefault(); if (dragged && movable(d)) drop(d.day); }}
                        onDragEnd={() => { setDragged(null); setOver(null); setArmed(null); }}>
                        <td>{movable(d) && (
                          <span className="admin-handle" title="Glisser pour déplacer"
                            onMouseDown={() => setArmed(d.day)} onMouseUp={() => setArmed(null)}>⠿</span>)}</td>
                        <td className="admin-number">{d.number}{d.locked && <span title="Verrouillé"> 🔒</span>}</td>
                        <td className="admin-day">
                          <span>{new Date(`${d.day}T12:00:00`).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric", month: "short" })}</span>
                          <span className="admin-profile" title={`${kindLabel} · ${eraLabel}`}>{kindIcon}{eraIcon}</span>
                          {d.current && <span className="tag">en cours</span>}
                          {d.players > 0 && <span className="muted admin-players" title="joueurs · trouvé">{d.players} · {d.solved} ✔</span>}
                        </td>
                        {d.path
                          ? d.path.map((p, i) => <td key={p.qid}><Person person={p} hidden={i === d.masked_index} /></td>)
                          : <td colSpan={3} className="muted">Aucun défi</td>}
                        <td className="admin-actions">
                          {d.editable && (
                            <>
                              <button className="btn" disabled={busy === d.day}
                                onClick={() => act(d.day, `/${d.day}/regenerate`, { method: "POST" })}>Régénérer</button>
                              <RowMenu items={[
                                { label: "Propositions…", onClick: () => showCandidates(d.day) },
                                { label: "Modifier à la main…", onClick: () => toggle(d.day, "edit") },
                                d.path && { label: "Inverser gauche ⇄ droite", onClick: () => act(d.day, `/${d.day}/flip`, { method: "POST" }) },
                                d.path && { label: "Avancer d'un jour ▲", disabled: !neighbor(index, -1), onClick: () => move(d.day, neighbor(index, -1)) },
                                d.path && { label: "Reculer d'un jour ▼", disabled: !neighbor(index, 1), onClick: () => move(d.day, neighbor(index, 1)) },
                                d.path && { label: d.locked ? "Déverrouiller" : "Verrouiller",
                                  onClick: () => act(d.day, `/${d.day}/lock`, { method: "POST", body: { locked: !d.locked } }) },
                                d.path && { label: "Supprimer", danger: true, onClick: () => act(d.day, `/${d.day}`, { method: "DELETE" },
                                  `Supprimer le défi #${d.number} ? La génération de la nuit remplira ce jour.`) },
                              ]} />
                            </>
                          )}
                        </td>
                      </tr>
                      {open[d.day] === "candidates" && (
                        <tr className="admin-panel-row"><td colSpan={COLUMNS}>
                          {!candidates[d.day] ? <span className="muted">Calcul des propositions…</span> : (
                            <div className="admin-candidates">
                              {candidates[d.day].map((c, i) => (
                                <Fragment key={i}>
                                  {c.path.map((p, k) => <Person key={p.qid} person={p} hidden={k === 1} />)}
                                  <span className="muted" title={`${KINDS[c.kind][1]} · ${ERAS[c.era][1]}`}>
                                    {KINDS[c.kind][0]}{ERAS[c.era][0]} · {c.alternatives} possible{c.alternatives > 1 ? "s" : ""}</span>
                                  <button className="btn" onClick={() => act(d.day, `/${d.day}/set`, { method: "POST",
                                    body: { youth: c.path[0].qid, middle: c.path[1].qid, contrast: c.path[2].qid } })}>Choisir</button>
                                </Fragment>
                              ))}
                              {candidates[d.day].length === 0 && <span className="muted">Aucune proposition.</span>}
                            </div>
                          )}
                        </td></tr>
                      )}
                      {open[d.day] === "edit" && (
                        <tr className="admin-panel-row"><td colSpan={COLUMNS}>
                          <ManualEditor onCancel={() => toggle(d.day, "edit")}
                            onSave={(body) => act(d.day, `/${d.day}/set`, { method: "POST", body })} />
                        </td></tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
