import { useI18n } from "../i18n/I18nProvider";

export default function Privacy() {
  const { t } = useI18n();
  return (
    <main className="grid">
      <div className="col-main">
        <section className="panel fade-in">
          <div className="panel-header">
            <span className="panel-title">{t("pages.privacy.title")}</span>
          </div>
          <div className="panel-body">
            <p>{t("pages.privacy.p1")}</p>
            <p style={{ marginTop: 8 }}>{t("pages.privacy.p2")}</p>
            <p style={{ marginTop: 8 }}>{t("pages.privacy.p3")}</p>
            <p style={{ marginTop: 8 }}>
              {t("pages.privacy.p4prefix")}<a className="chemin-link" href="mailto:linkguessr@gmail.com"> linkguessr@gmail.com</a>.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
