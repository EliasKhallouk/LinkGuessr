import { useI18n } from "../i18n/I18nProvider";
import { usePageMeta } from "../lib/meta";

const SECTIONS = [
  ["pages.about.dataTitle", ["pages.about.data1", "pages.about.data2", "pages.about.data3", "pages.about.data4"]],
  ["pages.about.licenseTitle", ["pages.about.license1", "pages.about.license2", "pages.about.license3", "pages.about.license4"]],
];

export default function About() {
  const { t } = useI18n();
  usePageMeta(t("meta.about.title"), t("meta.about.description"));
  return (
    <main className="page fade-in">
      <section className="panel">
        <div className="panel-header"><span className="panel-title">{t("pages.about.title")}</span></div>
        <div className="panel-body legal">
          <p>{t("pages.about.p1")}</p>
          {SECTIONS.map(([title, items]) => (
            <div key={title}>
              <h3>{t(title)}</h3>
              <ul>{items.map((k) => <li key={k}>{t(k)}</li>)}</ul>
            </div>
          ))}
          <p>{t("pages.about.p3")}</p>
        </div>
      </section>
    </main>
  );
}
