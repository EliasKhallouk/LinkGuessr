// Cases d'essais façon Framed / Wordle : ✕ rouge par erreur, ✓ vert pour la bonne réponse, vides ensuite.
export default function TriesTiles({ total, wrong, solved, label }) {
  const cells = Array.from({ length: total }, (_, i) => (i < wrong ? "wrong" : solved && i === wrong ? "win" : "empty"));
  return (
    <span className="tries" role="img" aria-label={label}>
      {cells.map((c, i) => (
        <span key={i} className={`tile is-${c}`}>{c === "wrong" ? "✕" : c === "win" ? "✓" : ""}</span>
      ))}
    </span>
  );
}
