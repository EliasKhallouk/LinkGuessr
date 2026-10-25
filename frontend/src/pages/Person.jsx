import { useNavigate, useParams } from "react-router-dom";
import PersonDetails from "../components/PersonDetails";
import { useI18n } from "../i18n/I18nProvider";

// Page seule d'une fiche (lien partagé). Depuis les jeux, la fiche s'ouvre plutôt dans un panneau.
export default function Person() {
  const { qid } = useParams();
  const { t } = useI18n();
  const navigate = useNavigate();
  // Revenir là d'où l'on vient si possible, sinon à l'accueil (lien ouvert directement).
  const back = () => (window.history.state?.idx > 0 ? navigate(-1) : navigate("/"));
  return (
    <main className="page">
      <button className="btn back-btn" onClick={back}>{t("person.back")}</button>
      <PersonDetails qid={qid} />
    </main>
  );
}
