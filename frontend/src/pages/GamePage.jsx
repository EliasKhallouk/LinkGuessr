import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import GameIcon from "../components/GameIcon";
import Modal from "../components/Modal";
import { useI18n } from "../i18n/I18nProvider";
import { load, save } from "../lib/storage";

// Un jeu en plein écran : barre de jeu (retour au hub, titre, aide) puis le jeu.
// « Comment jouer » s'ouvre tout seul à la première visite, comme sur Wordle.
export default function GamePage({ game }) {
  const { t } = useI18n();
  const seenKey = `lg-howto-${game.key}`;
  const [help, setHelp] = useState(() => !load(seenKey, false));

  useEffect(() => {
    const previous = document.title;
    document.title = `${t(`games.${game.key}.title`)} · LinkGuessr`;
    return () => { document.title = previous; };
  }, [game.key, t]);

  const closeHelp = () => {
    save(seenKey, true);
    setHelp(false);
  };

  const steps = [1, 2, 3].map((i) => t(`games.${game.key}.how${i}`));

  return (
    <main className="page game-page">
      <div className="game-bar">
        <Link to="/" className="game-back" aria-label={t("hub.back")}><span aria-hidden="true">←</span><span className="game-back-text" aria-hidden="true">{t("hub.back").replace(/^←\s*/, "")}</span></Link>
        <h2 className="game-bar-title">
          <span className="game-bar-icon"><GameIcon game={game.key} size={28} /></span>
          {t(`games.${game.key}.title`)}
        </h2>
        <button type="button" className="icon-btn" onClick={() => setHelp(true)} aria-label={t("hub.howTo")}>?</button>
      </div>

      {game.element}

      <Modal open={help} onClose={closeHelp} title={t("hub.howTo")}>
        <div className="howto-hero"><GameIcon game={game.key} size={64} /></div>
        <ol className="howto-steps">
          {steps.map((s, i) => <li key={i}><span className="howto-num">{i + 1}</span><span>{s}</span></li>)}
        </ol>
        <button type="button" className="btn btn-block" onClick={closeHelp}>{t("hub.letsGo")}</button>
      </Modal>
    </main>
  );
}
