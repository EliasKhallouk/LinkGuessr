import { useI18n } from "../i18n/I18nProvider";

// Page Lab : analyses du réseau, ouvertes à tous (phase 5 de la refonte).
export default function Lab() {
  const { t } = useI18n();
  return (
    <main className="page fade-in">
      <section className="panel">
        <div className="panel-header"><span className="panel-title">Lab</span></div>
        <div className="panel-body">
          <p style={{ marginTop: 0 }}>{t("lab.soon")}</p>
          <ul className="muted">
            <li>{t("lab.item1")}</li>
            <li>{t("lab.item2")}</li>
            <li>{t("lab.item3")}</li>
          </ul>
        </div>
      </section>
    </main>
  );
}
