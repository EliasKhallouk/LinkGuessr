import { useEffect, useState } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import ConnectRelay from "../components/ConnectRelay";
import GuessRelations from "../components/GuessRelations";
import { useI18n } from "../i18n/I18nProvider";

// Page d'arrivée d'un lien de duel : /defi?jeu=relais&paire=Q1-Q2&score=3 ou /defi?jeu=nombre&score=340
export default function Duel() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const game = params.get("jeu");
  const score = Number(params.get("score")) || null;
  const pairParam = params.get("paire") || "";
  const [pair, setPair] = useState(null);
  const [error, setError] = useState(false);

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

  if (!["relais", "nombre"].includes(game) || error) return <Navigate to="/" replace />;
  return (
    <main className="page fade-in">
      <section className="panel duel-banner">
        <div className="panel-body">
          <p style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
            {game === "relais"
              ? (pair ? t("duel.relayIntro", { a: pair.from.name, b: pair.to.name, n: score }) : "…")
              : t("duel.countIntro", { n: score })}
          </p>
          <p className="muted" style={{ margin: "4px 0 0" }}>{t("duel.canYou")}</p>
        </div>
      </section>
      {game === "relais" && pair && <ConnectRelay fixedPair={pair} rivalSteps={score} />}
      {game === "nombre" && <GuessRelations rivalScore={score} />}
    </main>
  );
}
