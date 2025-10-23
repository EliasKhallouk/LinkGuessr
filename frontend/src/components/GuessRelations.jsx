import { useEffect, useMemo, useState } from "react";

export default function GuessRelations() {
  const [people, setPeople] = useState([]);
  const [p1, setP1] = useState(null); // DB label
  const [p2, setP2] = useState(null); // DB label
  const [guess, setGuess] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [outcome, setOutcome] = useState(null); // { actual: number, chemin: string[], correct: boolean }

  // Game session state
  const GAME_DURATION = 60; // seconds
  const [gameActive, setGameActive] = useState(false);
  const [timeLeft, setTimeLeft] = useState(GAME_DURATION);
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0); // exact answers in a row
  const [answered, setAnswered] = useState(false); // current challenge answered?
  const [totalAnswered, setTotalAnswered] = useState(0);
  const [totalCorrect, setTotalCorrect] = useState(0);
  const [playerName, setPlayerName] = useState("");
  const [lastSubmit, setLastSubmit] = useState(null); // { ok, rank, total }

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

  // Countdown timer effect
  useEffect(() => {
    if (!gameActive) return;
    if (timeLeft <= 0) {
      setGameActive(false);
      return;
    }
    const id = setInterval(() => {
      setTimeLeft((t) => (t > 0 ? t - 1 : 0));
    }, 1000);
    return () => clearInterval(id);
  }, [gameActive, timeLeft]);

  const formatTime = (s) => {
    const m = Math.floor(s / 60).toString().padStart(2, "0");
    const ss = (s % 60).toString().padStart(2, "0");
    return `${m}:${ss}`;
  };

  const newChallenge = () => {
    setError(null);
    setOutcome(null);
    setGuess("");
    setAnswered(false);
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
    // Cannot submit if already answered current challenge or out of time during a game
    if (gameActive && (answered || timeLeft <= 0)) return false;
    return p1 && p2 && Number.isFinite(n) && n >= 0 && !loading;
  }, [p1, p2, guess, loading, gameActive, answered, timeLeft]);

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
        setAnswered(true);

        // Update scoring if in a session
        if (gameActive) {
          // Base scoring: exact=100, off by 1=60, off by 2=30, else 0
          const diff = Math.abs(Number(guess) - actual);
          let points = 0;
          if (diff === 0) points = 100;
          else if (diff === 1) points = 60;
          else if (diff === 2) points = 30;

          // Streak bonus for exact answers: +20 per current streak (before increment)
          if (diff === 0) {
            points += 20 * streak;
            setStreak((s) => s + 1);
            setTotalCorrect((c) => c + 1);
          } else {
            setStreak(0);
          }

          setScore((sc) => sc + points);
          setTotalAnswered((ta) => ta + 1);
        }
      } else {
        setError("Aucun chemin trouvé entre ces deux personnes. Essayez un nouveau défi.");
      }
    } catch (e) {
      setError("Erreur lors du calcul du chemin.");
    } finally {
      setLoading(false);
    }
  };

  const startGame = () => {
    setScore(0);
    setStreak(0);
    setTotalAnswered(0);
    setTotalCorrect(0);
    setTimeLeft(GAME_DURATION);
    setGameActive(true);
    // create a fresh challenge
    newChallenge();
    setLastSubmit(null);
  };

  const stopGame = () => {
    setGameActive(false);
  };

  return (
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">Devinez le nombre de relations</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {gameActive ? (
            <>
              <span className="muted" style={{ fontSize: 12 }}>⏱ {formatTime(timeLeft)}</span>
              <span className="muted" style={{ fontSize: 12 }}>⭐ {score}</span>
              <button className="btn" onClick={stopGame}>Arrêter</button>
            </>
          ) : (
            <>
              <button className="btn" onClick={newChallenge} disabled={people.length < 2 || loading}>
                Nouveau défi
              </button>
              <button className="btn" onClick={startGame} disabled={people.length < 2}>Lancer la partie ({GAME_DURATION}s)</button>
            </>
          )}
        </div>
      </div>
      <div className="panel-body">
        {!p1 || !p2 ? (
          <p className="muted" style={{ margin: 0 }}>Chargement des personnes…</p>
        ) : (
          <>
            {gameActive && (
              <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
                <span className="kpi"><strong>Score:</strong> {score}</span>
                <span className="kpi"><strong>Série:</strong> {streak}</span>
                <span className="kpi"><strong>Temps:</strong> {formatTime(timeLeft)}</span>
              </div>
            )}
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
                  disabled={gameActive && (answered || timeLeft <= 0)}
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
                  {gameActive && timeLeft > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <button className="btn" onClick={newChallenge}>Suivant</button>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Game over summary */}
            {!gameActive && timeLeft === 0 && (
              <div className="panel" style={{ marginTop: 12, borderRadius: 12 }}>
                <div className="panel-body">
                  <p style={{ margin: 0, fontWeight: 600 }}>⏳ Temps écoulé !</p>
                  <p className="kpi" style={{ marginTop: 6 }}>
                    Score final: <strong>{score}</strong>
                  </p>
                  <p className="kpi" style={{ marginTop: 6 }}>
                    Exactes: <strong>{totalCorrect}</strong> / Tentatives: <strong>{totalAnswered}</strong>
                  </p>
                  <div className="row" style={{ marginTop: 8, alignItems: "end" }}>
                    <div>
                      <label htmlFor="playerName" className="muted">Votre pseudo</label>
                      <input
                        id="playerName"
                        type="text"
                        maxLength={32}
                        value={playerName}
                        onChange={(e) => setPlayerName(e.target.value)}
                        placeholder="Ex: Elias"
                      />
                    </div>
                    <div>
                      <button
                        className="btn"
                        onClick={async () => {
                          try {
                            const res = await fetch("http://127.0.0.1:8000/submit_score", {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ name: playerName || "Anonyme", score, duration: GAME_DURATION })
                            });
                            const data = await res.json();
                            setLastSubmit({ ok: data.ok, rank: data.rank, total: data.total });
                          } catch (e) {
                            setLastSubmit({ ok: false });
                          }
                        }}
                        disabled={!playerName || (lastSubmit && lastSubmit.ok)}
                      >
                        {lastSubmit && lastSubmit.ok ? "Score enregistré" : "Enregistrer le score"}
                      </button>
                    </div>
                  </div>
                  {lastSubmit && lastSubmit.ok && (
                    <p className="kpi" style={{ marginTop: 8 }}>
                      Rang: <strong>#{lastSubmit.rank}</strong> sur {lastSubmit.total}
                    </p>
                  )}
                  <div style={{ marginTop: 8 }}>
                    <button className="btn" onClick={startGame}>Rejouer</button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
