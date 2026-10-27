import { lazy, Suspense, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useI18n } from "../i18n/I18nProvider";
import { trackUmami } from "../lib/tracking";
import PathView from "./PathView";
import PersonChip from "./PersonChip";
import PersonPicker from "./PersonPicker";
import { ShowMoreButton, useShowMore } from "./ShowMore";

// vis-network est lourd : chargé seulement quand un graphe est affiché.
const Graph = lazy(() => import("./Graph"));

const PALETTE = ["#ff6b6b", "#4dabf7", "#ffd43b", "#9b7cff", "#2ecc71", "#f77fbe"];

// Graphe vis-network de tous les plus courts chemins renvoyés.
function graphOf(result) {
  const nodes = new Map();
  const edges = new Map();
  result.paths.forEach((path, pi) => {
    path.forEach((qid, i) => {
      if (!nodes.has(qid)) nodes.set(qid, { id: qid, label: result.persons[qid].name, title: result.persons[qid].description || "" });
      const next = path[i + 1];
      if (!next) return;
      const key = [qid, next].sort().join("-");
      const edge = edges.get(key);
      if (edge) edge.width = Math.min(8, edge.width + 1);
      else edges.set(key, { from: qid, to: next, color: PALETTE[pi % PALETTE.length], width: 2 });
    });
  });
  return { nodes: [...nodes.values()], edges: [...edges.values()] };
}

export default function Game() {
  const { t } = useI18n();
  const [p1, setP1] = useState(null);
  const [p2, setP2] = useState(null);
  const [mode, setMode] = useState("all");
  const [result, setResult] = useState(null);
  const [shown, setShown] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [popularPairs, setPopularPairs] = useState([]);
  const [ppPeriod, setPpPeriod] = useState("7");
  const shownPairs = useShowMore(popularPairs, ppPeriod);

  // Depuis une fiche personne : /explorer?from=Q42 pré-remplit la première personne.
  const [params] = useSearchParams();
  const from = params.get("from");
  useEffect(() => {
    if (from) api.person(from).then((d) => setP1(d.person)).catch(() => {});
  }, [from]);

  useEffect(() => {
    api.popularPairs(ppPeriod).then(setPopularPairs).catch(() => setPopularPairs([]));
  }, [ppPeriod, result]);

  const explore = async (a = p1, b = p2) => {
    if (!a || !b) return;
    if (a.qid === b.qid) { setError(t("game.errorSame")); return; }
    setLoading(true);
    setError(null);
    try {
      const data = await api.path(a.qid, b.qid, { mode, limit: 6, track: true });
      setResult(data);
      setShown(0);
      api.logEvent("explore", { from: a.qid, to: b.qid, length: data.length, n_paths: data.n_paths, mode });
      // Pas de partie à finir : Explorer se mesure en recherches par visite (docs/tracking.md).
      trackUmami("explore", "exploration_recherche", { resultat: data.length != null ? "chemin" : "aucun" });
    } catch (e) {
      setError(e.message || t("game.errorUnknown"));
    } finally {
      setLoading(false);
    }
  };

  const randomPair = async () => {
    setLoading(true);
    try {
      const pair = await api.randomPair({ difficulty: "facile" });
      setP1(pair.from);
      setP2(pair.to);
      await explore(pair.from, pair.to);
    } catch (e) {
      setError(e.message || t("game.errorUnknown"));
    } finally {
      setLoading(false);
    }
  };

  const tryPair = async (r) => {
    const a = { qid: r.a_qid, name: r.a_name, image: r.a_image };
    const b = { qid: r.b_qid, name: r.b_name, image: r.b_image };
    setP1(a);
    setP2(b);
    await explore(a, b);
  };

  const graph = result?.paths?.length > 1 ? graphOf(result) : null;

  return (
    <>
      <section className="panel fade-in">
        <div className="panel-header">
          <span className="panel-title">{t("game.titlePath")}</span>
        </div>
        <div className="panel-body">
          <form className="form" style={{ gap: 16 }} onSubmit={(e) => { e.preventDefault(); explore(); }}>
            <div className="row">
              <PersonPicker id="pick-1" label={t("game.person1")} value={p1} onChange={setP1} />
              <PersonPicker id="pick-2" label={t("game.person2")} value={p2} onChange={setP2} />
            </div>
            <div className="toolbar">
              <button type="submit" className="btn btn-primary" disabled={!p1 || !p2 || loading}>
                {loading ? t("game.calculating") : t("game.check")}
              </button>
              <button type="button" className="btn" disabled={loading} onClick={randomPair}>{t("game.random")}</button>
              <select value={mode} onChange={(e) => setMode(e.target.value)} aria-label={t("game.modeLabel")}>
                <option value="all">{t("game.modeAll")}</option>
                <option value="strong">{t("game.modeStrong")}</option>
                <option value="wikidata">{t("game.modeWikidata")}</option>
              </select>
            </div>
          </form>

          {error && <div className="error-box" style={{ marginTop: 12 }}><p style={{ margin: 0 }}>{error}</p></div>}

          {result && result.length === null && (
            <p className="muted" style={{ marginTop: 12 }}>{t("game.noPath")}</p>
          )}

          {result && result.length !== null && (
            <div className="panel result-box" style={{ marginTop: 12 }}>
              <p className="kpi">{t("game.minRelations")}</p>
              <p style={{ fontSize: 28, margin: 0, fontWeight: 700 }}>{result.length}</p>
              <p className="muted" style={{ marginTop: 4 }}>
                {result.n_paths.toLocaleString()} {t("game.pathsCount")}
              </p>
              {result.paths.length > 1 && (
                <div className="toolbar" style={{ marginTop: 8 }}>
                  {result.paths.map((_, i) => (
                    <button key={i} className={`btn ${i === shown ? "btn-primary" : ""}`} onClick={() => setShown(i)}>
                      {t("game.pathN", { n: i + 1 })}
                    </button>
                  ))}
                </div>
              )}
              <PathView path={result.paths[shown]} persons={result.persons} hops={result.hops} />
              {graph && (
                <div style={{ marginTop: 12 }}>
                  <Suspense fallback={<p className="muted">…</p>}>
                    <Graph nodesData={graph.nodes} edgesData={graph.edges} height="360px" title={t("game.graphTitle")} />
                  </Suspense>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {popularPairs.length > 0 && (
        <section className="panel fade-in" style={{ marginTop: 12 }}>
          <div className="panel-header">
            <span className="panel-title">{t("game.popularPairs")}</span>
            <select value={ppPeriod} onChange={(e) => setPpPeriod(e.target.value)} aria-label={t("game.popularPeriod")}>
              <option value="7">{t("period.7")}</option>
              <option value="30">{t("period.30")}</option>
              <option value="all">{t("period.all")}</option>
            </select>
          </div>
          <div className="panel-body">
            <table className="table pairs-table">
              <tbody>
                {shownPairs.visible.map((r, i) => (
                  <tr key={`${r.a_qid}-${r.b_qid}`}>
                    <td style={{ width: 32 }}>{i + 1}</td>
                    <td><PersonChip person={{ qid: r.a_qid, name: r.a_name, image: r.a_image }} size={28} /></td>
                    <td><PersonChip person={{ qid: r.b_qid, name: r.b_name, image: r.b_image }} size={28} /></td>
                    <td style={{ textAlign: "right" }}><strong>{r.count}</strong></td>
                    <td style={{ textAlign: "right" }}>
                      <button className="btn" onClick={() => tryPair(r)} disabled={loading}>{t("game.try")}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ShowMoreButton list={shownPairs} />
          </div>
        </section>
      )}
    </>
  );
}
