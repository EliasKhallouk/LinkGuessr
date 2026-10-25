import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { translations } from "./translations";

const I18nContext = createContext({ t: (k, p) => k, lang: "fr", setLang: () => {} });

function format(template, params) {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, key) => (params[key] ?? `{${key}}`));
}

export function I18nProvider({ children, defaultLang = "fr" }) {
  const [lang, setLang] = useState(() => {
    try {
      const saved = localStorage.getItem("lang");
      if (saved && (saved === "fr" || saved === "en")) return saved;
    } catch {}
    return defaultLang;
  });

  useEffect(() => {
    try { localStorage.setItem("lang", lang); } catch {}
  }, [lang]);

  const t = useMemo(() => {
    const dict = translations[lang] || translations.fr;
    const plural = new Intl.PluralRules(lang === "en" ? "en" : "fr");
    const fn = (key, params) => {
      const parts = key.split(".");
      let node = dict;
      for (const p of parts) node = node?.[p];
      // Accord : { one, other } choisi d'après params.count (sinon params.n) ; en français, 0 et 1 sont au singulier.
      if (node && typeof node === "object" && "other" in node) {
        const count = Number(params?.count ?? params?.n);
        node = node[plural.select(Number.isFinite(count) ? count : 2)] ?? node.other;
      }
      const val = typeof node === "string" ? node : key;
      return format(val, params);
    };
    return fn;
  }, [lang]);

  const value = useMemo(() => ({ t, lang, setLang }), [t, lang, setLang]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
