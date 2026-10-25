import { useCallback, useEffect, useState } from "react";
import { api, lifespan } from "../api";
import { useI18n } from "../i18n/I18nProvider";
import DifficultyPicker from "./DifficultyPicker";
import PathView from "./PathView";
import PersonChip from "./PersonChip";
import PersonPicker from "./PersonPicker";

const GAME = "guess_who";
const MAX_TRIES = 4; // après 4 erreurs, la réponse est révélée

export default function GuessWhoPath() {
  const { t } = useI18n();
  const [difficulty, setDifficulty] = useState("facile");
  const [domain, setDomain] = useState("");
  const [domains, setDomains] = useState([]);
  const [challenge, setChallenge] = useState(null);
  const [guess, setGuess] = useState(null);
  const [tries, setTries] = useState(0);
  const [found, setFound] = useState(false);
  const [lastWrong, setLastWrong] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [topList, setTopList] = useState([]);

  useEffect(() => {
    api.domains().then(setDomains).catch(() => {});
    api.top("degree", { limit: 10 }).then(setTopList).catch(() => {});
  }, []);

  const fetchChallenge = useCallback(async () => {
    setLoading(true);
    setError(null);
    setGuess(null);
    setTries(0);
    setFound(false);
    setLastWrong(null);
    try {
      setChallenge(await api.randomPath({ difficulty, domain }));
    } catch (e) {
      setError(e.message || t("guess.errorLoadPeople"));
    } finally {
      setLoading(false);
    }
  }, [difficulty, domain, t]);

  useEffect(() => { fetchChallenge(); }, [fetchChallenge]);

  const validate = () => {
    if (!guess || !challenge || found) return;
    const ok = guess.qid === challenge.answer.qid;
    const newTries = tries + (ok ? 0 : 1);
    setTries(newTries);
    if (ok) setFound(true);
    else setLastWrong(guess);
    setGuess(null);
    if (ok || newTries >= MAX_TRIES) {
      api.logEvent(GAME, {
        answer: challenge.answer.qid, path: challenge.path, tries: newTries, found: ok, difficulty, domain: domain || null,
      });
    }
  };

  const revealed = found || tries >= MAX_TRIES;
  const hints = challenge?.hints;
  const persons = challenge && (revealed ? { ...challenge.persons, [challenge.answer.qid]: challenge.answer } : challenge.persons);

  return (
    <>
      <section className="panel fade-in">
        <div className="panel-header">
          <span className="panel-title">{t("who.title")}</span>
          <div className="toolbar">
            <DifficultyPicker value={difficulty} onChange={setDifficulty} />
            <select value={domain} onChange={(e) => setDomain(e.target.value)} aria-label={t("who.domain")}>
              <option value="">{t("who.allDomains")}</option>
              {domains.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            <button className="btn" onClick={fetchChallenge} disabled={loading}>{t("guess.newChallenge")}</button>
          </div>
        </div>
        <div className="panel-body">
          {error && <div className="error-box"><p style={{ margin: 0 }}>{error}</p></div>}
          {!challenge ? (
            <p className="muted" style={{ margin: 0 }}>{t("guess.loadingPeople")}</p>
          ) : (
            <>
              <PathView path={challenge.path} persons={persons} hops={challenge.hops}
                hiddenIndex={revealed ? null : challenge.masked_index} />

              {!revealed && (
                <form className="row" style={{ alignItems: "end" }} onSubmit={(e) => { e.preventDefault(); validate(); }}>
                  <PersonPicker id="who-guess" label={t("who.question")} value={guess} onChange={setGuess} />
                  <div><button type="submit" className="btn btn-primary" disabled={!guess}>{t("guess.verify")}</button></div>
                </form>
              )}

              {lastWrong && !revealed && (
                <p style={{ color: "var(--danger)", fontWeight: 600 }}>{t("who.notThisOne", { name: lastWrong.name })}</p>
              )}

              {!revealed && tries > 0 && (
                <ul className="hints">
                  {tries >= 1 && hints.domain && <li>{t("who.hintDomain")} <strong>{hints.domain}</strong></li>}
                  {tries >= 2 && hints.birth_year && <li>{t("who.hintLife")} <strong>{lifespan(hints)}</strong></li>}
                  {tries >= 3 && <li>{t("who.hintInitials")} <strong>{hints.initials}</strong> ({hints.name_length} {t("who.chars")})</li>}
                </ul>
              )}

              {revealed && (
                <div className={found ? "success-box" : "panel result-box"} style={{ marginTop: 12 }}>
                  <p style={{ margin: 0, fontWeight: 600 }}>{found ? t("guess.good") : t("who.answerWas")}</p>
                  <div style={{ marginTop: 8 }}><PersonChip person={challenge.answer} showDescription size={56} /></div>
                  <button className="btn" style={{ marginTop: 8 }} onClick={fetchChallenge}>{t("guess.next")}</button>
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
