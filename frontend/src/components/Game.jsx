import { useEffect, useState } from "react";
import { apiUrl } from "../config";
import { useI18n } from "../i18n/I18nProvider";
import Autocomplete from "./Autocomplete";

export default function Game() {
  const { t } = useI18n();
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [popularPairs, setPopularPairs] = useState([]);

  // With server-backed autocomplete and raw selection, values should already be exact DB labels
  const resolveDbLabel = (input) => (input || "").toString().trim() || null;

  // Resolve to the exact DB label by querying the backend search
  const resolveLabelFromDb = async (input) => {
    const qs = (input || "").trim();
    if (!qs) return null;
    try {
      const res = await fetch(apiUrl(`/search_people?q=${encodeURIComponent(qs)}&limit=8`));
      if (!res.ok) return null;
      const data = await res.json();
      const results = Array.isArray(data.results) ? data.results : [];
      if (!results.length) return null;
      const qLower = qs.toLowerCase();
      const exact = results.find((r) =>
        r.toLowerCase() === qLower || r.replace(/_/g, " ").toLowerCase() === qLower
      );
      return exact || results[0];
    } catch {
      return null;
    }
  };

  const isValid = !!resolveDbLabel(p1) && !!resolveDbLabel(p2);
  const isSamePerson = !!p1 && !!p2 && p1.trim().toLowerCase() === p2.trim().toLowerCase();

  // helper to title-case and prettify node labels
  const formatNode = (label) =>
    (label || "")
      .toString()
      .replaceAll("_", " ")
      .replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());

  // A SUPPRIMER A L'AVENIR CAR NOM DANS LA BDD AVEC DES _ (DEJA BIEN FORMATÉ)
  // helper to build FR Wikipedia URL from a raw label
  const getWikiUrl = (label) => `https://fr.wikipedia.org/wiki/${encodeURIComponent(label || "")}`;

  // Server-backed search for autocomplete suggestions
  const queryPeople = async (q) => {
    const qs = (q || "").trim();
    if (!qs) return [];
    try {
      const res = await fetch(apiUrl(`/search_people?q=${encodeURIComponent(qs)}&limit=8`));
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data.results) ? data.results : [];
    } catch {
      return [];
    }
  };

  // fetch popular pairs (most requested shortest_path queries)
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await fetch(apiUrl('/popular_pairs?limit=10'));
        if (!res.ok) return;
        const data = await res.json();
        if (!mounted) return;
        if (data && Array.isArray(data.results)) setPopularPairs(data.results);
      } catch (e) {
        // ignore
      }
    })();
    return () => { mounted = false; };
  }, []);

  const handleGuess = async () => {
    setLoading(true);
    setError(null);
    try {
      if (isSamePerson) {
        setError(t("game.errorSame"));
        setLoading(false);
        return;
      }
      const dbP1 = await resolveLabelFromDb(p1);
      const dbP2 = await resolveLabelFromDb(p2);
      if (!dbP1 || !dbP2) {
        setError(t("game.errorUnknown"));
        setLoading(false);
        return;
      }

  const res = await fetch(apiUrl(`/shortest_path?person1=${encodeURIComponent(dbP1)}&person2=${encodeURIComponent(dbP2)}`));
      const data = await res.json();
      setResult(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">{t("game.titlePath")}</span>
      </div>
      <div className="panel-body">
        <form className="form" style={{ gap: 16 }} onSubmit={(e) => { e.preventDefault(); if (!loading && isValid && !isSamePerson) handleGuess(); }}>
          <div className="row">
            <div>
              <Autocomplete
                id="ac-person-1"
                label={t("game.person1")}
                options={[]}
                value={p1}
                onChange={setP1}
                placeholder={t("game.typeName")}
                onQuery={queryPeople}
                useRawOnSelect
              />
            </div>
            <div>
              <Autocomplete
                id="ac-person-2"
                label={t("game.person2")}
                options={[]}
                value={p2}
                onChange={setP2}
                placeholder={t("game.typeName")}
                onQuery={queryPeople}
                useRawOnSelect
              />
            </div>
          </div>

          <div>
            <button type="submit" className="btn" disabled={!isValid || loading || isSamePerson}>
              {loading ? t("game.calculating") : t("game.check")}
            </button>
          </div>

          {error && (
            <div className="error-box">
              <p style={{ margin: 0, marginBottom: 4 }}>⚠️ Erreur</p>
              <p style={{ margin: 0, fontSize: 14 }}>{error}</p>
            </div>
          )}

          {!result && !error && (
            <p className="muted" style={{ margin: 0 }}>
              {t("game.chooseTwo")}
              {!isValid && (p1 || p2) ? t("game.suffixUnknown") : ""}
              {isSamePerson ? t("game.suffixSame") : ""}
            </p>
          )}

          {result && result.nb_relations !== null && (
            <div className="panel" style={{ borderRadius: 12 }}>
              <div className="panel-body">
                <p className="kpi">{t("game.minRelations")}</p>
                <p style={{ fontSize: 28, margin: 0, fontWeight: 700 }}>{result.nb_relations}</p>
                {Array.isArray(result.chemin) && result.chemin.length > 0 && (
                  <p className="muted" style={{ marginTop: 8 }}>
                    {t("game.path")} {result.chemin.map((node, idx) => (
                      <span key={`${node}-${idx}`}>
                        <a href={getWikiUrl(node)} target="_blank" rel="noopener noreferrer" className="chemin-link">
                          {formatNode(node)}
                        </a>
                        {idx < result.chemin.length - 1 ? " → " : ""}
                      </span>
                    ))}
                  </p>
                )}
              </div>
            </div>
          )}
  </form>
      </div>
  </section>
    {popularPairs && popularPairs.length > 0 && (
      <section className="panel fade-in" style={{ marginTop: 12 }}>
        <div className="panel-header">
          <span className="panel-title">Paires les plus demandées</span>
        </div>
        <div className="panel-body">
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--muted)" }}>
                  <th style={{ padding: "8px" }}>#</th>
                  <th style={{ padding: "8px" }}>Personne A</th>
                  <th style={{ padding: "8px" }}>Personne B</th>
                  <th style={{ padding: "8px" }}>Requêtes</th>
                </tr>
              </thead>
              <tbody>
                {popularPairs.map((r, i) => (
                  <tr key={`${r.person1}-${r.person2}-${i}`} style={{ borderTop: "1px solid var(--border)" }}>
                    <td style={{ padding: "8px", width: 36 }}>{i + 1}</td>
                    <td style={{ padding: "8px" }}>
                      <a className="chemin-link" href={`https://fr.wikipedia.org/wiki/${encodeURIComponent(r.person1)}`} target="_blank" rel="noopener noreferrer">
                        { (r.person1 || '').toString().replaceAll('_', ' ') }
                      </a>
                    </td>
                    <td style={{ padding: "8px" }}>
                      <a className="chemin-link" href={`https://fr.wikipedia.org/wiki/${encodeURIComponent(r.person2)}`} target="_blank" rel="noopener noreferrer">
                        { (r.person2 || '').toString().replaceAll('_', ' ') }
                      </a>
                    </td>
                    <td style={{ padding: "8px", width: 80, textAlign: 'right' }}><strong>{r.count}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    )}
    </>
  );
}
