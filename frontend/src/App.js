import "./App.css";
import AdSlot from "./components/AdSlot";
import Game from "./components/Game";
import GuessRelations from "./components/GuessRelations";
import Leaderboard from "./components/Leaderboard";
import Tabs from "./components/Tabs";
import { useI18n } from "./i18n/I18nProvider";

function App() {
  const { t, lang, setLang } = useI18n();
  return (
    <div className="app-shell">
      <header className="header">
        <div className="brand">
          <span className="logo-dot" />
          <h1 className="title">LinkGuessr</h1>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "space-between" }}>
          <p className="tagline" style={{ margin: 0 }}>{t("app.tagline")}</p>
          <div>
            <label className="muted" style={{ fontSize: 12, marginRight: 6 }}>{t("app.language")}:</label>
            <select value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="fr">Français</option>
              <option value="en">English</option>
            </select>
          </div>
        </div>
      </header>

      <main className="grid">
        <div className="col-main">
          <Tabs
            tabs={[
              { key: "path", title: t("tabs.path"), content: <Game /> },
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

      <footer className="footer">
        <span>© {new Date().getFullYear()} LinkGuessr - Elias Khallouk</span>
      </footer>
    </div>
  );
}

export default App;
