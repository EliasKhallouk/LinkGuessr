import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import DailyChallenge from "../components/DailyChallenge";
import PathView from "../components/PathView";
import PersonChip from "../components/PersonChip";
import { useI18n } from "../i18n/I18nProvider";

// /jour/12 : le défi du jour si c'est celui d'aujourd'hui, sinon l'archive (réponse révélée).
export default function DailyPage() {
  const { number } = useParams();
  const { t } = useI18n();
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setData(null);
    setError(false);
    api.dailyArchive(number).then(setData).catch(() => setError(true));
  }, [number]);

  const playLink = <Link className="btn" to="/">{t("daily.play")}</Link>;
  if (error) return <main className="page"><p className="muted">{t("daily.unknown")}</p>{playLink}</main>;
  if (!data) return <main className="page"><p className="muted">{t("daily.loading")}</p></main>;
  if (data.current) return <main className="page"><DailyChallenge /></main>;
  if (!data.answer) return <main className="page"><p className="muted">{t("daily.notYet")}</p>{playLink}</main>;
  return (
    <main className="page fade-in">
      <section className="panel">
        <div className="panel-header">
          <span className="panel-title">{t("daily.archiveTitle", { n: data.number, day: data.day })}</span>
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
