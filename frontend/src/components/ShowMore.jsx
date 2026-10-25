import { useEffect, useState } from "react";
import { useI18n } from "../i18n/I18nProvider";

const STEP = 10;

// Affiche les `step` premiers éléments, puis `step` de plus à chaque « Voir plus ».
// `resetKey` : quand il change (autre personne, autre filtre…), on revient aux premiers éléments.
export function useShowMore(items, resetKey, step = STEP) {
  const [limit, setLimit] = useState(step);
  useEffect(() => { setLimit(step); }, [resetKey, step]);
  return {
    visible: items.slice(0, limit),
    hasMore: items.length > limit,
    more: () => setLimit((n) => n + step),
  };
}

export function ShowMoreButton({ list }) {
  const { t } = useI18n();
  if (!list.hasMore) return null;
  return <button type="button" className="btn btn-more" onClick={list.more}>{t("common.showMore")}</button>;
}
