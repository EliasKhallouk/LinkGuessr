import { Link } from "react-router-dom";
import { commonsThumb } from "../api";

// Une personne : photo, nom (lien vers sa fiche) et, en option, sa description.
export default function PersonChip({ person, showDescription = false, size = 40, hidden = false }) {
  if (hidden) {
    return (
      <span className="person-chip hidden-person">
        <span className="person-avatar placeholder" style={{ width: size, height: size }}>?</span>
        <span className="person-text"><strong>???</strong></span>
      </span>
    );
  }
  if (!person) return null;
  const thumb = commonsThumb(person.image, size * 2);
  return (
    <span className="person-chip">
      {thumb ? (
        <img className="person-avatar" src={thumb} alt="" width={size} height={size} loading="lazy" />
      ) : (
        <span className="person-avatar placeholder" style={{ width: size, height: size }}>
          {(person.name || "?").charAt(0)}
        </span>
      )}
      <span className="person-text">
        <Link className="chemin-link" to={`/personne/${person.qid}`}>{person.name}</Link>
        {showDescription && person.description && <span className="person-desc">{person.description}</span>}
      </span>
    </span>
  );
}
