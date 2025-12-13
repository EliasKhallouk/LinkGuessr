import { useEffect, useState } from "react";
import { apiUrl } from "../config";
import { useI18n } from "../i18n/I18nProvider";

export default function ConnectRelay() {
  const { t } = useI18n();
  const [startA, setStartA] = useState(null);
  const [startB, setStartB] = useState(null);
  const [currentTarget, setCurrentTarget] = useState(null); // label of target person we try to reach
  const [currentNode, setCurrentNode] = useState(null); // current selected node label
  const [neighbors, setNeighbors] = useState([]);
  const [search, setSearch] = useState("");
  const [history, setHistory] = useState([]);
  const [message, setMessage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [bestLen, setBestLen] = useState(null);
  const [bestPath, setBestPath] = useState([]);
  const [restrictedMode, setRestrictedMode] = useState(false);
  const [helpMessage, setHelpMessage] = useState("");
  const [hintShown, setHintShown] = useState(false);

  const formatNode = (label) =>
    (label || "")
      .toString()
      .replaceAll("_", " ")
      .replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());

  const getWikiUrl = (label) => `https://fr.wikipedia.org/wiki/${encodeURIComponent(label || "")}`;

  const loadChallenge = async () => {
    setMessage(null);
    setNeighbors([]);
    setHistory([]);
    setSuccess(false);
    setBestLen(null);
    setBestPath([]);
  setRestrictedMode(false);
  setHelpMessage("");
  setHintShown(false);
    setLoading(true);
    try {
      const res = await fetch(apiUrl(`/challenge`));
      if (!res.ok) throw new Error("challenge");
      const data = await res.json();
      setStartA(data.p1 || null);
      setStartB(data.p2 || null);
      // choose randomly which one is the target and which is the starting current node
      const chooseTarget = Math.random() < 0.5;
      const target = chooseTarget ? data.p2 : data.p1;
      const current = chooseTarget ? data.p1 : data.p2;
      setCurrentTarget(target);
      setCurrentNode(current);
      setHistory([current]);
      // preload PCC from current to target
      try {
        const res2 = await fetch(apiUrl(`/shortest_paths?person1=${encodeURIComponent(current)}&person2=${encodeURIComponent(target)}`));
        const d2 = await res2.json();
        if (d2 && typeof d2.nb_relations === 'number') {
          setBestLen(d2.nb_relations);
          setBestPath(Array.isArray(d2.chemin) ? d2.chemin : []);
        } else if (d2 && typeof d2.min_len === 'number') {
          const chemin = Array.isArray(d2.chemins) && d2.chemins.length ? d2.chemins[0].chemin : [];
          setBestLen(d2.min_len);
          setBestPath(chemin);
        }
      } catch {}
      // preload neighbors
      await loadNeighbors(current);
    } catch (e) {
      setMessage(t("relay.errorLoad"));
    } finally {
      setLoading(false);
    }
  };

  const loadNeighbors = async (person) => {
    setLoading(true);
    try {
      const res = await fetch(apiUrl(`/neighbors?person=${encodeURIComponent(person)}&limit=500`));
      if (!res.ok) throw new Error("neighbors");
      const data = await res.json();
      const list = Array.isArray(data.results) ? data.results.map(r => r.name) : [];
      // Always update with latest neighbors from backend; restriction will override when needed
      setNeighbors(list);
    } catch (e) {
      setNeighbors([]);
      setMessage(t("relay.errorNeighbors"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadChallenge();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSelectNeighbor = async (label) => {
    // user selects a neighbor to move to
    if (!label) return;
    const next = label;
    const newHistory = [...history, next];
    setHistory(newHistory);
    setCurrentNode(next);
    // check success
    if (next === currentTarget) {
      setMessage(t("relay.success", { steps: newHistory.length - 1 }));
      setNeighbors([]);
      setSuccess(true);
      // fetch the shortest path between initial start and target to compare
      try {
        const startRoot = newHistory[0];
        const res = await fetch(apiUrl(`/shortest_paths?person1=${encodeURIComponent(startRoot)}&person2=${encodeURIComponent(currentTarget)}`));
        const data = await res.json();
        if (data && typeof data.nb_relations === 'number') {
          setBestLen(data.nb_relations);
          setBestPath(Array.isArray(data.chemin) ? data.chemin : []);
        } else if (data && typeof data.min_len === 'number') {
          const chemin = Array.isArray(data.chemins) && data.chemins.length ? data.chemins[0].chemin : [];
          setBestLen(data.min_len);
          setBestPath(chemin);
        }
      } catch (e) {
        // ignore errors, keep success
      }
      return;
    }
    // otherwise load neighbors of next
    await loadNeighbors(next);

    // Hint: if user's path length so far exceeds PCC by >=2, provide the next correct person
    // Compute next correct step using local shortest path from currentNode to target
    if (bestLen !== null) {
      const userLen = newHistory.length - 1; // edges from initial start
      if (!hintShown && userLen >= (bestLen + 2)) {
        try {
          const r = await fetch(apiUrl(`/shortest_paths?person1=${encodeURIComponent(currentNode)}&person2=${encodeURIComponent(currentTarget)}`));
          const d = await r.json();
          let localPath = [];
          if (d && typeof d.nb_relations === 'number') {
            localPath = Array.isArray(d.chemin) ? d.chemin : [];
          } else if (d && typeof d.min_len === 'number') {
            localPath = Array.isArray(d.chemins) && d.chemins.length ? d.chemins[0].chemin : [];
          }
          if (Array.isArray(localPath) && localPath.length >= 2 && localPath[0] === currentNode) {
            const nextCorrect = localPath[1];
            setHelpMessage(t("relay.hintNext", { name: formatNode(nextCorrect) }));
            setHintShown(true);
          }
        } catch {}
      }
    }

    // Restrict choices to 5 if still off by >=2 after hint: include the correct next PCC node
    // Restrict choices to 5 if still off by >=2 after hint: include the correct next PCC node
    if (bestLen !== null) {
      const userLen2 = newHistory.length - 1; // edges
      if (userLen2 >= (bestLen + 2)) {
        try {
          const r2 = await fetch(apiUrl(`/shortest_paths?person1=${encodeURIComponent(currentNode)}&person2=${encodeURIComponent(currentTarget)}`));
          const d2 = await r2.json();
          let localPath2 = [];
          if (d2 && typeof d2.nb_relations === 'number') {
            localPath2 = Array.isArray(d2.chemin) ? d2.chemin : [];
          } else if (d2 && typeof d2.min_len === 'number') {
            localPath2 = Array.isArray(d2.chemins) && d2.chemins.length ? d2.chemins[0].chemin : [];
          }
          const nextCorrect2 = (Array.isArray(localPath2) && localPath2.length >= 2 && localPath2[0] === currentNode) ? localPath2[1] : null;
          if (nextCorrect2 && neighbors.length > 0) {
            const others = neighbors.filter(n => n !== nextCorrect2);
            const shuffled = others.sort(() => Math.random() - 0.5);
            // Total choices: 4 (1 correct + 3 others)
            const picked = [nextCorrect2, ...shuffled.slice(0, Math.max(0, 4 - 1))];
            setNeighbors(picked);
            setRestrictedMode(true);
            setHelpMessage(t("relay.restricted"));
          }
        } catch {}
      }
    }
  };

  return (
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">{t("relay.title")}</span>
        <div>
          <button className="btn" onClick={loadChallenge} disabled={loading}>{t("relay.new")}</button>
        </div>
      </div>
      <div className="panel-body">
        {!startA || !startB ? (
          <p className="muted">{t("relay.loading")}</p>
        ) : (
          <>
            {helpMessage && (
              <div className="panel" style={{ marginBottom: 8 }}>
                <div className="panel-body">
                  <p style={{ margin: 0 }}>{helpMessage}</p>
                </div>
              </div>
            )}
            <p style={{ marginTop: 0 }}>
              {t("relay.prompt")} <strong>{formatNode(currentTarget)}</strong>
            </p>

            {/* Debug info to verify backend and query state */}
            <p className="muted" style={{ marginTop: 4 }}>
              API: <code>{apiUrl("")}</code> · Personne courante: <code>{currentNode}</code> · Voisins: <strong>{neighbors.length}</strong>
            </p>

            <p className="muted">
              {t("relay.current")} <a href={getWikiUrl(currentNode)} target="_blank" rel="noreferrer" className="chemin-link">{formatNode(currentNode)}</a>
            </p>

            <div style={{ marginTop: 8 }}>
              <label htmlFor="relay-search" className="muted">{t("relay.searchLabel")}</label>
              <input
                id="relay-search"
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t("relay.searchPlaceholder")}
              />
            </div>

            <div style={{ marginTop: 8, maxHeight: 300, overflowY: 'auto', border: '1px solid var(--border)', borderRadius: 8, padding: 8 }}>
              {neighbors.length === 0 ? (
                <p className="muted" style={{ margin: 0 }}>{t("relay.noNeighbors")}</p>
              ) : (
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {neighbors
                    .filter(n => {
                      const s = (search || "").trim().toLowerCase();
                      if (!s) return true;
                      const formatted = formatNode(n).toLowerCase();
                      return formatted.includes(s);
                    })
                    .map((n) => (
                      <li key={n} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px dashed var(--border)' }}>
                        <a href={getWikiUrl(n)} target="_blank" rel="noreferrer" className="chemin-link">{formatNode(n)}</a>
                        <button className="btn" onClick={() => handleSelectNeighbor(n)}>{t("relay.choose")}</button>
                      </li>
                    ))}
                </ul>
              )}
            </div>

            <div style={{ marginTop: 12 }}>
              <strong>{t("relay.path")}</strong>
              <div style={{ marginTop: 6 }}>
                {history.map((h, idx) => (
                  <span key={`${h}-${idx}`}>
                    <a href={getWikiUrl(h)} target="_blank" rel="noreferrer" className="chemin-link">{formatNode(h)}</a>
                    {idx < history.length - 1 ? " → " : ""}
                  </span>
                ))}
              </div>
            </div>

            {message && (
              success ? (
                <div className="success-box" style={{ marginTop: 12 }}>
                  <p style={{ margin: 0 }}>{message}</p>
                </div>
              ) : (
                <div className="panel" style={{ marginTop: 12 }}>
                  <div className="panel-body">
                    <p style={{ margin: 0 }}>{message}</p>
                  </div>
                </div>
              )
            )}

            {success && bestLen !== null && (
              <div className="panel" style={{ marginTop: 12 }}>
                <div className="panel-body">
                  <p style={{ margin: 0 }}>
                    <strong>{t("relay.bestTitle")}</strong> — {t("relay.minRelations")} <strong>{bestLen}</strong>
                  </p>
                  {bestPath && bestPath.length > 0 && (
                    <p className="muted" style={{ marginTop: 6 }}>
                      {t("relay.bestPath")} {bestPath.map((node, idx) => (
                        <span key={`${node}-${idx}`}>
                          <a href={getWikiUrl(node)} target="_blank" rel="noreferrer" className="chemin-link">{formatNode(node)}</a>
                          {idx < bestPath.length - 1 ? " → " : ""}
                        </span>
                      ))}
                    </p>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
