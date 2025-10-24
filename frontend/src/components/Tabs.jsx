import { useState } from "react";

export default function Tabs({ tabs = [], initial = 0, onChange }) {
  const [active, setActive] = useState(initial);
  return (
    <div className="tabs">
      <div className="tabs-list">
        {tabs.map((t, i) => (
          <button
            key={t.key}
            className={`tab ripple ${i === active ? "active" : ""}`}
            onClick={() => {
              setActive(i);
              onChange?.(i);
            }}
          >
            <span>{t.title}</span>
          </button>
        ))}
      </div>
      <div className="tabs-panel">
        {tabs[active]?.content}
      </div>
    </div>
  );
}
