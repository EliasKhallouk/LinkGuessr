import { useEffect, useState } from "react";
import { commonsDirect, commonsFilePath } from "../lib/commons";

// Photo Wikimedia Commons : miniature directe (un seul aller-retour), et Special:FilePath en repli
// si cette miniature n'existe pas (image d'origine plus petite que la largeur demandée…).
// `width` : largeur affichée en pixels CSS ; on demande le double pour les écrans haute densité.
export default function CommonsImg({ file, width, alt = "", ...props }) {
  const [src, setSrc] = useState(() => commonsDirect(file, width * 2));
  useEffect(() => { setSrc(commonsDirect(file, width * 2)); }, [file, width]);
  const fallback = () => setSrc((s) => (s.startsWith("https://upload.") ? commonsFilePath(file, width * 2) : s));
  return <img src={src} alt={alt} width={width} onError={fallback} {...props} />;
}
