import { useState, useEffect } from "react";

export default function Game() {
  const [people, setPeople] = useState([]);
  const [p1, setP1] = useState("");
  const [p2, setP2] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetch("http://127.0.0.1:8000/graph")
      .then(res => res.json())
      .then(data => {
        setPeople(data.nodes.map(n => n.label));
      });
  }, []);

  const handleGuess = async () => {
    const res = await fetch(`http://127.0.0.1:8000/shortest_path?person1=${encodeURIComponent(p1)}&person2=${encodeURIComponent(p2)}`);
    const data = await res.json();
    setResult(data);
  };

  return (
    <div>
      <h2>Devinez le nombre de relations</h2>
      <select onChange={e => setP1(e.target.value)} value={p1}>
        <option value="">Personne 1</option>
        {people.map(p => <option key={p} value={p}>{p}</option>)}
      </select>
      <select onChange={e => setP2(e.target.value)} value={p2}>
        <option value="">Personne 2</option>
        {people.map(p => <option key={p} value={p}>{p}</option>)}
      </select>
      <button onClick={handleGuess} disabled={!p1 || !p2}>Vérifier</button>

      {result && result.nb_relations !== null && (
        <div>
          <p>Nombre minimal de relations : {result.nb_relations}</p>
          <p>Chemin : {result.chemin.join(" → ")}</p>
        </div>
      )}
    </div>
  );
}
