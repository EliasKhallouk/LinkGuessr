import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import PathView from "../components/PathView";
import PersonChip from "../components/PersonChip";
import { useI18n } from "../i18n/I18nProvider";
import { formatLongDate, parseDay } from "../lib/format";
import Home from "./Home";

// /jour/12 : le défi du jour si c'est celui d'aujourd'hui, sinon l'archive (réponse révélée).
export default function DailyPage() {
  const { number } = useParams();
  const { t, lang } = useI18n();
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setData(null);
    setError(false);
    api.dailyArchive(number).then(setData).catch(() => setError(true));
  }, [number]);

  const playLink = <Link className="btn btn-primary" to="/">{t("home.discover")}</Link>;
  if (error) return <main className="page"><p className="muted">{t("daily.unknown")}</p>{playLink}</main>;
  if (!data) return <main className="page"><p className="muted">{t("daily.loading")}</p></main>;
  if (data.current) return <Home />;
  if (!data.answer) return <main className="page"><p className="muted">{t("daily.notYet")}</p>{playLink}</main>;
  return (
    <main className="page fade-in">
      <section className="panel">
        <div className="panel-header">
          <span className="panel-title">{t("daily.archiveTitle", { n: data.number, day: formatLongDate(parseDay(data.day), lang) })}</span>
        </div>
        <div className="panel-body">
          <PathView path={data.path} persons={data.persons} hops={data.hops} />
          <p style={{ marginTop: 12 }}>{t("daily.answerWas")} <PersonChip person={data.answer} size={32} /></p>
          {playLink}
        </div>
      </section>
    </main>
  );
}
