import { Link, useLocation, useSearchParams } from "react-router-dom";
import Avatar from "./Avatar";

// Lien vers une fiche : ouvre le panneau latéral sans quitter la page (jeux, duels, défis) ;
// sur une page /personne, mène à la page de l'autre personne.
function usePersonLink(qid) {
  const location = useLocation();
  const [params] = useSearchParams();
  if (location.pathname.startsWith("/personne/")) return { to: `/personne/${qid}` };
  const next = new URLSearchParams(params);
  next.set("personne", qid);
  return { to: { search: next.toString() }, state: { drawerDepth: (location.state?.drawerDepth || 0) + 1 } };
}

// Une personne : photo, nom (lien vers sa fiche) et, en option, sa description.
export default function PersonChip({ person, showDescription = false, size = 40, hidden = false }) {
  const link = usePersonLink(person?.qid);
  if (hidden) {
    return (
      <span className="person-chip hidden-person">
        <span className="person-avatar placeholder" style={{ width: size, height: size }}>?</span>
        <span className="person-text"><strong>???</strong></span>
      </span>
    );
  }
  if (!person) return null;
  return (
    <span className="person-chip">
      <Avatar person={person} size={size} />
      <span className="person-text">
        <Link className="chemin-link" to={link.to} state={link.state}>{person.name}</Link>
        {showDescription && person.description && <span className="person-desc">{person.description}</span>}
      </span>
    </span>
  );
}
