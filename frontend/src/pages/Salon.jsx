import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import Avatar from "../components/Avatar";
import DifficultyPicker from "../components/DifficultyPicker";
import { ERAS } from "../components/GuessWhoPath";
import PathView from "../components/PathView";
import ShareButton from "../components/ShareButton";
import { LIVE_URL } from "../config";
import { useI18n } from "../i18n/I18nProvider";
import { confetti } from "../lib/confetti";
import { SITE_URL } from "../lib/share";
import { load, save } from "../lib/storage";
import { trackUmami } from "../lib/tracking";

// Salon en direct (« Qui est caché ? » à plusieurs) : /salon pour créer ou rejoindre, /salon/K7QF pour jouer.
// Tout passe par un WebSocket vers la VM ; le serveur mène la partie (voir backend/app/live.py).
export default function Salon() {
  const { code } = useParams();
  return code ? <Room code={code.toUpperCase()} /> : <Lobby />;
}

function Lobby() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [niveau, setNiveau] = useState("moyen");
  const [epoque, setEpoque] = useState("aujourdhui");
  const [code, setCode] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const room = await api.createRoom({ niveau, epoque });
      trackUmami("live", "salon_cree", { niveau });
      navigate(`/salon/${room.code}`);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <section className="panel fade-in">
      <div className="panel-body">
        <h3 style={{ marginTop: 0 }}>{t("live.createTitle")}</h3>
        <div className="toolbar">
          <DifficultyPicker value={niveau} onChange={setNiveau} />
          <select value={epoque} onChange={(e) => setEpoque(e.target.value)} aria-label={t("who.era")}>
            {ERAS.map((e) => <option key={e} value={e}>{t(`who.eras.${e}`)}</option>)}
          </select>
          <button className="btn btn-primary" onClick={create} disabled={busy}>{t("live.create")}</button>
        </div>
        <h3>{t("live.joinTitle")}</h3>
        <form className="toolbar" onSubmit={(e) => { e.preventDefault(); if (code.length === 4) navigate(`/salon/${code}`); }}>
          <input value={code} maxLength={4} placeholder="K7QF" aria-label={t("live.code")} style={{ width: 120, textTransform: "uppercase" }}
            onChange={(e) => setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))} />
          <button className="btn" type="submit" disabled={code.length !== 4}>{t("live.join")}</button>
        </form>
        {error && <div className="error-box" style={{ marginTop: 12 }}><p style={{ margin: 0 }}>{error}</p></div>}
      </div>
    </section>
  );
}

// Salon déjà rejoint dans cet onglet : on y revient directement après un rechargement.
const joinedKey = (code) => `lg-live-${code}`;
function session(key, value) {
  try {
    if (value === undefined) return sessionStorage.getItem(key);
    if (value === null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, value);
  } catch { /* stockage indisponible : pas de retour automatique */ }
  return null;
}

// Jeton aléatoire de ce navigateur : il permet de revenir dans le salon après un rechargement.
function liveToken() {
  let token = load("lg-live-token", null);
  if (!token) {
    token = crypto.randomUUID();
    save("lg-live-token", token);
  }
  return token;
}

