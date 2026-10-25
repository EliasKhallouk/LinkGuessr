import { useEffect, useState } from "react";
import { api, lifespan } from "../api";
import { useI18n } from "../i18n/I18nProvider";
import { formatCountdown, msUntilParisMidnight } from "../lib/paris";
import { deviceId } from "../lib/storage";
import PathView from "./PathView";
import PersonChip from "./PersonChip";
import { dailyGrid, SITE_URL } from "../lib/share";
import PersonPicker from "./PersonPicker";
import ShareButton from "./ShareButton";

function Countdown() {
  const { t } = useI18n();
  const [left, setLeft] = useState(msUntilParisMidnight());
  useEffect(() => {
    const id = setInterval(() => setLeft(msUntilParisMidnight()), 1000);
    return () => clearInterval(id);
  }, []);
  return <p className="muted" style={{ margin: "8px 0 0" }}>{t("daily.next", { time: formatCountdown(left) })}</p>;
}

function Hint({ hint }) {
  const { t } = useI18n();
  if (hint.kind === "domain") return <li>{t("who.hintDomain")} <strong>{hint.value}</strong></li>;
  if (hint.kind === "life") return <li>{t("who.hintLife")} <strong>{lifespan(hint)}</strong></li>;
  return <li>{t("who.hintInitials")} <strong>{hint.value}</strong> ({hint.length} {t("who.chars")})</li>;
}

// Défi du jour : même chemin pour tous, une seule tentative par appareil, vérification côté serveur.
export default function DailyChallenge() {
  const { t } = useI18n();
  const [game, setGame] = useState(null);
  const [guess, setGuess] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);

  // On reprend l'état de la partie du jour pour cet appareil (déjà jouée, en cours…).
  useEffect(() => {
    api.dailyGuess(deviceId()).then(setGame).catch((e) => setError(e.message));
  }, []);

  const submit = async () => {
    if (!guess || sending) return;
    setSending(true);
    try {
      setGame(await api.dailyGuess(deviceId(), guess.qid));
      setGuess(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setSending(false);
    }
  };

  if (error) return null;  // le défi est un bonus : en cas de panne, l'accueil reste jouable
  if (!game) return <section className="panel daily fade-in"><div className="panel-body muted">{t("daily.loading")}</div></section>;

  const left = game.max_tries - game.wrong.length;
  return (
    <section className="panel daily fade-in">
      <div className="panel-header">
        <span className="panel-title">{t("daily.title", { n: game.number })}</span>
        {!game.finished && <span className="kpi">{t("daily.triesLeft", { n: left })}</span>}
      </div>
      <div className="panel-body">
        {!game.finished && <p style={{ marginTop: 0 }}>{t("daily.rules")}</p>}
        <PathView path={game.path} persons={game.persons} hops={game.hops}
          hiddenIndex={game.finished ? null : game.masked_index} />

        {!game.finished && (
          <form className="row" style={{ alignItems: "end" }} onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <PersonPicker id="daily-guess" label={t("who.question")} value={guess} onChange={setGuess} />
            <div><button type="submit" className="btn btn-primary" disabled={!guess || sending}>{t("guess.verify")}</button></div>
          </form>
        )}

        {game.wrong.length > 0 && !game.finished && (
          <p className="muted">{t("daily.notThem")} {game.wrong.map((w) => w.name).join(", ")}</p>
        )}
        {game.hints.length > 0 && !game.finished && <ul className="hints">{game.hints.map((h) => <Hint key={h.kind} hint={h} />)}</ul>}

        {game.finished && (
          <div className={game.solved ? "success-box" : "panel result-box"} style={{ marginTop: 12 }}>
            <p style={{ margin: 0, fontWeight: 600 }}>
              {game.solved ? t("daily.won", { n: game.tries }) : t("daily.lost")}
            </p>
            <div style={{ marginTop: 8 }}><PersonChip person={game.answer} showDescription size={56} /></div>
            {game.stats?.players > 0 && (
              <p className="muted" style={{ marginTop: 8 }}>
                {t("daily.stats", { players: game.stats.players, pct: Math.round((100 * game.stats.solved) / game.stats.players) })}
              </p>
            )}
            <div className="toolbar" style={{ marginTop: 8 }}>
              <ShareButton
                text={[
                  `LinkGuessr #${game.number} 🔗`,
                  `${game.persons[game.path[0]].name} → ? → ${game.persons[game.path[2]].name}`,
                  `${dailyGrid(game.wrong.length, game.solved, game.max_tries)} · ${t("share.hints", { n: Math.min(game.wrong.length, 3) })}`,
                ].join("\n")}
                url={`${SITE_URL}/jour/${game.number}`}
                onShared={() => api.logEvent("daily", { event: "share", number: game.number })}
              />
            </div>
            <Countdown />
          </div>
        )}
      </div>
    </section>
  );
}
