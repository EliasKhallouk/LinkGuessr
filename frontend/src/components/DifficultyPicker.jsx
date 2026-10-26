import { useI18n } from "../i18n/I18nProvider";

export const LEVELS = ["facile", "moyen", "difficile", "extreme", "humain"];

// Facile : les 200 personnes les plus connues (tout le monde peut réussir) … « Tu es humain ? » : 60 000 (cf. API LEVELS).
export default function DifficultyPicker({ value, onChange }) {
  const { t } = useI18n();
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={t("difficulty.label")}>
      {LEVELS.map((level) => <option key={level} value={level}>{t(`difficulty.${level}`)}</option>)}
    </select>
  );
}
