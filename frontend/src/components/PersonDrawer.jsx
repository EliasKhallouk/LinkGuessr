import { useEffect } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import PersonDetails from "./PersonDetails";

// Fiche personne en panneau latéral, par-dessus les jeux (qui restent affichés et gardent leur état).
// L'ouverture est portée par l'URL (?personne=Q…) : le bouton Retour du navigateur fonctionne,
// et on garde dans l'historique le nombre de fiches ouvertes pour tout refermer d'un coup.
export default function PersonDrawer() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const qid = params.get("personne");

  const close = () => {
    const depth = location.state?.drawerDepth || 0;
    if (depth > 0) {
      navigate(-depth);
    } else {
      const next = new URLSearchParams(params);
      next.delete("personne");
      navigate({ search: next.toString() }, { replace: true });
    }
  };

  useEffect(() => {
    if (!qid) return;
    const onKey = (e) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", onKey);
    document.body.classList.add("drawer-open");
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.classList.remove("drawer-open");
    };
  });

  if (!qid) return null;
  return (
    <div className="drawer-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={t("person.title")}>
        <div className="drawer-header">
          <button className="btn back-btn" onClick={close}>{t("person.backToGame")}</button>
        </div>
        <div className="drawer-body">
          <PersonDetails key={qid} qid={qid} />
        </div>
      </aside>
    </div>
  );
}
