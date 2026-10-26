import { useEffect, useState } from "react";
import { commonsDirect, commonsFilePath } from "../lib/commons";

// Photo Wikimedia Commons : miniature directe (un seul aller-retour), et Special:FilePath en repli
// si cette miniature n'existe pas (image d'origine plus petite que la largeur demandée…).
// `width` : largeur affichée en pixels CSS ; on demande le double pour les écrans haute densité.
// `onFail` : appelé si le repli échoue aussi (l'appelant affiche autre chose qu'une image cassée).
export default function CommonsImg({ file, width, alt = "", onFail, ...props }) {
  const [src, setSrc] = useState(() => commonsDirect(file, width * 2));
  useEffect(() => { setSrc(commonsDirect(file, width * 2)); }, [file, width]);
  const fallback = () => {
    if (src.startsWith("https://upload.")) setSrc(commonsFilePath(file, width * 2));
    else onFail?.();
  };
  return <img src={src} alt={alt} width={width} onError={fallback} {...props} />;
}
