import { useState } from "react";
import CommonsImg from "./CommonsImg";

// Photo ronde d'une personne ; son initiale si elle n'a pas de photo ou si la photo ne charge pas
// (jamais un cercle vide).
function Photo({ person, size, className }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <Initial person={person} size={size} className={className} />;
  return <CommonsImg className={`person-avatar ${className}`} file={person.image} width={size} height={size}
    loading="lazy" onFail={() => setFailed(true)} />;
}

function Initial({ person, size, className }) {
  return (
    <span className={`person-avatar placeholder ${className}`} style={{ width: size, height: size }} aria-hidden="true">
      {(person.name || "?").charAt(0)}
    </span>
  );
}

export default function Avatar({ person, size = 40, className = "" }) {
  if (!person.image) return <Initial person={person} size={size} className={className} />;
  // Une clé par photo : l'état « échec » d'une personne ne passe jamais à la suivante.
  return <Photo key={person.image} person={person} size={size} className={className} />;
}
