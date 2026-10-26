import { useEffect, useMemo, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import ConnectRelay from "../components/ConnectRelay";
import GuessRelations from "../components/GuessRelations";
import GuessWhoPath from "../components/GuessWhoPath";
import { LEVELS } from "../components/DifficultyPicker";
import { useI18n } from "../i18n/I18nProvider";
import { track } from "../lib/tracking";

// Page d'arrivée d'un lien de duel : /defi?jeu=relais&paire=Q1-Q2&score=3, /defi?jeu=nombre&score=340
// ou /defi?jeu=cache&chemin=Q1-Q2-Q3&cache=1&niveau=facile&essais=2&trouve=1 (même énigme « Qui est caché ? »).
const GAMES = { relais: "relay", nombre: "guess_count", cache: "guess_who" };
export default function Duel() {
  const { t } = useI18n();
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
  const puzzle = useMemo(() => ({ chemin, cache, niveau }), [chemin, cache, niveau]);
  const tries = Number(params.get("essais")) || 0;
  const found = params.get("trouve") === "1";
  const rival = useMemo(() => ({ found, tries }), [found, tries]);
  const validPuzzle = /^Q\d+(-Q\d+){2,7}$/.test(chemin) && cache >= 1 && cache <= chemin.split("-").length - 2;

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

  if (!GAMES[game] || error || (game === "cache" && !validPuzzle)) return <Navigate to="/" replace />;
  return (
    <main className="page fade-in">
      <section className="panel duel-banner">
        <div className="panel-body">
          <p style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
            {game === "relais"
              ? (pair ? t("duel.relayIntro", { a: pair.from.name, b: pair.to.name, n: score }) : "…")
              : game === "cache"
                ? (found ? t("duel.whoFound", { n: tries }) : t("duel.whoLost"))
                : t("duel.countIntro", { n: score })}
          </p>
          <p className="muted" style={{ margin: "4px 0 0" }}>{game === "cache" ? t("duel.whoCanYou") : t("duel.canYou")}</p>
        </div>
      </section>
      {game === "relais" && pair && <ConnectRelay fixedPair={pair} rivalSteps={score} />}
      {game === "nombre" && <GuessRelations rivalScore={score} />}
      {game === "cache" && <GuessWhoPath puzzle={puzzle} rival={rival} />}
      <section className="panel" style={{ marginTop: 16 }}>
        <div className="panel-body toolbar" style={{ justifyContent: "space-between" }}>
          <span>{t("home.moreGames")}</span>
          <Link className="btn btn-primary" to="/">{t("home.discover")}</Link>
        </div>
      </section>
    </main>
  );
}
