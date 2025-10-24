import { useEffect, useState } from "react";
import "./App.css";
import AdSlot from "./components/AdSlot";
import Game from "./components/Game";
import GuessRelations from "./components/GuessRelations";
import Leaderboard from "./components/Leaderboard";
import Tabs from "./components/Tabs";
import { useI18n } from "./i18n/I18nProvider";
import "./playful-effects.css";
import PlayfulDemo from "./components/PlayfulDemo";

function App() {
  const { t, lang, setLang } = useI18n();
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem("theme") || "dark"; } catch { return "dark"; }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("theme", theme); } catch {}
  }, [theme]);
  return (
    <div className="app-shell">
      <header className="header">
        <div className="brand">
          <span className="logo-dot" />
          <h1 className="title">LinkGuessr</h1>
        </div>
        <p className="tagline">{t("app.tagline")}</p>
        
        <div className="header-controls">
          <div className="control-group">
            <label htmlFor="lang-select">{t("app.language")}</label>
            <select id="lang-select" value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="fr">🇫🇷 Français</option>
              <option value="en">🇬🇧 English</option>
            </select>
          </div>
          
          <div className="control-group">
            <label htmlFor="theme-select">{t("app.theme")}</label>
            <select id="theme-select" value={theme} onChange={(e) => setTheme(e.target.value)}>
              <option value="light">☀️ {t("app.themeLight")}</option>
              <option value="dark">🌙 {t("app.themeDark")}</option>
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
                  <PlayfulDemo />
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
