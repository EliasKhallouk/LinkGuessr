import { useI18n } from "../i18n/I18nProvider";
import { usePageMeta } from "../lib/meta";

const ITEMS = ["scores", "games", "explore", "prefs", "logs"];

export default function Privacy() {
  const { t } = useI18n();
  usePageMeta(t("meta.privacy.title"), t("meta.privacy.description"));
  return (
    <main className="page fade-in">
      <section className="panel">
        <div className="panel-header"><span className="panel-title">{t("pages.privacy.title")}</span></div>
        <div className="panel-body legal">
          <p>{t("pages.privacy.p1")}</p>
          <h3>{t("pages.privacy.storedTitle")}</h3>
          <ul>{ITEMS.map((k) => <li key={k}>{t(`pages.privacy.${k}`)}</li>)}</ul>
          <h3>{t("pages.privacy.localTitle")}</h3>
          <p>{t("pages.privacy.local")}</p>
          <p>{t("pages.privacy.p3")}</p>
          <p>
            {t("pages.privacy.p4prefix")} <a className="chemin-link" href="mailto:linkguessr@gmail.com">linkguessr@gmail.com</a>.
          </p>
        </div>
      </section>
    </main>
  );
}
