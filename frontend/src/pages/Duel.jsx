import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import ConnectRelay from "../components/ConnectRelay";
import GuessRelations from "../components/GuessRelations";
import GuessWhoPath, { ERAS } from "../components/GuessWhoPath";
import { LEVELS } from "../components/DifficultyPicker";
import { useI18n } from "../i18n/I18nProvider";
import { usePageMeta } from "../lib/meta";
import { parseSeed } from "../lib/share";
import { track } from "../lib/tracking";

// Page d'arrivée d'un lien de duel : /defi?jeu=relais&paire=Q1-Q2&score=3,
// /defi?jeu=nombre&score=340&niveau=moyen&graine=k3x9za (mêmes paires que l'ami, dans le même ordre),
// /defi?jeu=serie&score=2750&niveau=moyen&epoque=tous&graine=k3x9za (les 10 mêmes énigmes « Qui est caché ? »)
// ou /defi?jeu=qui&t=<jeton> (même énigme « Qui est caché ? », chiffrée par l'API : le lien ne dit rien
// de la réponse). Anciens liens en clair, encore acceptés :
// /defi?jeu=cache&chemin=Q1-Q2-Q3&cache=1&niveau=facile&epoque=aujourdhui&essais=2&trouve=1.
const GAMES = { relais: "relay", nombre: "guess_count", qui: "guess_who", cache: "guess_who", serie: "guess_who" };
const HIDDEN = ["qui", "cache"];
export default function Duel() {
  const { t } = useI18n();
  usePageMeta(t("meta.duel.title"), t("meta.duel.description"));
  const [params] = useSearchParams();
  const game = params.get("jeu");
  const score = Number(params.get("score")) || null;
  const pairParam = params.get("paire") || "";
  const [pair, setPair] = useState(null);
  const [error, setError] = useState(false);
  // Énigme partagée : objet stable (sinon le jeu la recharge à chaque rendu).
  const chemin = params.get("chemin") || "";
  const cache = Number(params.get("cache"));
  const niveau = LEVELS.includes(params.get("niveau")) ? params.get("niveau") : "moyen";
  const epoque = ERAS.includes(params.get("epoque")) ? params.get("epoque") : "tous";
  const puzzle = useMemo(() => ({ chemin, cache, niveau, epoque }), [chemin, cache, niveau, epoque]);
  const tries = Number(params.get("essais")) || 0;
  const found = params.get("trouve") === "1";
  // Combien : graine en base 36 (anciens liens sans graine : paires au hasard).
  const graine = parseSeed(params.get("graine"));
  const plainRival = useMemo(() => ({ found, tries }), [found, tries]);
  const domaine = (params.get("domaine") || "").slice(0, 60);
  const series = useMemo(() => (graine == null ? null : { seed: graine, niveau, epoque, domaine, score }),
    [graine, niveau, epoque, domaine, score]);
  const validPuzzle = /^Q\d+(-Q\d+){2,7}$/.test(chemin) && cache >= 1 && cache <= chemin.split("-").length - 2;

  // Lien chiffré : niveau, époque et résultat de l'ami lus par l'API (sans la réponse).
  const token = params.get("t") || "";
  const [preview, setPreview] = useState(null);
  const [invalid, setInvalid] = useState(null);
  useEffect(() => {
    if (game !== "qui") return;
    api.duelPreview(token).then(setPreview)
      .catch((e) => setInvalid(e.status === 503 ? e.message : t("duel.invalid")));
  }, [game, token, t]);
  const tokenPuzzle = useMemo(() => preview && { t: token, niveau: preview.niveau, epoque: preview.epoque },
    [preview, token]);
  const rival = game === "qui" ? preview?.rival : plainRival;

  // Ouverture d'un lien de duel : mesure de la viralité.
  useEffect(() => {
    if (GAMES[game]) track(GAMES[game], "duel_open", { score });
  }, [game, score]);

  useEffect(() => {
    if (game !== "relais") return;
    const [a, b] = pairParam.split("-");
    if (!/^Q\d+$/.test(a || "") || !/^Q\d+$/.test(b || "")) {
      setError(true);
      return;
    }
    Promise.all([api.personCard(a), api.personCard(b)])
      .then(([ca, cb]) => setPair({ from: ca.person, to: cb.person }))
      .catch(() => setError(true));
  }, [game, pairParam]);

  if (!GAMES[game] || error || (game === "cache" && !validPuzzle) || (game === "serie" && !series)) return <Navigate to="/" replace />;
  if (invalid) {
    return (
      <main className="page fade-in">
        <section className="panel">
          <div className="panel-body">
            <div className="error-box"><p style={{ margin: 0 }}>{invalid}</p></div>
            <div className="toolbar" style={{ marginTop: 12 }}>
              <Link className="btn btn-primary" to="/qui-est-cache">{t("duel.newGame")}</Link>
              <Link className="btn" to="/">{t("duel.otherGames")}</Link>
            </div>
          </div>
        </section>
      </main>
    );
  }
  return (
    <main className="page fade-in">
      <section className="panel duel-banner">
        <div className="panel-body duel-banner-body">
          <div>
            <p style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
              {game === "relais"
                ? (pair ? t("duel.relayIntro", { a: pair.from.name, b: pair.to.name, n: score }) : "…")
                : game === "serie" ? t("duel.serieIntro", { n: score ?? 0 })
                : HIDDEN.includes(game)
                  ? (!rival ? "…" : rival.found ? t("duel.whoFound", { n: rival.tries }) : t("duel.whoLost"))
                  : t("duel.countIntro", { n: score })}
            </p>
            <p className="muted" style={{ margin: "4px 0 0" }}>{HIDDEN.includes(game) ? t("duel.whoCanYou") : t("duel.canYou")}</p>
          </div>
          <Link className="btn btn-ghost" to="/">{t("duel.otherGames")}</Link>
        </div>
      </section>
      {game === "relais" && pair && <ConnectRelay fixedPair={pair} rivalSteps={score} />}
      {game === "nombre" && <GuessRelations rivalScore={score} seed={graine} level={graine != null ? niveau : null} />}
      {game === "cache" && <GuessWhoPath puzzle={puzzle} rival={rival} />}
      {game === "qui" && tokenPuzzle && <GuessWhoPath puzzle={tokenPuzzle} rival={rival} />}
      {game === "serie" && <GuessWhoPath series={series} />}
      {/* « Qui est caché ? » propose les autres jeux dans sa carte de fin de partie. */}
      {!HIDDEN.includes(game) && game !== "serie" && <section className="panel" style={{ marginTop: 16 }}>
        <div className="panel-body toolbar" style={{ justifyContent: "space-between" }}>
          <span>{t("home.moreGames")}</span>
          <Link className="btn btn-primary" to="/">{t("home.discover")}</Link>
        </div>
      </section>}
    </main>
  );
}
