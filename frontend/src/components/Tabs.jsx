import { useState } from "react";

// Onglets. Non contrôlés par défaut ; contrôlés si `active` est fourni (avec `onChange`).
export default function Tabs({ tabs = [], initial = 0, active: controlled, onChange }) {
  const [internal, setInternal] = useState(initial);
  const active = controlled ?? internal;
  return (
    <div className="tabs">
      <div className="tabs-list">
        {tabs.map((t, i) => (
          <button
            key={t.key}
            className={`tab ripple ${i === active ? "active" : ""}`}
            onClick={() => {
              setInternal(i);
              onChange?.(i);
            }}
          >
            <span>{t.title}</span>
          </button>
        ))}
      </div>
      {/* Tous les jeux restent montés (cachés) : changer d'onglet ne perd pas la partie en cours. */}
      {tabs.map((t, i) => (
        <div key={t.key} className="tabs-panel" hidden={i !== active}>{t.content}</div>
      ))}
    </div>
  );
}
