import { useEffect, useMemo, useRef, useState } from "react";

export default function Autocomplete({
  options = [],
  value,
  onChange,
  placeholder = "",
  id,
  label,
}) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef(null);
  const listId = id ? `${id}-listbox` : undefined;

  const suggestions = useMemo(() => {
    const q = (value || "").toLowerCase().trim();
    if (!q) return options.slice(0, 8);
    return options
      .filter((o) => o.toLowerCase().includes(q))
      .slice(0, 8);
  }, [options, value]);

  useEffect(() => {
    if (open && suggestions.length === 0) {
      setActiveIndex(-1);
    } else if (open && suggestions.length > 0) {
      setActiveIndex(0);
    }
  }, [open, suggestions.length]);

  const handleInputChange = (e) => {
    onChange?.(e.target.value);
    setOpen(true);
  };

  const handleKeyDown = (e) => {
    if (!open && ["ArrowDown", "ArrowUp"].includes(e.key)) {
      setOpen(true);
      return;
    }
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((i) => (suggestions.length ? (i + 1) % suggestions.length : -1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((i) => (suggestions.length ? (i - 1 + suggestions.length) % suggestions.length : -1));
        break;
      case "Enter":
        if (open && activeIndex >= 0 && suggestions[activeIndex]) {
          e.preventDefault();
          onChange?.(suggestions[activeIndex]);
          setOpen(false);
        }
        break;
      case "Escape":
        setOpen(false);
        break;
      default:
        break;
    }
  };

  const handleSelect = (option) => {
    onChange?.(option);
    setOpen(false);
    // focus back to input for continuity
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  // close on outside click
  useEffect(() => {
    const onDocClick = (e) => {
      if (!inputRef.current) return;
      const wrapper = inputRef.current.closest(".autocomplete");
      if (wrapper && !wrapper.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  return (
    <div className="autocomplete">
      {label && <label className="muted" htmlFor={id}>{label}</label>}
      <input
        id={id}
        ref={inputRef}
        type="text"
        value={value}
        onChange={handleInputChange}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={activeIndex >= 0 ? `${listId}-item-${activeIndex}` : undefined}
        // reuse global input styles
        className="ac-input"
      />
      {open && suggestions.length > 0 && (
        <ul className="ac-list" role="listbox" id={listId}>
          {suggestions.map((opt, idx) => (
            <li
              key={opt}
              id={`${listId}-item-${idx}`}
              role="option"
              aria-selected={idx === activeIndex}
              className={`ac-item ${idx === activeIndex ? "active" : ""}`}
              onMouseDown={(e) => {
                e.preventDefault();
                handleSelect(opt);
              }}
              onMouseEnter={() => setActiveIndex(idx)}
            >
              {opt}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
