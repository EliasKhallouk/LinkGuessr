import { useState } from "react";
import { useI18n } from "../i18n/I18nProvider";
import { shareText } from "../lib/share";

// Bouton Partager avec retour visuel (« Copié ! »). `utm` : { source, campaign } ajoutés au lien.
// `onShared` sert à mesurer les partages.
export default function ShareButton({ text, url, utm, onShared, label }) {
  const { t } = useI18n();
  const [status, setStatus] = useState(null);
  const click = async () => {
    const result = await shareText(text, url, utm);
    setStatus(result);
    if (result === "shared" || result === "copied") onShared?.(result);
    setTimeout(() => setStatus(null), 2500);
  };
  return (
    <button type="button" className="btn btn-share" onClick={click}>
      {status === "copied" ? t("share.copied") : status === "failed" ? t("share.failed") : (label || t("share.share"))}
    </button>
  );
}
