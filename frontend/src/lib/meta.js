import { useEffect } from "react";

// Titre d'onglet « Titre de la page · LinkGuessr » et meta description propres à chaque page.
// À la sortie de la page (ou à la fermeture d'une fiche ouverte en panneau), on remet ceux d'avant.
// Les robots qui n'exécutent pas le JavaScript reçoivent les mêmes via middleware.js.
export function usePageMeta(title, description) {
  useEffect(() => {
    if (!title) return undefined;
    const tag = document.querySelector('meta[name="description"]');
    const previous = { title: document.title, description: tag?.getAttribute("content") };
    document.title = `${title} · LinkGuessr`;
    if (tag && description) tag.setAttribute("content", description);
    return () => {
      document.title = previous.title;
      if (tag && previous.description) tag.setAttribute("content", previous.description);
    };
  }, [title, description]);
}
