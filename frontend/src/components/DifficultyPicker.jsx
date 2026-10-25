import { useI18n } from "../i18n/I18nProvider";

const LEVELS = ["facile", "moyen", "difficile"];

// Facile : parmi les 2 % les plus connus ; moyen : 10 % ; difficile : 40 % (cf. API /random_pair).
export default function DifficultyPicker({ value, onChange }) {
  const { t } = useI18n();
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={t("difficulty.label")}>
      {LEVELS.map((level) => <option key={level} value={level}>{t(`difficulty.${level}`)}</option>)}
    </select>
  );
}
