import { useEffect, useState } from "react";

export default function Game() {
  const [people, setPeople] = useState([]);
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/graph")
      .then(res => res.json())
      .then(data => {
        setPeople(data.nodes.map(n => n.label));
      });
  }, []);

  const handleGuess = async () => {
    setLoading(true);
    try {
      const res = await fetch(`http://127.0.0.1:8000/shortest_path?person1=${encodeURIComponent(p1)}&person2=${encodeURIComponent(p2)}`);
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
              <label>Personne 1</label>
              <select onChange={e => setP1(e.target.value)} value={p1}>
                <option value="">Sélectionner...</option>
                {people.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Personne 2</label>
              <select onChange={e => setP2(e.target.value)} value={p2}>
                <option value="">Sélectionner...</option>
                {people.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <button className="btn" onClick={handleGuess} disabled={!p1 || !p2 || loading}>
              {loading ? "Calcul…" : "Vérifier"}
            </button>
          </div>

          {!result && (
            <p className="muted" style={{ margin: 0 }}>Choisissez deux personnes puis cliquez sur Vérifier.</p>
          )}

          {result && result.nb_relations !== null && (
            <div className="panel" style={{ borderRadius: 12 }}>
              <div className="panel-body">
                <p className="kpi">Nombre minimal de relations</p>
                <p style={{ fontSize: 28, margin: 0, fontWeight: 700 }}>{result.nb_relations}</p>
                {result.chemin && (
                  <p className="muted" style={{ marginTop: 8 }}>
                    Chemin : {result.chemin.join(" → ")}
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
