import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ConnectRelay from "../components/ConnectRelay";
import DailyChallenge from "../components/DailyChallenge";
import Game from "../components/Game";
import GuessRelations from "../components/GuessRelations";
import GuessWhoPath from "../components/GuessWhoPath";
import Leaderboard from "../components/Leaderboard";
import StatsBanner from "../components/StatsBanner";
import Tabs from "../components/Tabs";
import { useI18n } from "../i18n/I18nProvider";

// Ordre des onglets : l'explorateur d'abord (le défi du jour, juste au-dessus, est déjà un « Qui est caché ? »),
// puis les jeux du plus accessible au plus exigeant.
const TABS = [
  { key: "explore", content: <Game /> },
  { key: "guesswho", content: <GuessWhoPath /> },
  { key: "relay", content: <ConnectRelay /> },
  { key: "count", content: <><GuessRelations /><Leaderboard /></> },
];

export default function Home() {
  const { t } = useI18n();
  const [tab, setTab] = useState(0);
  // « Trouver un chemin depuis cette personne » (/?from=Q…) : on bascule sur l'explorateur.
  const [params] = useSearchParams();
  const from = params.get("from");
  useEffect(() => { if (from) setTab(TABS.findIndex((x) => x.key === "explore")); }, [from]);
  return (
    <main className="grid grid-single">
      <div className="col-main">
        <header className="home-intro">
          <h2>{t("home.title")}</h2>
          <p>{t("home.text")}</p>
        </header>
        <StatsBanner />
        <DailyChallenge />
        <Tabs
          active={tab}
          onChange={setTab}
          tabs={TABS.map(({ key, content }) => ({ key, title: t(`tabs.${key}`), content }))}
        />
      </div>
    </main>
  );
}
