import { useEffect, useMemo, useState } from "react";

export default function GuessRelations() {
  const [people, setPeople] = useState([]);
  const [p1, setP1] = useState(null); // DB label
  const [p2, setP2] = useState(null); // DB label
  const [guess, setGuess] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [outcome, setOutcome] = useState(null); // { actual: number, chemin: string[], correct: boolean }

  const formatNode = (label) =>
    (label || "")
      .toString()
      .replaceAll("_", " ")
      .replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());

  const getWikiUrl = (label) => `https://fr.wikipedia.org/wiki/${encodeURIComponent(label || "")}`;

  useEffect(() => {
    fetch("http://127.0.0.1:8000/graph")
      .then((res) => res.json())
      .then((data) => {
        const labels = data.nodes.map((n) => n.label);
        setPeople(labels);
      })
      .catch(() => setError("Impossible de récupérer la liste des personnes."));
  }, []);

  const newChallenge = () => {
    setError(null);
    setOutcome(null);
    setGuess("");
    if (people.length < 2) return;
    const i1 = Math.floor(Math.random() * people.length);
    let i2 = Math.floor(Math.random() * people.length);
    // ensure different
    if (i2 === i1) {
      i2 = (i2 + 1) % people.length;
    }
    setP1(people[i1]);
    setP2(people[i2]);
  };

  // Start a challenge when people are loaded
  useEffect(() => {
    if (people.length >= 2 && (p1 == null || p2 == null)) {
      newChallenge();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [people]);

  const canSubmit = useMemo(() => {
    const n = Number(guess);
    return p1 && p2 && Number.isFinite(n) && n >= 0 && !loading;
  }, [p1, p2, guess, loading]);

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setOutcome(null);
    try {
      const res = await fetch(
        `http://127.0.0.1:8000/shortest_path?person1=${encodeURIComponent(p1)}&person2=${encodeURIComponent(p2)}`
      );
      const data = await res.json();
      if (data && typeof data.nb_relations === "number") {
        const actual = data.nb_relations;
        const correct = Number(guess) === actual;
        setOutcome({ actual, chemin: Array.isArray(data.chemin) ? data.chemin : [], correct });
      } else {
        setError("Aucun chemin trouvé entre ces deux personnes. Essayez un nouveau défi.");
      }
    } catch (e) {
      setError("Erreur lors du calcul du chemin.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">Devinez le nombre de relations</span>
        <div>
          <button className="btn" onClick={newChallenge} disabled={people.length < 2 || loading}>
            Nouveau défi
          </button>
        </div>
      </div>
      <div className="panel-body">
        {!p1 || !p2 ? (
          <p className="muted" style={{ margin: 0 }}>Chargement des personnes…</p>
        ) : (
          <>
            <p style={{ marginTop: 0 }}>
              Entre
              {" "}
              <a
                href={getWikiUrl(p1)}
                target="_blank"
                rel="noopener noreferrer"
                className="chemin-link"
              >
                {formatNode(p1)}
              </a>
              {" "}et{" "}
              <a
                href={getWikiUrl(p2)}
                target="_blank"
                rel="noopener noreferrer"
                className="chemin-link"
              >
                {formatNode(p2)}
              </a>
            </p>

            <div className="row" style={{ alignItems: "end" }}>
              <div>
                <label htmlFor="guess" className="muted">Votre estimation</label>
                <input
                  id="guess"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  step={1}
                  value={guess}
                  onChange={(e) => setGuess(e.target.value)}
                  placeholder="Ex: 3"
                />
              </div>
              <div>
                <button className="btn" onClick={handleSubmit} disabled={!canSubmit}>
                  {loading ? "Vérification…" : "Valider"}
                </button>
              </div>
            </div>

            {error && (
              <div className="error-box" style={{ marginTop: 12 }}>
                <p style={{ margin: 0 }}>{error}</p>
              </div>
            )}

            {outcome && (
              <div className="panel" style={{ marginTop: 12, borderRadius: 12 }}>
                <div className="panel-body">
                  {outcome.correct ? (
                    <p style={{ margin: 0, fontWeight: 600, color: "var(--success)" }}>✅ Bonne réponse !</p>
                  ) : (
                    <p style={{ margin: 0, fontWeight: 600, color: "var(--danger)" }}>❌ Mauvaise réponse.</p>
                  )}
                  <p style={{ marginTop: 6 }}>
                    Nombre minimal de relations: <strong>{outcome.actual}</strong>
                  </p>
                  {outcome.chemin && outcome.chemin.length > 0 && (
                    <p className="muted" style={{ marginTop: 8 }}>
                      Chemin: {outcome.chemin.map((node, idx) => (
                        <span key={`${node}-${idx}`}>
                          <a href={getWikiUrl(node)} target="_blank" rel="noopener noreferrer" className="chemin-link">
                            {formatNode(node)}
                          </a>
                          {idx < outcome.chemin.length - 1 ? " → " : ""}
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
