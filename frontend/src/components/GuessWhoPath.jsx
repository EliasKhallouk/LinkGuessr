import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, lifespan } from "../api";
import Avatar from "./Avatar";
import { useI18n } from "../i18n/I18nProvider";
import { capitalize } from "../lib/format";
import DifficultyPicker from "./DifficultyPicker";
import PathView, { Snippet } from "./PathView";
import PersonChip from "./PersonChip";
import PersonPicker from "./PersonPicker";
import { newRound, track, trackUmami } from "../lib/tracking";
import Feedback from "./Feedback";
import TriesTiles from "./TriesTiles";
import { confetti } from "../lib/confetti";
import { duelShare, newSeed, SITE_URL } from "../lib/share";
import ShareButton from "./ShareButton";

const GAME = "guess_who";
// Époques : aujourd'hui (vivants nés après 1970, classés par notoriété actuelle), culture générale, histoire.
export const ERAS = ["aujourdhui", "tous", "histoire"];

// Aides selon le niveau : chaque indice apparaît après ce nombre d'erreurs (0 : dès le départ, absent : jamais).
// clues : phrases à trou qui relient la personne cachée à ses voisins.
// L'API choisit aussi des énigmes plus simples en facile (liens forts, personne très connue) ; facile et moyen : choix parmi 4.
const HELP = {
  facile: { tries: 2, clues: 0, domain: 0, life: 0 },  // 2 essais pour 4 propositions : sinon on gagne presque à coup sûr
  moyen: { tries: 2 },  // choix parmi 4, sans aucun indice
  difficile: { tries: 4, domain: 1, clues: 2, initials: 3 },
  extreme: { tries: 4, domain: 1, life: 2, initials: 3 },
  humain: { tries: 3 },
};

function Choice({ person, disabled, onPick }) {
  return (
    <button type="button" className="who-choice" disabled={disabled} onClick={() => onPick(person)}
      aria-label={person.description ? `${person.name}, ${person.description}` : person.name}>
      <Avatar person={person} size={44} />
      <span className="person-text">
        <strong>{person.name}</strong>
        {person.description && <span className="person-desc">{person.description}</span>}
      </span>
    </button>
  );
}

// Mode partie : 10 énigmes au même niveau. Points par énigme trouvée : plus le niveau est dur, plus elle
// rapporte, et moins on a eu besoin d'essais, mieux c'est (la moitié au 2e essai, un quart au 3e, un dixième
// au 4e). Pas de chrono : on prend le temps de réfléchir.
export const RUN_LENGTH = 10;
export const LEVEL_POINTS = { facile: 100, moyen: 200, difficile: 400, extreme: 600, humain: 1000 };
const TRY_SHARE = [1, 0.5, 0.25, 0.1];
export const pointsFor = (level, found, attempts) => (found ? Math.round(LEVEL_POINTS[level] * TRY_SHARE[attempts - 1]) : 0);
// Une case par énigme : 🟩 du premier coup, 🟨 trouvée ensuite, 🟥 pas trouvée.
const runGrid = (results) => results.map((r) => (!r.found ? "🟥" : r.attempts === 1 ? "🟩" : "🟨")).join("");

// Résultat partageable sans rien dévoiler : 🟥 erreur, 🟩 trouvé, ⬛ essai non utilisé.
function grid(wrongCount, solved, maxTries) {
  const cells = [...Array(wrongCount).fill("🟥"), ...(solved ? ["🟩"] : [])];
  return cells.concat(Array(Math.max(0, maxTries - cells.length)).fill("⬛")).join("");
}

