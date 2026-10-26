import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { useI18n } from "../i18n/I18nProvider";
import DifficultyPicker from "./DifficultyPicker";
import PathView from "./PathView";
import { duelUrl } from "../lib/share";
import { load, save } from "../lib/storage";
import PersonChip from "./PersonChip";
import ShareButton from "./ShareButton";
import { newRound, track } from "../lib/tracking";
import Feedback from "./Feedback";
import { confetti } from "../lib/confetti";

const GAME = "guess_count";
const GAME_DURATION = 60; // secondes

// Points : exact 100 (+20 par bonne réponse d'affilée), à 1 près 60, à 2 près 30.
function pointsFor(diff, streak) {
  if (diff === 0) return 100 + 20 * streak;
  if (diff === 1) return 60;
  if (diff === 2) return 30;
  return 0;
}

// `rivalScore` : score à battre quand on arrive par un lien de duel.
export default function GuessRelations({ rivalScore = null }) {
  const { t } = useI18n();
  const [difficulty, setDifficulty] = useState("moyen");
  const [pair, setPair] = useState(null);          // { from, to, length, n_paths }
  const [guess, setGuess] = useState("");
  const [outcome, setOutcome] = useState(null);    // { actual, correct, details }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const shownAt = useRef(0);

  const [gameActive, setGameActive] = useState(false);
  const [timeLeft, setTimeLeft] = useState(GAME_DURATION);
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [totalAnswered, setTotalAnswered] = useState(0);
  const [totalCorrect, setTotalCorrect] = useState(0);
  const [playerName, setPlayerName] = useState("");
  const [lastSubmit, setLastSubmit] = useState(null);
  const [submitError, setSubmitError] = useState(null);
  const [popup, setPopup] = useState(null);
  const guessInputRef = useRef(null);
  const nextBtnRef = useRef(null);

  useEffect(() => {
    if (!gameActive) return;
    if (timeLeft <= 0) { setGameActive(false); return; }
    const id = setInterval(() => setTimeLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [gameActive, timeLeft]);

  // `focus` : place le curseur dans le champ. Par défaut seulement avec une souris : sur téléphone,
  // ouvrir le clavier sans action du joueur masquerait la moitié de l'écran.
  const newChallenge = async (focus = window.matchMedia?.("(pointer: fine)").matches) => {
    setError(null);
    setOutcome(null);
    setGuess("");
    setLoading(true);
    try {
      setPair(await api.randomPair({ difficulty }));
      shownAt.current = performance.now();
      if (focus) requestAnimationFrame(() => guessInputRef.current?.focus());
    } catch (e) {
      setError(e.message || t("guess.errorLoadPeople"));
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { newChallenge(); }, [difficulty]);

  useEffect(() => {
    if (outcome && gameActive && timeLeft > 0) nextBtnRef.current?.focus();
  }, [outcome, gameActive, timeLeft]);

  const answered = !!outcome;
  const canSubmit = useMemo(() => {
    const n = Number(guess);
    return pair && guess !== "" && Number.isInteger(n) && n >= 0 && !answered && !loading
      && !(gameActive && timeLeft <= 0);
  }, [pair, guess, answered, loading, gameActive, timeLeft]);

  const handleSubmit = async () => {
    const actual = pair.length;
    const value = Number(guess);
    const diff = Math.abs(value - actual);
    setOutcome({ actual, correct: diff === 0, details: null });
    api.logEvent(GAME, {
      from: pair.from.qid, to: pair.to.qid, length: actual, n_paths: pair.n_paths, guess: value,
      ms: Math.round(performance.now() - shownAt.current), difficulty, timed: gameActive,
    });

    if (gameActive) {
      const points = pointsFor(diff, streak);
      setScore((s) => s + points);
      setTotalAnswered((n) => n + 1);
      if (diff === 0) {
        setStreak((s) => s + 1);
        setTotalCorrect((n) => n + 1);
      } else {
        setStreak(0);
      }
      if (points) {
        setPopup(points);
        setTimeout(() => setPopup(null), 1500);
      }
    }
    try {
      const details = await api.path(pair.from.qid, pair.to.qid, { limit: 1 });
      setOutcome((o) => o && { ...o, details });
    } catch { /* le chemin détaillé est un bonus */ }
  };

  const startGame = () => {
    newRound(GAME);
    track(GAME, "start", { duel: rivalScore != null });
    setScore(0);
    setStreak(0);
    setTotalAnswered(0);
    setTotalCorrect(0);
    setTimeLeft(GAME_DURATION);
    setLastSubmit(null);
    setSubmitError(null);
    setGameActive(true);
    newChallenge(true);
  };

  const saveScore = async () => {
    try {
      setSubmitError(null);
      const res = await api.submitScore(GAME, playerName, score, GAME_DURATION);
      setLastSubmit(res);
      window.dispatchEvent(new Event("leaderboard:refresh"));
    } catch (e) {
      setSubmitError(e.message || t("guess.errorSave"));
    }
  };

  // Fin de partie chronométrée : un seul événement « finish » par partie.
  useEffect(() => {
    if (!gameActive && timeLeft === 0) {
      track(GAME, "finish", { score, answered: totalAnswered, correct: totalCorrect, duel: rivalScore != null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameActive, timeLeft]);

  // Record personnel, gardé dans le navigateur.
  const [best, setBest] = useState(() => load("lg-best-count", 0));
  useEffect(() => {
    if (!gameActive && timeLeft === 0 && score > best) {
      save("lg-best-count", score);
      setBest(score);
      confetti(); // nouveau record perso
    }
  }, [gameActive, timeLeft, score, best]);

  const formatTime = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  return (
    <>
      <section className="panel fade-in">
        <div className="panel-header">
          <span className="panel-title">{t("guess.titleNumber")}</span>
          <div className="toolbar">
            {gameActive ? (
              <>
                <span className="kpi">⏱ <strong>{formatTime(timeLeft)}</strong></span>
                <span className="kpi">⭐ <strong>{score}</strong></span>
                {streak > 1 && <span className="kpi">🔥 <strong>{streak}</strong></span>}
                <button className="btn" onClick={() => setGameActive(false)}>{t("guess.stop")}</button>
              </>
            ) : (
              <>
                <DifficultyPicker value={difficulty} onChange={setDifficulty} />
                <button className="btn" onClick={newChallenge} disabled={loading}>{t("guess.newChallenge")}</button>
                <button className="btn btn-primary" onClick={startGame} disabled={loading}>
                  {t("guess.startGame", { seconds: GAME_DURATION })}
                </button>
              </>
            )}
          </div>
        </div>
        <div className="panel-body">
          {gameActive && (
            <div className="timer-bar" role="progressbar" aria-label={t("guess.timeLeft")}
              aria-valuemin={0} aria-valuemax={GAME_DURATION} aria-valuenow={timeLeft}>
              <span className={timeLeft <= 10 ? "is-urgent" : ""} style={{ width: `${(100 * timeLeft) / GAME_DURATION}%` }} />
            </div>
          )}
          {error && <div className="error-box"><p style={{ margin: 0 }}>{error}</p></div>}
          {!pair ? (
            <p className="muted" style={{ margin: 0 }}>{t("guess.loadingPeople")}</p>
          ) : (
            <>
              <div className="pair">
                <PersonChip person={pair.from} showDescription size={56} />
                <span className="pair-sep">↔</span>
                <PersonChip person={pair.to} showDescription size={56} />
              </div>

              <form
                className="row"
                style={{ alignItems: "end", marginTop: 12 }}
                onSubmit={(e) => {
                  e.preventDefault();
                  if (canSubmit) handleSubmit();
                  else if (answered && gameActive && timeLeft > 0) newChallenge(true);
                }}
              >
                <div>
                  <label htmlFor="guess" className="muted">{t("guess.estimation")}</label>
                  <input
                    ref={guessInputRef}
                    id="guess"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    step={1}
                    value={guess}
                    onChange={(e) => setGuess(e.target.value)}
                    placeholder={t("guess.exampleNumber")}
                    disabled={answered}
                  />
                </div>
                <div>
                  <button type="submit" className="btn" disabled={!canSubmit}>{t("guess.verify")}</button>
                </div>
              </form>

              {outcome && (
                <div className={outcome.correct ? "success-box" : "panel result-box"} style={{ marginTop: 12 }}>
                  <p style={{ margin: 0, fontWeight: 600, color: outcome.correct ? "var(--success)" : "var(--danger)" }}>
                    {outcome.correct ? t("guess.good") : t("guess.bad")}
                  </p>
                  <p style={{ marginTop: 6 }}>
                    {t("guess.minRelations")} <strong>{outcome.actual}</strong>
                    {pair.n_paths > 1 && <span className="muted"> · {pair.n_paths.toLocaleString()} {t("guess.pathsCount")}</span>}
                  </p>
                  {outcome.details && (
                    <PathView path={outcome.details.paths[0]} persons={outcome.details.persons} hops={outcome.details.hops} />
                  )}
                  {timeLeft > 0 && (
                    <button ref={nextBtnRef} className="btn" style={{ marginTop: 8 }} onClick={newChallenge}>
                      {t("guess.next")}
                    </button>
                  )}
                </div>
              )}

              {!gameActive && timeLeft === 0 && (
                <div className="panel result-box" style={{ marginTop: 12 }}>
                  <p style={{ margin: 0, fontWeight: 600 }}>{t("guess.timeUp")}</p>
                  <p className="kpi" style={{ marginTop: 6 }}>{t("guess.finalScore")} <strong>{score}</strong>
                    <span className="muted"> · {t("guess.personalBest", { n: best })}</span></p>
                  <p className="kpi" style={{ marginTop: 6 }}>
                    {t("guess.corrects")} <strong>{totalCorrect}</strong> / {t("guess.attempts")} <strong>{totalAnswered}</strong>
                  </p>
                  <div className="row" style={{ marginTop: 8, alignItems: "end" }}>
                    <div>
                      <label htmlFor="playerName" className="muted">{t("guess.yourName")}</label>
                      <input id="playerName" type="text" maxLength={16} value={playerName}
                        onChange={(e) => setPlayerName(e.target.value)} placeholder={t("guess.exampleName")} />
                    </div>
                    <div>
                      <button className="btn" onClick={saveScore} disabled={!playerName || lastSubmit?.ok}>
                        {lastSubmit?.ok ? t("guess.scoreSaved") : t("guess.saveScore")}
                      </button>
                    </div>
                  </div>
                  {submitError && <div className="error-box" style={{ marginTop: 8 }}><p style={{ margin: 0 }}>{submitError}</p></div>}
                  {lastSubmit?.ok && (
                    <p className="kpi" style={{ marginTop: 8 }}>
                      {t("guess.rank")} <strong>#{lastSubmit.rank}</strong> {t("guess.outOf")} {lastSubmit.total}
                    </p>
                  )}
                  {rivalScore != null && (
                    <p style={{ marginTop: 8, fontWeight: 600 }}>
                      {score > rivalScore ? t("duel.beaten") : score === rivalScore ? t("duel.tie") : t("duel.lostScore", { n: rivalScore })}
                    </p>
                  )}
                  <div className="toolbar" style={{ marginTop: 8 }}>
                    <ShareButton
                      text={[
                        `LinkGuessr · ${t("tabs.count")} 🔗`,
                        `⭐ ${score} pts · ${totalCorrect}/${totalAnswered} ${t("share.exact")} · ${GAME_DURATION} s`,
                      ].join("\n")}
                      url={duelUrl({ jeu: "nombre", score })}
                      label={t("share.challenge")}
                      onShared={() => track(GAME, "share", { score })}
                    />
                    <button className="btn" onClick={startGame}>{t("guess.retry")}</button>
                  </div>
                  <Feedback game={GAME} />
                </div>
              )}
            </>
          )}
        </div>
      </section>
      {popup && (
        <div className="toast-bottom">
          <div className="success-box score-pop" style={{ maxWidth: 420 }}><strong>+{popup}</strong></div>
        </div>
      )}
    </>
  );
}
