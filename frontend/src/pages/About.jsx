import { useI18n } from "../i18n/I18nProvider";

export default function About() {
  const { t } = useI18n();
  return (
    <main className="grid">
      <div className="col-main">
        <section className="panel fade-in">
          <div className="panel-header">
            <span className="panel-title">{t("pages.about.title")}</span>
          </div>
          <div className="panel-body">
            <p>{t("pages.about.p1")}</p>
            <p style={{ marginTop: 8 }}>{t("pages.about.p2")}</p>
            <p style={{ marginTop: 8 }}>{t("pages.about.p3")}</p>
          </div>
        </section>
      </div>
    </main>
  );
}