function Room({ code }) {
  const { t } = useI18n();
  const [pseudo, setPseudo] = useState(() => load("lg-live-pseudo", ""));
  const [joined, setJoined] = useState(() => session(joinedKey(code)) === "1");
  const [me, setMe] = useState(null);
  const [room, setRoom] = useState(null);
  const [fatal, setFatal] = useState(null);
  const [lost, setLost] = useState(false);
  const [, tick] = useState(0);
  const [slow, setSlow] = useState(false);
  const ws = useRef(null);
  const receivedAt = useRef(0);
  const retries = useRef(0);
  const ended = useRef(null);
  const isFatal = useRef(false);

  const connect = useCallback(() => {
    const socket = new WebSocket(`${LIVE_URL}/${code}`);
    ws.current = socket;
    socket.onopen = () => socket.send(JSON.stringify({ t: "join", token: liveToken(), pseudo: load("lg-live-pseudo", "") }));
    socket.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.t === "welcome") {
        setMe(msg.pid);
        setLost(false);
        retries.current = 0;
      } else if (msg.t === "state") {
        receivedAt.current = performance.now();
        setRoom(msg);
      } else if (msg.t === "error" && msg.fatal) {
        isFatal.current = true;
        setFatal(msg.message);
        session(joinedKey(code), null);
      }
    };
    // Coupure (réseau, mise en veille du téléphone) : on se reconnecte, la place est gardée par le jeton.
    socket.onclose = () => {
      if (ws.current !== socket || isFatal.current) return;
      setLost(true);
      if (retries.current < 6) setTimeout(() => ws.current === socket && connect(), 1000 * 2 ** retries.current++);
    };
  }, [code]);

  // Toujours pas de salon après 8 s : sans doute un bloqueur ou un pare-feu.
  useEffect(() => {
    if (!joined || room) return undefined;
    const id = setTimeout(() => setSlow(true), 8000);
    return () => clearTimeout(id);
  }, [joined, room]);

  useEffect(() => {
    if (!joined) return undefined;
    connect();
    return () => {
      const socket = ws.current;
      ws.current = null;
      socket?.close();
    };
  }, [joined, connect]);

  // Compte à rebours : affiché d'après le temps restant annoncé par le serveur.
  useEffect(() => {
    if (room?.phase !== "question" && room?.phase !== "reveal") return undefined;
    const id = setInterval(() => tick((n) => n + 1), 200);
    return () => clearInterval(id);
  }, [room?.phase]);

  // Fin de partie : confettis pour le vainqueur, un événement par partie.
  useEffect(() => {
    if (room?.phase !== "end") {
      ended.current = false;
      return;
    }
    if (ended.current) return;
    ended.current = true;
    const rank = room.players.findIndex((p) => p.pid === me) + 1;
    if (rank === 1 && room.players.length > 1) confetti();
    trackUmami("live", "salon_partie_fin", { joueurs: room.players.length, rang: rank });
  }, [room, me]);

  const send = (msg) => ws.current?.readyState === WebSocket.OPEN && ws.current.send(JSON.stringify(msg));
  const join = (e) => {
    e.preventDefault();
    save("lg-live-pseudo", pseudo.trim());
    session(joinedKey(code), "1");
    isFatal.current = false;
    setFatal(null);
    setJoined(true);
  };

  if (fatal) {
    return (
      <section className="panel fade-in"><div className="panel-body">
        <div className="error-box"><p style={{ margin: 0 }}>{fatal}</p></div>
        <div className="toolbar" style={{ marginTop: 12 }}>
          <a className="btn btn-primary" href="/salon">{t("live.back")}</a>
        </div>
      </div></section>
    );
  }

  if (!joined) {
    return (
      <section className="panel fade-in"><div className="panel-body">
        <p style={{ marginTop: 0 }}>{t("live.joining", { code })}</p>
        <form className="toolbar" onSubmit={join}>
          <input value={pseudo} maxLength={16} placeholder={t("guess.exampleName")} aria-label={t("guess.yourName")}
            onChange={(e) => setPseudo(e.target.value)} autoFocus />
          <button className="btn btn-primary" type="submit" disabled={!pseudo.trim()}>{t("live.enter")}</button>
        </form>
      </div></section>
    );
  }

  if (!room) {
    return (
      <section className="panel"><div className="panel-body">
        {lost || slow ? (
          <>
            <div className="error-box"><p style={{ margin: 0 }}>{t("live.unreachable")}</p></div>
            <div className="toolbar" style={{ marginTop: 12 }}>
              <button className="btn btn-primary" onClick={() => window.location.reload()}>{t("live.retry")}</button>
            </div>
          </>
        ) : <p className="muted" style={{ margin: 0 }}>{t("live.connecting")}</p>}
      </div></section>
    );
  }

  const isHost = room.host === me;
  const host = room.players.find((p) => p.pid === room.host);
  const remaining = Math.max(0, room.remaining_ms - (performance.now() - receivedAt.current));
  const mine = room.players.find((p) => p.pid === me);

  return (
    <>
      {lost && <div className="error-box" style={{ marginBottom: 12 }}><p style={{ margin: 0 }}>{t("live.lost")}</p></div>}
      <section className="panel fade-in">
        <div className="panel-header">
          <span className="panel-title">{t("live.room", { code })}</span>
          <ShareButton text={t("live.inviteText", { code })} url={`${SITE_URL}/salon/${code}`}
            utm={{ source: "partage", campaign: "salon" }} label={t("live.invite")} />
        </div>
        <div className="panel-body">
          {room.error && <div className="error-box"><p style={{ margin: 0 }}>{room.error}</p></div>}

          {(room.phase === "lobby" || room.phase === "end") && (
            <>
              {room.phase === "end" && <Podium players={room.players} me={me} t={t} />}
              {isHost ? (
                <div className="toolbar" style={{ marginTop: 8 }}>
                  <DifficultyPicker value={room.niveau} onChange={(niveau) => send({ t: "settings", niveau })} />
                  <select value={room.epoque} onChange={(e) => send({ t: "settings", epoque: e.target.value })} aria-label={t("who.era")}>
                    {ERAS.map((e) => <option key={e} value={e}>{t(`who.eras.${e}`)}</option>)}
                  </select>
                  <button className="btn btn-primary" onClick={() => { send({ t: "start" }); trackUmami("live", "salon_partie_debut", { niveau: room.niveau, joueurs: room.players.length }); }}>
                    {room.phase === "end" ? t("live.rematch") : t("live.start")}
                  </button>
                </div>
              ) : (
                <p className="muted">{t("live.waitHost", { name: host?.pseudo || "…" })} · {t(`difficulty.${room.niveau}`)} · {t(`who.eras.${room.epoque}`)}</p>
              )}
              {room.phase === "lobby" && <p className="muted">{t("live.rules", { rounds: room.rounds, seconds: room.round_ms / 1000 })}</p>}
            </>
          )}

          {room.phase === "starting" && <p className="muted">{t("live.preparing")}</p>}

          {(room.phase === "question" || room.phase === "reveal") && room.puzzle && (
            <Round room={room} me={me} remaining={remaining} send={send} t={t} />
          )}
        </div>
      </section>

      <section className="panel fade-in" style={{ marginTop: 12 }}>
        <div className="panel-header"><span className="panel-title">{t("live.players", { n: room.players.length })}</span>
          {mine && <span className="kpi">⭐ <strong>{mine.score.toLocaleString("fr-FR")}</strong></span>}</div>
        <div className="panel-body">
          <ol className="live-players">
            {room.players.map((p) => (
              <li key={p.pid} className={p.connected ? "" : "muted"}>
                <span>{p.pid === room.host ? "👑 " : ""}{p.pseudo}{p.pid === me ? ` (${t("live.you")})` : ""}</span>
                <span>
                  {room.phase === "question" && (p.answered ? "✅ " : "⏳ ")}
                  {room.phase === "reveal" && p.last && (p.last.correct ? `+${p.last.points.toLocaleString("fr-FR")} ` : "✗ ")}
                  <strong>{p.score.toLocaleString("fr-FR")}</strong>
                </span>
              </li>
            ))}
          </ol>
        </div>
      </section>
    </>
  );
}

