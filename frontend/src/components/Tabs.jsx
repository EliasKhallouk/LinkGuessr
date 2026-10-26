import { useId, useRef, useState } from "react";

// Onglets. Non contrôlés par défaut ; contrôlés si `active` est fourni (avec `onChange`).
// Motif ARIA « tabs » : flèches gauche/droite (et Début/Fin) pour passer d'un onglet à l'autre.
export default function Tabs({ tabs = [], initial = 0, active: controlled, onChange }) {
  const [internal, setInternal] = useState(initial);
  const active = controlled ?? internal;
  const baseId = useId();
  const buttons = useRef([]);

  const select = (i) => {
    setInternal(i);
    onChange?.(i);
  };

  const onKeyDown = (e) => {
    const last = tabs.length - 1;
    const next = { ArrowRight: active === last ? 0 : active + 1, ArrowLeft: active === 0 ? last : active - 1, Home: 0, End: last }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    select(next);
    buttons.current[next]?.focus();
  };

  return (
    <div className="tabs">
      <div className="tabs-list" role="tablist" onKeyDown={onKeyDown}>
        {tabs.map((t, i) => (
          <button
            key={t.key}
            ref={(el) => { buttons.current[i] = el; }}
            type="button"
            role="tab"
            id={`${baseId}-tab-${t.key}`}
            aria-selected={i === active}
            aria-controls={`${baseId}-panel-${t.key}`}
            tabIndex={i === active ? 0 : -1}
            className={`tab ${i === active ? "active" : ""}`}
            onClick={() => select(i)}
          >
            <span>{t.title}</span>
          </button>
        ))}
      </div>
      {/* Tous les jeux restent montés (cachés) : changer d'onglet ne perd pas la partie en cours. */}
      {tabs.map((t, i) => (
        <div
          key={t.key}
          role="tabpanel"
          id={`${baseId}-panel-${t.key}`}
          aria-labelledby={`${baseId}-tab-${t.key}`}
          className="tabs-panel"
          hidden={i !== active}
        >
          {t.content}
        </div>
      ))}
    </div>
  );
}
