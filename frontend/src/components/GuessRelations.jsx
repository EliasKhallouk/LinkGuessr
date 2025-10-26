import { useEffect, useMemo, useRef, useState } from "react";
import { apiUrl } from "../config";
import { useI18n } from "../i18n/I18nProvider";

export default function GuessRelations() {
  const { t } = useI18n();
  const [p1, setP1] = useState(null); // DB label
  const [p2, setP2] = useState(null); // DB label
  const [guess, setGuess] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [outcome, setOutcome] = useState(null); // { actual: number, chemin: string[], correct: boolean }
  const [prefetchedAnswer, setPrefetchedAnswer] = useState(null); // { actual, chemin } pré-calculé et caché

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
  const [submitError, setSubmitError] = useState(null);
  const nextBtnRef = useRef(null);
  const guessInputRef = useRef(null);
  const [showScorePopup, setShowScorePopup] = useState(false);

  const formatNode = (label) =>
    (label || "")
      .toString()
      .replaceAll("_", " ")
      .replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());

  const getWikiUrl = (label) => `https://fr.wikipedia.org/wiki/${encodeURIComponent(label || "")}`;


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

  // After answering, auto-focus the Next button so Enter triggers it
  useEffect(() => {
    if (gameActive && answered && timeLeft > 0) {
      nextBtnRef.current?.focus();
    }
  }, [gameActive, answered, timeLeft]);

  // On each new challenge (answered=false with valid people), focus the guess input
  useEffect(() => {
    if (!answered && p1 && p2) {
      // small delay to ensure input is in DOM and enabled
      requestAnimationFrame(() => {
        if (guessInputRef.current) {
          guessInputRef.current.focus();
          // select current value for quick overwrite
          try { guessInputRef.current.select?.(); } catch {}
        }
      });
    }
  }, [answered, p1, p2]);

  const newChallenge = async () => {
    setError(null);
    setOutcome(null);
    setPrefetchedAnswer(null);
    setGuess("");
    setAnswered(false);
    try {
      const res = await fetch(apiUrl(`/challenge`));
      if (!res.ok) throw new Error("challenge");
      const data = await res.json();
      if (!data || !data.p1 || !data.p2) throw new Error("challenge");
      setP1(data.p1);
      setP2(data.p2);
      // Pré-calcul: garder la réponse en cache mais ne pas l'afficher avant validation
      if (typeof data.nb_relations === "number") {
        setPrefetchedAnswer({ actual: data.nb_relations, chemin: Array.isArray(data.chemin) ? data.chemin : [] });
      }
    } catch (e) {
      setError(t("guess.errorLoadPeople"));
    }
  };

  // Start a challenge once mounted
  useEffect(() => {
    // Always fetch a first challenge on mount
    newChallenge();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      // Si la réponse est pré-calculée depuis /challenge, évite un aller-retour
      let data = prefetchedAnswer ? { nb_relations: prefetchedAnswer.actual, chemin: prefetchedAnswer.chemin } : null;
      if (!data) {
        const res = await fetch(
          apiUrl(`/shortest_path?person1=${encodeURIComponent(p1)}&person2=${encodeURIComponent(p2)}`)
        );
        data = await res.json();
      }
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
            // Show score popup for perfect answers
            setShowScorePopup(true);
            setTimeout(() => setShowScorePopup(false), 3000);
          } else {
            setStreak(0);
          }

          setScore((sc) => sc + points);
          setTotalAnswered((ta) => ta + 1);
        }
      } else {
        setError(t("guess.errorNoPath"));
      }
    } catch (e) {
      setError(t("guess.errorCompute"));
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
    <>
    <section className="panel fade-in">
      <div className="panel-header">
  <span className="panel-title">{t("guess.titleNumber")}</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {gameActive ? (
            <>
              <span className="kpi">⏱ <strong>{formatTime(timeLeft)}</strong></span>
              <span className="kpi">⭐ <strong>{score}</strong></span>
              <button className="btn" onClick={stopGame}>{t("guess.stop")}</button>
            </>
          ) : (
            <>
              <button className="btn" onClick={newChallenge} disabled={loading}>
                {t("guess.newChallenge")}
              </button>
              <button className="btn" onClick={startGame} disabled={loading}>{t("guess.startGame", { seconds: GAME_DURATION })}</button>
            </>
          )}
        </div>
      </div>
      <div className="panel-body">
        {!p1 || !p2 ? (
          <p className="muted" style={{ margin: 0 }}>{t("guess.loadingPeople")}</p>
        ) : (
          <>
            {gameActive && (
              <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap" }}>
                <span className="kpi">{t("guess.score")}: <strong>{score}</strong></span>
                <span className="kpi">{t("guess.streak")}: <strong>{streak}</strong> 🔥</span>
                <span className="kpi">{t("guess.time")}: <strong>{formatTime(timeLeft)}</strong></span>
              </div>
            )}
            
            
            
            <p style={{ marginTop: 0 }}>
              {t("guess.between")}
              {" "}
              <a
                href={getWikiUrl(p1)}
                target="_blank"
                rel="noopener noreferrer"
                className="chemin-link"
              >
                {formatNode(p1)}
              </a>
              {" "}{t("guess.and")} {" "}
              <a
                href={getWikiUrl(p2)}
                target="_blank"
                rel="noopener noreferrer"
                className="chemin-link"
              >
                {formatNode(p2)}
              </a>
            </p>

            <form
              className="row"
              style={{ alignItems: "end" }}
              onSubmit={(e) => { e.preventDefault(); if (canSubmit) handleSubmit(); }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  if (canSubmit) {
                    handleSubmit();
                  } else if (gameActive && answered && timeLeft > 0) {
                    newChallenge();
                  }
                }
              }}
            >
              <div>
                <label htmlFor="guess" className="muted">{t("guess.estimation")}</label>
                <input
                  ref={guessInputRef}
                  id="guess"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  step={1}
                  value={guess}
                  onChange={(e) => setGuess(e.target.value)}
                  placeholder={t("guess.exampleNumber")}
                  disabled={gameActive && (answered || timeLeft <= 0)}
                />
              </div>
              <div>
                <button type="submit" className="btn" disabled={!canSubmit}>
                  {loading ? t("guess.verifying") : t("guess.verify")}
                </button>
              </div>
            </form>

            {error && (
              <div className="error-box" style={{ marginTop: 12 }}>
                <p style={{ margin: 0 }}>{error}</p>
              </div>
            )}

            {outcome && (
              <div className="panel" style={{ marginTop: 12, borderRadius: 12 }}>
                <div className="panel-body">
                  {outcome.correct ? (
                    <p style={{ margin: 0, fontWeight: 600, color: "var(--success)" }}>{t("guess.good")}</p>
                  ) : (
                    <p style={{ margin: 0, fontWeight: 600, color: "var(--danger)" }}>{t("guess.bad")}</p>
                  )}
                  <p style={{ marginTop: 6 }}>
                    {t("guess.minRelations")} <strong>{outcome.actual}</strong>
                  </p>
                  {outcome.chemin && outcome.chemin.length > 0 && (
                    <p className="muted" style={{ marginTop: 8 }}>
                      {t("guess.path")} {outcome.chemin.map((node, idx) => (
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
                      <button ref={nextBtnRef} className="btn" onClick={newChallenge}>{t("guess.next")}</button>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Game over summary */}
            {!gameActive && timeLeft === 0 && (
              <div className="panel" style={{ marginTop: 12, borderRadius: 12 }}>
                <div className="panel-body">
                  <p style={{ margin: 0, fontWeight: 600 }}>{t("guess.timeUp")}</p>
                  <p className="kpi" style={{ marginTop: 6 }}>
                    {t("guess.finalScore")} <strong>{score}</strong>
                  </p>
                  <p className="kpi" style={{ marginTop: 6 }}>
                    {t("guess.corrects")} <strong>{totalCorrect}</strong> / {t("guess.attempts")} <strong>{totalAnswered}</strong>
                  </p>
                  <div className="row" style={{ marginTop: 8, alignItems: "end" }}>
                    <div>
                      <label htmlFor="playerName" className="muted">{t("guess.yourName")}</label>
                      <input
                        id="playerName"
                        type="text"
                        maxLength={16}
                        value={playerName}
                        onChange={(e) => setPlayerName(e.target.value)}
                        placeholder={t("guess.exampleName")}
                      />
                    </div>
                    <div>
                      <button
                        className="btn"
                        onClick={async () => {
                          try {
                            setSubmitError(null);
                            // lightweight client-side normalization (server also normalizes)
                            const name = (playerName || "Anonyme").normalize('NFKD').replace(/\p{Diacritic}/gu, '').replace(/[^A-Za-z0-9 _-]/g, '').trim().slice(0,32) || "Anonyme";
                            const res = await fetch(apiUrl("/submit_score"), {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({ name, score, duration: GAME_DURATION })
                            });
                            if (!res.ok) {
                              const err = await res.json().catch(() => ({}));
                              setSubmitError(err && err.error ? err.error : t("guess.errorSave"));
                              return;
                            }
                            const data = await res.json();
                            setLastSubmit({ ok: data.ok, rank: data.rank, total: data.total });
                            if (data && data.ok) {
                              // notify leaderboard to refresh
                              window.dispatchEvent(new Event("leaderboard:refresh"));
                            }
                          } catch (e) {
                            setLastSubmit({ ok: false });
                            setSubmitError(t("guess.errorSave"));
                          }
                        }}
                        disabled={!playerName || (lastSubmit && lastSubmit.ok)}
                      >
                        {lastSubmit && lastSubmit.ok ? t("guess.scoreSaved") : t("guess.saveScore")}
                      </button>
                    </div>
                  </div>
                  {submitError && (
                    <div className="error-box" style={{ marginTop: 8 }}>
                      <p style={{ margin: 0 }}>{submitError}</p>
                    </div>
                  )}
                  {lastSubmit && lastSubmit.ok && (
                    <p className="kpi" style={{ marginTop: 8 }}>
                      {t("guess.rank")} <strong>#{lastSubmit.rank}</strong> {t("guess.outOf")} {lastSubmit.total}
                    </p>
                  )}
                  <div style={{ marginTop: 8 }}>
                    <button className="btn" onClick={startGame}>{t("guess.retry")}</button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
    {showScorePopup && (
      <div className="toast-bottom">
        <div className="success-box" style={{ maxWidth: 420 }}>
          <strong>🎉 +100 {t("guess.score")}!</strong> {t("guess.good")}
        </div>
      </div>
    )}
    </>
  );
}
