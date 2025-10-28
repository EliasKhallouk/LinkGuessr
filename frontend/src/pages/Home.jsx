import AdSlot from "../components/AdSlot";
import Game from "../components/Game";
import GuessRelations from "../components/GuessRelations";
import GuessWhoPath from "../components/GuessWhoPath";
import Leaderboard from "../components/Leaderboard";
import Tabs from "../components/Tabs";
import { useI18n } from "../i18n/I18nProvider";

export default function Home() {
  const { t } = useI18n();
  return (
    <main className="grid">
      <div className="col-main">
        <Tabs
          tabs={[
            { key: "path", title: t("tabs.path"), content: <Game /> },
            { key: "guesswho", title: "Qui est caché ?", content: <GuessWhoPath /> },
            { key: "relations", title: t("tabs.relations"), content: (
              <>
                <GuessRelations />
                <Leaderboard />
              </>
            ) },
          ]}
        />
      </div>
      <div className="col-side">
        <AdSlot />
      </div>
    </main>
  );
}