function Round({ room, me, remaining, send, t }) {
  const { puzzle } = room;
  const reveal = room.phase === "reveal";
  const mine = room.players.find((p) => p.pid === me);
  const [picked, setPicked] = useState(null);
  useEffect(() => setPicked(null), [room.round]);
  const chosen = reveal ? mine?.last?.qid : picked;
  const answerQid = puzzle.answer?.qid;
  const persons = reveal ? { ...puzzle.persons, [answerQid]: puzzle.answer } : puzzle.persons;
  const hops = reveal ? { ...puzzle.hops, ...puzzle.answer_hops } : puzzle.hops;

  const pick = (qid) => {
    if (picked || reveal || mine?.answered) return;
    setPicked(qid);
    send({ t: "answer", qid });
  };

  return (
    <>
      <div className="toolbar" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <strong>{t("live.round", { n: room.round, total: room.rounds })}</strong>
        {!reveal && <span className="kpi">⏱ <strong>{Math.ceil(remaining / 1000)}</strong></span>}
      </div>
      {!reveal && (
        <div className="live-timer" aria-hidden="true"><span style={{ width: `${(remaining / room.round_ms) * 100}%` }} /></div>
      )}
      <PathView path={puzzle.path} persons={persons} hops={hops} hiddenIndex={reveal ? null : puzzle.masked_index} />
      <div className="who-choices" role="group" aria-label={t("who.question")}>
        {puzzle.choices.map((p) => {
          const state = reveal ? (p.qid === answerQid ? "right" : p.qid === chosen ? "wrong" : "") : p.qid === chosen ? "chosen" : "";
          return (
            <button key={p.qid} type="button" className={`who-choice live-${state}`} onClick={() => pick(p.qid)}
              disabled={reveal || Boolean(picked) || mine?.answered}
              aria-label={p.description ? `${p.name}, ${p.description}` : p.name}>
              <Avatar person={p} size={44} />
              <span className="person-text">
                <strong>{p.name}</strong>
                {p.description && <span className="person-desc">{p.description}</span>}
              </span>
            </button>
          );
        })}
      </div>
      {!reveal && (picked || mine?.answered) && <p className="muted">{t("live.waitOthers")}</p>}
      {reveal && mine?.last && (
        <p style={{ fontWeight: 700 }}>
          {mine.last.correct ? t("live.right", { n: mine.last.points.toLocaleString("fr-FR") })
            : t("live.wrong", { name: puzzle.answer.name })}
        </p>
      )}
    </>
  );
}

function Podium({ players, me, t }) {
  const medals = ["🥇", "🥈", "🥉"];
  return (
    <div className="panel result-box" style={{ marginBottom: 12 }}>
      <p style={{ margin: 0, fontWeight: 700 }}>{t("live.over")}</p>
      <ol className="live-players">
        {players.map((p, i) => (
          <li key={p.pid} style={{ fontWeight: i < 3 ? 700 : 400 }}>
            <span>{medals[i] || `${i + 1}.`} {p.pseudo}{p.pid === me ? ` (${t("live.you")})` : ""}</span>
            <strong>{p.score.toLocaleString("fr-FR")}</strong>
          </li>
        ))}
      </ol>
    </div>
  );
}
