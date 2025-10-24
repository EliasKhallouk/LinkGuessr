import { useState } from "react";

export default function Tabs({ tabs = [], initial = 0, onChange }) {
  const [active, setActive] = useState(initial);
  return (
    <div className="tabs">
      <div className="tabs-list">
        {tabs.map((t, i) => (
          <button
            key={t.key}
            className={`tab ${i === active ? "active" : ""}`}
            onClick={() => {
              setActive(i);
              onChange?.(i);
            }}
          >
            {t.title}
          </button>
        ))}
      </div>
      <div className="tabs-panel">
        {tabs[active]?.content}
      </div>
    </div>
  );
}
