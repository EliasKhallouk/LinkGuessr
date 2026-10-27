import { Link, Navigate, useSearchParams } from "react-router-dom";
import { usePageMeta } from "../lib/meta";
import DailyChallenge from "../components/DailyChallenge";
import GameIcon from "../components/GameIcon";
import StatsBanner from "../components/StatsBanner";
import { GAMES, gamePath } from "../games";
import { useI18n } from "../i18n/I18nProvider";

// Accueil en « hub », façon NYT Games : le défi du jour en grand, puis une carte par jeu.
export default function Home() {
  const { t } = useI18n();
  usePageMeta(t("meta.home.title"), t("meta.home.description"));
  // Anciens liens « Trouver un chemin depuis cette personne » (/?from=Q…) : direction l'explorateur.
  const [params] = useSearchParams();
  const from = params.get("from");
  if (from) return <Navigate to={`${gamePath("explore")}?de=${encodeURIComponent(from)}`} replace />;

  return (
    <main className="grid grid-single">
      <div className="col-main">
        <header className="home-intro">
          <h2>{t("home.title")}</h2>
          <p>{t("home.text")}</p>
        </header>
        <StatsBanner />
        <DailyChallenge />

        <section aria-labelledby="games-title">
          <h2 id="games-title" className="section-title">{t("hub.games")}</h2>
          <ul className="game-grid">
            {GAMES.map((g) => (
              <li key={g.key}>
                <Link to={g.path} className="game-card" aria-labelledby={`game-${g.key}-title`}
                  aria-describedby={`game-${g.key}-pitch`}>
                  <span className="game-card-icon"><GameIcon game={g.key} size={44} /></span>
                  <span className="game-card-text">
                    <span className="game-card-title" id={`game-${g.key}-title`}>{t(`games.${g.key}.title`)}</span>
                    <span className="game-card-pitch" id={`game-${g.key}-pitch`}>{t(`games.${g.key}.pitch`)}</span>
                  </span>
                  <span className="game-card-tag">{t(`games.${g.key}.tag`)}</span>
                  <span className="game-card-play" aria-hidden="true">{t("hub.play")} →</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </main>
  );
}
