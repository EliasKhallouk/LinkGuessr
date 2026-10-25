import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ConnectRelay from "../components/ConnectRelay";
import Game from "../components/Game";
import GuessRelations from "../components/GuessRelations";
import GuessWhoPath from "../components/GuessWhoPath";
import Leaderboard from "../components/Leaderboard";
import PersonDrawer from "../components/PersonDrawer";
import StatsBanner from "../components/StatsBanner";
import Tabs from "../components/Tabs";
import { useI18n } from "../i18n/I18nProvider";

export default function Home() {
  const { t } = useI18n();
  const [tab, setTab] = useState(0);
  // « Trouver un chemin depuis cette personne » (/?from=Q…) : on bascule sur l'explorateur.
  const [params] = useSearchParams();
  const from = params.get("from");
  useEffect(() => { if (from) setTab(0); }, [from]);
  return (
    <main className="grid grid-single">
      <div className="col-main">
        <StatsBanner />
        <Tabs
          active={tab}
          onChange={setTab}
          tabs={[
            { key: "path", title: t("tabs.path"), content: <Game /> },
            { key: "guesswho", title: t("tabs.guesswho"), content: <GuessWhoPath /> },
            { key: "relations", title: t("tabs.relations"), content: (
              <>
                <GuessRelations />
                <Leaderboard />
              </>
            ) },
            { key: "relay", title: t("tabs.relay"), content: <ConnectRelay /> },
          ]}
        />
      </div>
      <PersonDrawer />
    </main>
  );
}
