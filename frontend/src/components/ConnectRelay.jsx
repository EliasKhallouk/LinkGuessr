import { useEffect, useState } from "react";
import { api } from "../api";
import { useI18n } from "../i18n/I18nProvider";
import DifficultyPicker from "./DifficultyPicker";
import PathView from "./PathView";
import { duelUrl, relayGrid } from "../lib/share";
import { load, save } from "../lib/storage";
import PersonChip from "./PersonChip";
import ShareButton from "./ShareButton";
import { ShowMoreButton, useShowMore } from "./ShowMore";
import { newRound, track } from "../lib/tracking";
import Feedback from "./Feedback";
import { confetti } from "../lib/confetti";

const GAME = "relay";
const HINT_AFTER = 2; // aide quand le joueur a fait 2 pas de plus que le plus court chemin
// Longueur du plus court chemin selon le niveau : en facile, une seule personne entre les deux.
const LENGTHS = { facile: [2, 2], moyen: [2, 3], difficile: [3, 4], extreme: [4, 5], humain: [5, 6] };

// `fixedPair` ({ from, to }) : paire imposée par un duel ; `rivalSteps` : score à battre.
export default function ConnectRelay({ fixedPair = null, rivalSteps = null }) {
  const { t } = useI18n();
  const [difficulty, setDifficulty] = useState("facile");
  const [target, setTarget] = useState(null);
  const [history, setHistory] = useState([]);   // personnes visitées, la première est le départ
  const [neighbors, setNeighbors] = useState([]);
  const [search, setSearch] = useState("");
  const [best, setBest] = useState(null);       // résultat /path depuis le départ
  const [hint, setHint] = useState(null);       // prochaine bonne personne
  const [hintsUsed, setHintsUsed] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const current = history[history.length - 1];
  const success = current && target && current.qid === target.qid;
  const steps = history.length - 1;

  const loadNeighbors = async (person) => {
    try {
      setNeighbors(await api.neighbors(person.qid, 500));
    } catch {
      setNeighbors([]);
      setError(t("relay.errorNeighbors"));
    }
  };

  const loadChallenge = async () => {
    newRound(GAME);
    setLoading(true);
    setError(null);
    setHint(null);
    setHintsUsed(0);
    setSearch("");
    try {
      const pair = fixedPair || await api.randomPair({ difficulty, min_length: LENGTHS[difficulty][0], max_length: LENGTHS[difficulty][1] });
      setTarget(pair.to);
      setHistory([pair.from]);
      setBest(null);
      await loadNeighbors(pair.from);
      api.path(pair.from.qid, pair.to.qid, { limit: 1 }).then(setBest).catch(() => {});
    } catch (e) {
      setError(e.message || t("relay.errorLoad"));
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadChallenge(); }, [difficulty]);

  const choose = async (person) => {
    track(GAME, "start", { difficulty, duel: Boolean(fixedPair) });
    const newHistory = [...history, person];
    setHistory(newHistory);
    setSearch("");
    setHint(null);
    if (person.qid === target.qid) {
      confetti();
      setNeighbors([]);
      const record = load("lg-relay-stats", { played: 0, optimal: 0 });
      save("lg-relay-stats", { played: record.played + 1,
        optimal: record.optimal + (best?.length === newHistory.length - 1 ? 1 : 0) });
      track(GAME, "finish", {
        from: newHistory[0].qid, to: target.qid, best: best?.length ?? null, steps: newHistory.length - 1,
        path: newHistory.map((p) => p.qid), hints: hintsUsed, difficulty, duel: Boolean(fixedPair),
      });
      return;
    }
    setLoading(true);
    await loadNeighbors(person);
    setLoading(false);
    // Trop de détours : on indique la prochaine personne d'un plus court chemin.
    if (best?.length && newHistory.length - 1 >= best.length + HINT_AFTER) {
      try {
        const local = await api.path(person.qid, target.qid, { limit: 1 });
        const nextQid = local.paths[0]?.[1];
        if (nextQid) {
          setHint(local.persons[nextQid]);
          setHintsUsed((n) => n + 1);
        }
      } catch { /* l'aide est facultative */ }
    }
  };

  const goBack = async () => {
    if (history.length < 2) return;
    const newHistory = history.slice(0, -1);
    setHistory(newHistory);
    setHint(null);
    await loadNeighbors(newHistory[newHistory.length - 1]);
  };

  const query = search.trim().toLowerCase();
  const matching = neighbors.filter((n) => !query || n.name.toLowerCase().includes(query));
  // La personne suggérée par l'indice passe en tête : elle reste visible malgré « Voir plus ».
  const visible = hint ? [...matching.filter((n) => n.qid === hint.qid), ...matching.filter((n) => n.qid !== hint.qid)] : matching;
  const shown = useShowMore(visible, `${current?.qid}|${query}`);

  return (
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">{t("relay.title")}</span>
        <div className="toolbar">
          <DifficultyPicker value={difficulty} onChange={setDifficulty} />
          <button className="btn" onClick={loadChallenge} disabled={loading}>{t("relay.new")}</button>
        </div>
      </div>
      <div className="panel-body">
        {error && <div className="error-box"><p style={{ margin: 0 }}>{error}</p></div>}
        {!target || !current ? (
          <p className="muted">{t("relay.loading")}</p>
        ) : (
          <>
            <div className="pair">
              <PersonChip person={history[0]} showDescription size={48} />
              <span className="pair-sep">→</span>
              <PersonChip person={target} showDescription size={48} />
            </div>
            <p className="muted" style={{ marginTop: 8 }}>
              {t("relay.stepsSoFar", { n: steps })}{best?.length ? ` · ${t("relay.bestIs", { n: best.length })}` : ""}
            </p>

            <div className="relay-history">
              {history.map((p, i) => (
                <span key={`${p.qid}-${i}`}>{i > 0 && " → "}<PersonChip person={p} size={24} /></span>
              ))}
            </div>

            {success ? (
              <div className="success-box" style={{ marginTop: 12 }}>
                <p style={{ margin: 0, fontWeight: 600 }}>
                  {t("relay.success", { n: steps })}
                  {best?.length === steps ? ` ${t("relay.perfect")}` : ""}
                </p>
                {best && best.length < steps && (
                  <>
                    <p className="muted" style={{ marginTop: 8 }}>{t("relay.bestPath")}</p>
                    <PathView path={best.paths[0]} persons={best.persons} hops={best.hops} />
                  </>
                )}
                {rivalSteps && (
                  <p style={{ marginTop: 8, fontWeight: 600 }}>
                    {steps < rivalSteps ? t("duel.beaten") : steps === rivalSteps ? t("duel.tie") : t("duel.lost", { n: rivalSteps })}
                  </p>
                )}
                <div className="toolbar" style={{ marginTop: 8 }}>
                  <ShareButton
                    text={[
                      `LinkGuessr · ${t("tabs.relay")} 🔗`,
                      `${history[0].name} → ${target.name}`,
                      `${relayGrid(steps, best?.length)} · ${t("share.steps", { n: steps })}${best?.length ? ` (${t("share.optimal", { n: best.length })})` : ""}`,
                    ].join("\n")}
                    url={duelUrl({ jeu: "relais", paire: `${history[0].qid}-${target.qid}`, score: steps })}
                    label={t("share.challenge")}
                    onShared={() => track(GAME, "share", { steps, best: best?.length ?? null })}
                  />
                  {!fixedPair && <button className="btn" onClick={loadChallenge}>{t("relay.new")}</button>}
                </div>
                <Feedback game={GAME} />
              </div>
            ) : (
              <>
                {hint && (
                  <div className="panel result-box" style={{ marginTop: 8 }}>
                    {t("relay.hintNextPrefix")} <PersonChip person={hint} size={24} />
                  </div>
                )}
                <div className="toolbar" style={{ marginTop: 12 }}>
                  <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
                    placeholder={t("relay.searchPlaceholder", { name: current.name, n: neighbors.length })} />
                  <button className="btn" onClick={goBack} disabled={history.length < 2 || loading}>{t("relay.back")}</button>
                </div>
                <ul className="neighbor-list">
                  {visible.length === 0 && <li className="muted">{loading ? t("relay.loading") : t("relay.noNeighbors")}</li>}
                  {shown.visible.map((n) => (
                    <li key={n.qid} className={hint?.qid === n.qid ? "is-hint" : ""}>
                      <PersonChip person={n} showDescription size={32} />
                      <span className="muted">{n.degree?.toLocaleString()} {t("who.links")}</span>
                      <button className="btn" onClick={() => choose(n)} disabled={loading}>{t("relay.choose")}</button>
                    </li>
                  ))}
                </ul>
                <ShowMoreButton list={shown} />
              </>
            )}
          </>
        )}
      </div>
    </section>
  );
}