// `puzzle` ({ t, niveau, epoque } ou, anciens liens, { chemin, cache, niveau, epoque }) : énigme partagée
// par un ami (page /defi) ;
// `rival` ({ found, tries }) : son résultat, comparé au nôtre à la fin.
// `series` ({ seed, niveau, epoque, domaine, score }) : partie de 10 énigmes d'un ami, rejouée à l'identique.
export default function GuessWhoPath({ puzzle = null, rival = null, series = null }) {
  const { t } = useI18n();
  const [difficulty, setDifficulty] = useState(puzzle?.niveau || series?.niveau || "facile");
  const [era, setEra] = useState(puzzle?.epoque || series?.epoque || "aujourdhui");
  const [domain, setDomain] = useState(series?.domaine || "");
  const [domains, setDomains] = useState([]);
  const [challenge, setChallenge] = useState(null);
  const [guess, setGuess] = useState(null);
  const [tries, setTries] = useState(0);
  const [found, setFound] = useState(null);       // la personne trouvée (la réponse attendue ou une autre bonne)
  const [wrong, setWrong] = useState([]);         // réponses fausses déjà données
  const [checking, setChecking] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [topList, setTopList] = useState([]);
  const [shake, setShake] = useState(false);
  const [run, setRun] = useState(series && { level: series.niveau, seed: series.seed, results: [] });
  // Mode partie : { level, seed, results: [{ found, attempts, points }] }. La graine et le rang de l'énigme
  // en cours sont aussi gardés ici, hors de l'état, pour que le chargement d'une énigme n'en dépende pas.
  const runRef = useRef(series && { seed: series.seed, index: 0 });
  useEffect(() => {
    if (series) trackUmami(GAME, "serie_debut", { niveau: series.niveau });
  }, [series]);

  // Énigme d'un ami : ni filtres ni classement, pour que la fin de partie reste visible.
  useEffect(() => {
    if (puzzle || series) return;
    api.domains().then(setDomains).catch(() => {});
    api.top("degree", { limit: 10 }).then(setTopList).catch(() => {});
  }, [puzzle]);

  const fetchChallenge = useCallback(async () => {
    newRound(GAME);
    setLoading(true);
    setError(null);
    setGuess(null);
    setTries(0);
    setFound(null);
    setWrong([]);
    try {
      setChallenge(await (puzzle ? api.replayHidden(puzzle) : api.randomPath({ difficulty, domain, epoque: era,
        ...(runRef.current && { seed: runRef.current.seed, index: runRef.current.index }) })));
    } catch (e) {
      setError(e.message || t("guess.errorLoadPeople"));
    } finally {
      setLoading(false);
    }
  }, [difficulty, domain, era, puzzle, t]);

  useEffect(() => { fetchChallenge(); }, [fetchChallenge]);

  const help = HELP[difficulty];
  const maxTries = help.tries;

  // Toute personne liée aux deux voisins de la personne cachée est une bonne réponse
  // (les mauvaises propositions du choix multiple ne le sont jamais : l'API les écarte).
  const isRight = async (person) => {
    if (person.qid === challenge.answer.qid) return true;
    if (challenge.choices || challenge.path.includes(person.qid)) return false;
    const { path, masked_index: m } = challenge;
    try {
      return (await api.checkHidden(path[m - 1], path[m + 1], person.qid)).ok;
    } catch {
      return false;
    }
  };

  const answer = async (person) => {
    if (!person || !challenge || found || checking) return;
    track(GAME, "start", { difficulty });
    setChecking(true);
    const ok = await isRight(person);
    setChecking(false);
    const newTries = tries + (ok ? 0 : 1);
    setTries(newTries);
    setGuess(null);
    if (ok) {
      setFound(person);
      confetti();
    } else {
      setWrong((w) => [...w, person]);
      setShake(true);
    }
    if ((ok || newTries >= maxTries) && run) {
      const result = { found: ok, attempts: wrong.length + 1, points: pointsFor(difficulty, ok, wrong.length + 1) };
      const results = [...run.results, result];
      runRef.current = { ...runRef.current, index: results.length };  // énigme suivante de la série
      setRun({ ...run, results });
      if (results.length === RUN_LENGTH) {
        const score = results.reduce((s, r) => s + r.points, 0);
        const foundCount = results.filter((r) => r.found).length;
        api.logEvent(GAME, { event: "run_finish", difficulty, era, score, found: foundCount });
        trackUmami(GAME, "serie_fin", { niveau: difficulty, score, trouvees: foundCount });
      }
    }
    if (ok || newTries >= maxTries) {
      track(GAME, "finish", {
        answer: challenge.answer.qid, guessed: ok ? person.qid : null, path: challenge.path, tries: newTries,
        found: ok, difficulty, era, domain: domain || null, duel: Boolean(puzzle),
      });
    }
  };

  const revealed = Boolean(found) || tries >= maxTries;
  const shown = (hint) => help[hint] != null && tries >= help[hint];
  const hints = challenge?.hints;
  const persons = challenge && (revealed ? { ...challenge.persons, [challenge.answer.qid]: challenge.answer } : challenge.persons);
  // Une fois la réponse donnée, on montre aussi pourquoi la personne cachée est reliée à ses voisins.
  const hops = challenge && (revealed ? { ...challenge.hops, ...challenge.answer_hops } : challenge.hops);
  const clues = (challenge?.clues || []).filter((c) => c.relation || c.snippet);
  const lastWrong = wrong[wrong.length - 1];
  const attempts = wrong.length + (found ? 1 : 0);

  // Partage façon Wordle : le chemin avec ❓ à la place de la personne cachée, les cases, et un lien qui ouvre
  // la même énigme chez l'ami. Le ton change selon qu'on a trouvé ou non.
  const shareText = () => {
    const names = challenge.path.map((q, i) => (i === challenge.masked_index ? "❓" : challenge.persons[q].name));
    return [
      `LinkGuessr · ${t("who.title")} ${t(`who.eras.${era}`)} · ${t(`difficulty.${difficulty}`)}`,
      names.join(" → "),
      grid(wrong.length, Boolean(found), maxTries),
      found ? t("share.whoFound", { n: attempts }) : t("share.whoLost"),
    ].join("\n");
  };
  // Lien de duel chiffré par l'API (rien de l'énigme en clair). Demandé dès la fin de partie : le menu de
  // partage du téléphone doit s'ouvrir directement au clic. Sans jeton (API indisponible) : lien vers le jeu.
  const [token, setToken] = useState(null);
  useEffect(() => {
    setToken(null);
    if (!revealed || !challenge || run) return;  // mode partie : on partage la partie, pas l'énigme
    api.duelToken({ chemin: challenge.path.join("-"), cache: challenge.masked_index, niveau: difficulty, epoque: era,
      essais: attempts, trouve: Boolean(found) }).then((r) => setToken(r.t)).catch(() => {});
  }, [revealed, challenge, difficulty, era, attempts, found, run]);
  const shareLink = () => (token ? duelShare({ jeu: "qui", t: token })
    : { url: `${SITE_URL}/qui-est-cache`, utm: { source: "partage", campaign: "qui-est-cache" } });
  const startRun = () => {
    const seed = newSeed();
    runRef.current = { seed, index: 0 };
    setRun({ level: difficulty, seed, results: [] });
    trackUmami(GAME, "serie_debut", { niveau: difficulty });
    fetchChallenge();
  };
  const quitRun = () => {
    runRef.current = null;
    setRun(null);
    fetchChallenge();
  };
  const runScore = run ? run.results.reduce((s, r) => s + r.points, 0) : 0;
  const runDone = run?.results.length === RUN_LENGTH;
  const lastPoints = run && revealed ? run.results[run.results.length - 1]?.points : null;
  const runShareText = () => [
    `LinkGuessr · ${t("who.title")} · ${t(`difficulty.${run.level}`)}`,
    runGrid(run.results),
    `⭐ ${runScore.toLocaleString("fr-FR")} pts · ${t("who.run.found", { n: run.results.filter((r) => r.found).length, total: RUN_LENGTH })}`,
    t("who.run.beatMe"),
  ].join("\n");

  // Comparaison avec l'ami : trouver bat ne pas trouver, puis moins d'essais.
  const versus = rival && revealed && (() => {
    const mine = found ? attempts : Infinity;
    const theirs = rival.found ? rival.tries : Infinity;
    return mine < theirs ? t("duel.beaten") : mine === theirs ? t("duel.tie") : t("duel.whoWorse");
  })();

  return (
    <>
      <section className="panel fade-in">
        <div className="panel-header">
          <span className="panel-title">{t("who.title")}</span>
          {run && !puzzle && (
            <div className="toolbar">
              <span className="kpi">{t("who.run.progress", { n: Math.min(run.results.length + (revealed ? 0 : 1), RUN_LENGTH), total: RUN_LENGTH })}</span>
              <span className="kpi">⭐ <strong>{runScore.toLocaleString("fr-FR")}</strong></span>
              {!runDone && <button className="btn" onClick={quitRun}>{t("who.run.quit")}</button>}
            </div>
          )}
          {!run && !puzzle && (
            <div className="toolbar">
              <select value={era} onChange={(e) => setEra(e.target.value)} aria-label={t("who.era")}>
                {ERAS.map((e) => <option key={e} value={e}>{t(`who.eras.${e}`)}</option>)}
              </select>
              {/* « Tu es humain ? » passe en culture générale : en « Aujourd'hui », ses longs chemins ne sont
                  faits que de footballeurs inconnus. On peut toujours rechoisir l'époque ensuite. */}
              <DifficultyPicker value={difficulty} onChange={(level) => {
                setDifficulty(level);
                if (level === "humain") setEra("tous");
              }} />
              <select value={domain} onChange={(e) => setDomain(e.target.value)} aria-label={t("who.domain")}>
                <option value="">{t("who.allDomains")}</option>
                {domains.map((d) => <option key={d} value={d}>{capitalize(d)}</option>)}
              </select>
              <button className="btn" onClick={fetchChallenge} disabled={loading}>{t("guess.newChallenge")}</button>
              <button className="btn btn-primary" onClick={startRun} disabled={loading}>{t("who.run.start", { n: RUN_LENGTH })}</button>
            </div>
          )}
        </div>
        <div className="panel-body">
          <p className="muted who-level-help">{t(`who.help.${difficulty}`)}</p>
          {run && run.results.length === 0 && !revealed && (
            <p className="muted who-level-help">{t("who.run.rules", { n: LEVEL_POINTS[run.level] })}</p>
          )}
          {error && <div className="error-box"><p style={{ margin: 0 }}>{error}</p></div>}
          {!challenge ? (
            <p className="muted" style={{ margin: 0 }}>{t("guess.loadingPeople")}</p>
          ) : (
            <>
              <div className="tries-row" style={{ marginBottom: 8 }}>
                <TriesTiles total={maxTries} wrong={tries} solved={Boolean(found)}
                  label={found ? t("guess.good") : t("daily.triesLeft", { n: maxTries - tries })} />
                {!revealed && <span className="muted tries-left" aria-hidden="true">{t("daily.triesLeft", { n: maxTries - tries })}</span>}
              </div>
              <PathView path={challenge.path} persons={persons} hops={hops}
                hiddenIndex={revealed ? null : challenge.masked_index} />

              {!revealed && shown("clues") && clues.length > 0 && (
                <div className="who-clues">
                  <p className="muted" style={{ margin: "0 0 4px" }}>{t("who.clues")}</p>
                  <ul>
                    {clues.map((c) => (
                      <li key={c.with}>
                        {c.relation && <strong className="hop-relation">{c.relation}</strong>}
                        {c.snippet && <Snippet text={c.snippet} />}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {!revealed && (shown("domain") || shown("life") || shown("initials")) && (
                <ul className="hints">
                  {shown("domain") && hints.domain && <li>{t("who.hintDomain")} <strong>{capitalize(hints.domain)}</strong></li>}
                  {shown("life") && hints.birth_year && <li>{t("who.hintLife")} <strong>{lifespan(hints)}</strong></li>}
                  {shown("initials") && <li>{t("who.hintInitials")} <strong>{hints.initials}</strong> ({hints.name_length} {t("who.chars")})</li>}
                </ul>
              )}

              {!revealed && challenge.choices && (
                <div className={`who-choices ${shake ? "shake" : ""}`} onAnimationEnd={() => setShake(false)}
                  role="group" aria-label={t("who.question")}>
                  {challenge.choices.map((p) => (
                    <Choice key={p.qid} person={p} onPick={answer}
                      disabled={checking || wrong.some((w) => w.qid === p.qid)} />
                  ))}
                </div>
              )}

              {!revealed && !challenge.choices && (
                <form className={`row ${shake ? "shake" : ""}`} style={{ alignItems: "end" }} onAnimationEnd={(e) => { if (e.target === e.currentTarget) setShake(false); }}
                  onSubmit={(e) => { e.preventDefault(); answer(guess); }}>
                  <PersonPicker id="who-guess" label={t("who.question")} value={guess} onChange={setGuess} />
                  <div><button type="submit" className="btn btn-primary" disabled={!guess || checking}>{t("guess.verify")}</button></div>
                </form>
              )}

              {lastWrong && !revealed && (
                <p style={{ color: "var(--danger)", fontWeight: 600 }}>{t("who.notThisOne", { name: lastWrong.name })}</p>
              )}

              {revealed && (
                <div className={found ? "success-box" : "panel result-box"} style={{ marginTop: 12 }}>
                  <p style={{ margin: 0, fontWeight: 600 }}>{found ? t("guess.good") : t("who.answerWas")}</p>
                  {found && found.qid !== challenge.answer.qid && (
                    <p style={{ margin: "6px 0 0" }}>{t("who.alsoRight", { guess: found.name, name: challenge.answer.name })}</p>
                  )}
                  <div style={{ marginTop: 8 }}><PersonChip person={challenge.answer} showDescription size={56} /></div>
                  {versus && <p style={{ margin: "8px 0 0", fontWeight: 600 }}>{versus}</p>}
                  {lastPoints != null && <p style={{ margin: "8px 0 0", fontWeight: 700 }}>{t("who.run.points", { n: lastPoints })}</p>}
                  {puzzle && (
                    <div className="more-games">
                      <span>{t("home.moreGames")}</span>
                      <Link className="btn btn-primary" to="/">{t("home.discover")}</Link>
                    </div>
                  )}
                  {run && !runDone && (
                    <div className="toolbar" style={{ marginTop: 8 }}>
                      <button className="btn btn-primary" onClick={fetchChallenge}>
                        {t("who.run.next", { n: run.results.length + 1, total: RUN_LENGTH })}
                      </button>
                    </div>
                  )}
                  {runDone && (
                    <div className="panel result-box" style={{ marginTop: 12 }}>
                      <p style={{ margin: 0, fontWeight: 700 }}>{t("who.run.doneTitle")}</p>
                      <p style={{ fontSize: 28, margin: "6px 0", letterSpacing: 2 }}>{runGrid(run.results)}</p>
                      <p className="kpi" style={{ margin: 0 }}>
                        ⭐ <strong>{runScore.toLocaleString("fr-FR")}</strong> pts ·{" "}
                        {t("who.run.found", { n: run.results.filter((r) => r.found).length, total: RUN_LENGTH })}
                      </p>
                      {series?.score != null && run.seed === series.seed && (
                        <p style={{ margin: "8px 0 0", fontWeight: 600 }}>
                          {runScore > series.score ? t("duel.beaten") : runScore === series.score ? t("duel.tie")
                            : t("duel.lostScore", { n: series.score.toLocaleString("fr-FR") })}
                        </p>
                      )}
                      <div className="toolbar" style={{ marginTop: 8 }}>
                        {/* Lien de duel : la graine fait rejouer les 10 mêmes énigmes, dans le même ordre. */}
                        <ShareButton text={runShareText()} label={t("share.challenge")} {...duelShare({
                          jeu: "serie", niveau: run.level, epoque: era, ...(domain && { domaine: domain }),
                          graine: run.seed.toString(36), score: runScore })} />
                        <button className="btn btn-primary" onClick={startRun}>{t("who.run.again")}</button>
                        <button className="btn" onClick={quitRun}>{t("who.run.free")}</button>
                      </div>
                      <Feedback game={GAME} />
                    </div>
                  )}
                  {!run && (
                    <>
                      <div className="toolbar" style={{ marginTop: 8 }}>
                        <ShareButton text={shareText()} {...shareLink()} label={t("share.challenge")}
                          onShared={() => track(GAME, "share", { found: Boolean(found), tries: attempts, difficulty })} />
                        {!puzzle && <button className="btn" onClick={fetchChallenge}>{t("guess.next")}</button>}
                      </div>
                      <Feedback game={GAME} />
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {topList.length > 0 && (
        <section className="panel fade-in" style={{ marginTop: 12 }}>
          <div className="panel-header"><span className="panel-title">{t("who.topTitle")}</span></div>
          <div className="panel-body">
            <table className="table">
              <tbody>
                {topList.map((p, i) => (
                  <tr key={p.qid}>
                    <td style={{ width: 32 }}>{i + 1}</td>
                    <td><PersonChip person={p} size={28} /></td>
                    <td style={{ textAlign: "right" }}><strong>{p.degree?.toLocaleString()}</strong> {t("who.links")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  );
}
