import { useState } from "react";
import { api } from "../api";
import { useI18n } from "../i18n/I18nProvider";
import { markFeedbackAsked, shouldAskFeedback, source } from "../lib/tracking";

// Une question en fin de partie (au plus une fois par jeu et par jour) : 👍/👎 + commentaire facultatif.
export default function Feedback({ game }) {
  const { t } = useI18n();
  const [visible] = useState(() => shouldAskFeedback(game));
  const [rating, setRating] = useState(null);
  const [comment, setComment] = useState("");
  const [sent, setSent] = useState(false);

  if (!visible) return null;
  if (sent) return <p className="muted" style={{ marginTop: 8 }}>{t("feedback.thanks")}</p>;

  const send = async (value, text = "") => {
    markFeedbackAsked(game);
    setSent(true);
    try {
      await api.feedback({ game, rating: value, comment: text || null, src: source() });
    } catch { /* un retour perdu n'est pas grave */ }
  };

  return (
    <div className="feedback">
      <span>{t("feedback.question")}</span>
      {rating === null ? (
        <div className="toolbar">
          <button type="button" className="btn btn-ghost" onClick={() => setRating(1)} aria-label="👍">👍</button>
          <button type="button" className="btn btn-ghost" onClick={() => setRating(-1)} aria-label="👎">👎</button>
        </div>
      ) : (
        <form className="toolbar" onSubmit={(e) => { e.preventDefault(); send(rating, comment.trim()); }}>
          <input type="text" maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)}
            placeholder={rating > 0 ? t("feedback.likePlaceholder") : t("feedback.dislikePlaceholder")} />
          <button type="submit" className="btn">{t("feedback.send")}</button>
        </form>
      )}
    </div>
  );
}
