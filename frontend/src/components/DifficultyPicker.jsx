import { useI18n } from "../i18n/I18nProvider";

const LEVELS = ["facile", "moyen", "difficile"];

// Facile : parmi les 0,15 % les plus connus ; moyen : 1 % ; difficile : 5 % (cf. API DIFFICULTY_TOP).
export default function DifficultyPicker({ value, onChange }) {
  const { t } = useI18n();
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={t("difficulty.label")}>
      {LEVELS.map((level) => <option key={level} value={level}>{t(`difficulty.${level}`)}</option>)}
    </select>
  );
}
