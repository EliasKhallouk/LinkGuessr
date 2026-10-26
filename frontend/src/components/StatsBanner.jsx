import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useI18n } from "../i18n/I18nProvider";
import { formatLongDate } from "../lib/format";

// Compteur animé de 0 à `value` (ease-out), respecte « réduire les animations ».
function useCountUp(value, durationMs = 1400) {
  const [shown, setShown] = useState(0);
  const frame = useRef(0);
  useEffect(() => {
    if (!value) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setShown(value);
      return;
    }
    const start = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - start) / durationMs);
      setShown(Math.round(value * (1 - Math.pow(1 - p, 3))));
      if (p < 1) frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [value, durationMs]);
  return shown;
}

function formatDate(yyyymmdd, lang) {
  if (!yyyymmdd) return null;
  const d = new Date(`${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}T00:00:00`);
  return formatLongDate(d, lang);
}

export default function StatsBanner() {
  const { t, lang } = useI18n();
  const [stats, setStats] = useState(null);
  useEffect(() => { api.stats().then(setStats).catch(() => {}); }, []);
  const persons = useCountUp(stats?.persons);
  const links = useCountUp(stats?.links);
  if (!stats) return null;
  const locale = lang === "en" ? "en-GB" : "fr-FR";
  return (
    <div className="stats-banner fade-in">
      <div className="stat"><strong>{persons.toLocaleString(locale)}</strong><span>{t("stats.persons")}</span></div>
      <div className="stat"><strong>{links.toLocaleString(locale)}</strong><span>{t("stats.links")}</span></div>
      {stats.data_date && (
        <p className="stat-date">{t("stats.dataDate", { date: formatDate(stats.data_date, lang) })}</p>
      )}
    </div>
  );
}
