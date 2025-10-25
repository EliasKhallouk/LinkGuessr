import { useEffect, useMemo, useState } from "react";
import { apiUrl } from "../config";
import Autocomplete from "./Autocomplete";

export default function Game() {
  const [people, setPeople] = useState([]);
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Canonicalize a display value to a DB key (lowercase + underscores)
  const canonicalize = (s) => (s || "").toString().trim().toLowerCase().replace(/\s+/g, "_");

  // Map from canonical key to the exact DB label as returned by the backend
  const canonicalToDb = useMemo(() => {
    const m = new Map();
    for (const label of people) {
      m.set(canonicalize(label), label);
    }
    return m;
  }, [people]);

  const resolveDbLabel = (input) => {
    const key = canonicalize(input);
    return canonicalToDb.get(key) || null;
  };

  const isValid = !!resolveDbLabel(p1) && !!resolveDbLabel(p2);
  const isSamePerson = !!p1 && !!p2 && canonicalize(p1) === canonicalize(p2);

  // helper to title-case and prettify node labels
  const formatNode = (label) =>
    (label || "")
      .toString()
      .replaceAll("_", " ")
      .replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());

  // A SUPPRIMER A L'AVENIR CAR NOM DANS LA BDD AVEC DES _ (DEJA BIEN FORMATÉ)
  // helper to build FR Wikipedia URL from a raw label
  const getWikiUrl = (label) => `https://fr.wikipedia.org/wiki/${encodeURIComponent(label || "")}`;

  useEffect(() => {
    fetch(apiUrl("/graph"))
      .then(res => res.json())
      .then(data => {
        setPeople(data.nodes.map(n => n.label));
      });
  }, []);

  const handleGuess = async () => {
    setLoading(true);
    setError(null);
    try {
      if (isSamePerson) {
        setError("Les deux personnes doivent être différentes !");
        setLoading(false);
        return;
      }
      const dbP1 = resolveDbLabel(p1);
      const dbP2 = resolveDbLabel(p2);
      if (!dbP1 || !dbP2) {
        setError("Nom inconnu. Veuillez sélectionner des personnes valides.");
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
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">Devinez le chemin</span>
      </div>
      <div className="panel-body">
        <div className="form" style={{ gap: 16 }}>
          <div className="row">
            <div>
              <Autocomplete
                id="ac-person-1"
                label="Personne 1"
                options={people}
                value={p1}
                onChange={setP1}
                placeholder="Tapez un nom…"
              />
            </div>
            <div>
              <Autocomplete
                id="ac-person-2"
                label="Personne 2"
                options={people}
                value={p2}
                onChange={setP2}
                placeholder="Tapez un nom…"
              />
            </div>
          </div>

          <div>
            <button className="btn" onClick={handleGuess} disabled={!isValid || loading || isSamePerson}>
              {loading ? "Calcul…" : "Vérifier"}
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
              Choisissez deux personnes puis cliquez sur Vérifier.
              {!isValid && (p1 || p2) ? " (nom inconnu)" : ""}
              {isSamePerson ? " (personnes identiques)" : ""}
            </p>
          )}

          {result && result.nb_relations !== null && (
            <div className="panel" style={{ borderRadius: 12 }}>
              <div className="panel-body">
                <p className="kpi">Nombre minimal de relations</p>
                <p style={{ fontSize: 28, margin: 0, fontWeight: 700 }}>{result.nb_relations}</p>
                {Array.isArray(result.chemin) && result.chemin.length > 0 && (
                  <p className="muted" style={{ marginTop: 8 }}>
                    Chemin : {result.chemin.map((node, idx) => (
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
        </div>
      </div>
    </section>
  );
}
