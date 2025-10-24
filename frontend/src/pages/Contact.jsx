import { useI18n } from "../i18n/I18nProvider";

export default function Contact() {
  const { t } = useI18n();
  return (
    <main className="grid">
      <div className="col-main">
        <section className="panel fade-in">
          <div className="panel-header">
            <span className="panel-title">{t("pages.contact.title")}</span>
          </div>
          <div className="panel-body">
            <p>{t("pages.contact.p1")}</p>
            <p style={{ marginTop: 8 }}>
              {t("pages.contact.emailLabel")} <a className="chemin-link" href="mailto:linkguessr@gmail.com">linkguessr@gmail.com</a>
            </p>
            <p style={{ marginTop: 8 }}>{t("pages.contact.socials")}</p>
          </div>
        </section>
      </div>
    </main>
  );
}
