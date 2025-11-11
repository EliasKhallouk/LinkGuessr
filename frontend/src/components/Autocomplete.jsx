import { useEffect, useMemo, useRef, useState } from "react";

export default function Autocomplete({
  options = [],
  value,
  onChange,
  placeholder = "",
  id,
  label,
  onQuery, // optional async(query) -> Promise<string[]> to override suggestions
  useRawOnSelect = false, // when true, write back the raw option value instead of prettified display
}) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [remoteOptions, setRemoteOptions] = useState(null); // null=use local options; array=server suggestions
  const [pending, setPending] = useState(false);
  const inputRef = useRef(null);
  const listId = id ? `${id}-listbox` : undefined;

  const suggestions = useMemo(() => {
    if (Array.isArray(remoteOptions)) {
      return remoteOptions.slice(0, 8);
    }
    // normalize: lower, remove diacritics, replace ligatures, remove punctuation, collapse spaces
    const strip = (s) => {
      const str = (s || "").toString();
      // Replace common ligatures first
      const lig = str.replace(/œ/g, "oe").replace(/æ/g, "ae");
      // Remove diacritics via NFKD
      const noDia = lig.normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
      // Normalize separators and keep only a-z0-9 and spaces
      return noDia
        .toLowerCase()
        .replace(/[_-]+/g, ' ')
        .replace(/[^a-z0-9 ]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    };

    const q = strip(value);
    if (!q) return options.slice(0, 8);
    const tokens = q.split(' ');

    return options
      .filter((o) => {
        const cand = strip(o);
        // Every token from the query must appear somewhere in the candidate
        return tokens.every((tok) => cand.includes(tok));
      })
      .slice(0, 8);
  }, [options, value, remoteOptions]);

  const formatNode = (label) =>
    (label || "")
      .toString()
      .replaceAll("_", " ")
      //.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());

  useEffect(() => {
    if (open && suggestions.length === 0) {
      setActiveIndex(-1);
    } else if (open && suggestions.length > 0) {
      setActiveIndex(0);
    }
  }, [open, suggestions.length]);

  const handleInputChange = (e) => {
    const v = e.target.value;
    onChange?.(v);
    setOpen(true);
    // If server-backed search is provided, debounce and fetch
    if (onQuery) {
      setPending(true);
      // small debounce
      clearTimeout(handleInputChange._t);
      handleInputChange._t = setTimeout(async () => {
        try {
          const res = await onQuery(v);
          if (Array.isArray(res)) setRemoteOptions(res);
          else setRemoteOptions([]);
        } catch {
          setRemoteOptions([]);
        } finally {
          setPending(false);
        }
      }, 150);
    } else {
      setRemoteOptions(null);
    }
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
          const chosen = suggestions[activeIndex];
          onChange?.(useRawOnSelect ? chosen : formatNode(chosen));
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
    onChange?.(useRawOnSelect ? option : formatNode(option));
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
        value={useRawOnSelect ? formatNode(value) : value}
        onChange={handleInputChange}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
  aria-autocomplete="list"
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
              {formatNode(opt)}
            </li>
          ))}
        </ul>
      )}
      {open && pending && (
        <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{"Recherche..."}</div>
      )}
    </div>
  );
}
