import { useEffect, useRef, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes } from "react-router-dom";
import "./App.css";
import { useI18n } from "./i18n/I18nProvider";
import About from "./pages/About";
import Contact from "./pages/Contact";
import Home from "./pages/Home";
import Privacy from "./pages/Privacy";
import LinkGuessrLogo from "./components/LinkGuessrLogo";
import PersonDrawer from "./components/PersonDrawer";
import DailyPage from "./pages/DailyPage";
import Duel from "./pages/Duel";
import Admin from "./pages/Admin";
import Lab from "./pages/Lab";
import Person from "./pages/Person";

function App() {
  const { t, lang, setLang } = useI18n();
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem("theme") || "dark"; } catch { return "dark"; }
  });
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("theme", theme); } catch {}
  }, [theme]);
  // close menu on outside click
  useEffect(() => {
    const onDocClick = (e) => {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  }, []);
  return (
    <div className="app-shell">
      <header className="header">
        <div className="brand">
          <LinkGuessrLogo size={36} className="brand-logo" />
          <h1 className="title">
            <Link to="/" className="title-link">Link<span className="title-accent">Guessr</span></Link>
          </h1>
        </div>
        <p className="tagline">{t("app.tagline")}</p>
        {/* Nav moved into ellipsis menu */}
        <div className="header-ellipsis" ref={menuRef}>
          <button aria-label="menu" className="btn-ellipsis" onClick={() => setMenuOpen((o) => !o)}>⋯</button>
          {menuOpen && (
            <div className="popover">
              <div className="menu-section">
                <div className="menu-title">{t("nav.navigation")}</div>
                <NavLink to="/" onClick={() => setMenuOpen(false)} className={({ isActive }) => isActive ? "menu-link active" : "menu-link"}>{t("nav.home")}</NavLink>
                <NavLink to="/a-propos" onClick={() => setMenuOpen(false)} className={({ isActive }) => isActive ? "menu-link active" : "menu-link"}>{t("nav.about")}</NavLink>
                <NavLink to="/contact" onClick={() => setMenuOpen(false)} className={({ isActive }) => isActive ? "menu-link active" : "menu-link"}>{t("nav.contact")}</NavLink>
                <NavLink to="/lab" onClick={() => setMenuOpen(false)} className={({ isActive }) => isActive ? "menu-link active" : "menu-link"}>Lab</NavLink>
                <NavLink to="/politique-de-confidentialite" onClick={() => setMenuOpen(false)} className={({ isActive }) => isActive ? "menu-link active" : "menu-link"}>{t("nav.privacy")}</NavLink>
              </div>
              <hr className="menu-sep" />
              <div className="control-group">
                <label htmlFor="lang-select">{t("app.language")}</label>
                <select id="lang-select" value={lang} onChange={(e) => setLang(e.target.value)}>
                  <option value="fr">🇫🇷 Français</option>
                  <option value="en">🇬🇧 English</option>
                </select>
              </div>
              <div className="control-group" style={{ marginTop: 8 }}>
                <label htmlFor="theme-select">{t("app.theme")}</label>
                <select id="theme-select" value={theme} onChange={(e) => setTheme(e.target.value)}>
                  <option value="light">☀️ {t("app.themeLight")}</option>
                  <option value="dark">🌙 {t("app.themeDark")}</option>
                </select>
              </div>
            </div>
          )}
        </div>
      </header>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/a-propos" element={<About />} />
        <Route path="/lab" element={<Lab />} />
        <Route path="/stats" element={<Navigate to="/lab" replace />} />
        <Route path="/personne/:qid" element={<Person />} />
        <Route path="/jour/:number" element={<DailyPage />} />
        <Route path="/defi" element={<Duel />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/politique-de-confidentialite" element={<Privacy />} />
      </Routes>
      <PersonDrawer />

      <footer className="footer">
        <span>© {new Date().getFullYear()} LinkGuessr - Elias Khallouk</span>
        <span className="footer-credits">
          {t("footer.data")}{" "}
          <a href="https://fr.wikipedia.org" target="_blank" rel="noreferrer">Wikipédia</a>
          {" "}(<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.fr" target="_blank" rel="noreferrer">CC BY-SA 4.0</a>),{" "}
          <a href="https://www.wikidata.org" target="_blank" rel="noreferrer">Wikidata</a> (CC0),{" "}
          {t("footer.images")}{" "}
          <a href="https://commons.wikimedia.org" target="_blank" rel="noreferrer">Wikimedia Commons</a>.{" "}
          <Link to="/a-propos">{t("footer.more")}</Link>
        </span>
      </footer>
    </div>
  );
}

export default App;
