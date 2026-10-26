import { useEffect, useRef } from "react";
import { useI18n } from "../i18n/I18nProvider";

// Fenêtre modale sur <dialog> : focus piégé, Échap et retour du focus gérés par le navigateur.
// Un clic sur le voile (hors de la boîte) ferme aussi.
export default function Modal({ open, onClose, title, children }) {
  const { t } = useI18n();
  const dialog = useRef(null);

  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={dialog}
      className="modal"
      aria-labelledby="modal-title"
      onClose={onClose}
      onClick={(e) => { if (e.target === dialog.current) onClose(); }}
    >
      <div className="modal-box">
        <div className="modal-header">
          <h2 id="modal-title" className="modal-title">{title}</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label={t("common.close")}>✕</button>
        </div>
        <div className="modal-body">{open && children}</div>
      </div>
    </dialog>
  );
}
