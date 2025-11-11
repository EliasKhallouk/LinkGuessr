import Fuse from 'fuse.js';
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from 'react-dom';

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
    // Use remoteOptions when available, otherwise local options
    const source = Array.isArray(remoteOptions) ? remoteOptions : options;
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
    if (!q) return source.slice(0, 8);
    const tokens = q.split(' ');
    const filtered = source
      .filter((o) => {
        const cand = strip(o);
        // split candidate into words for per-word prefix checks
        const candWords = (cand || '').split(/\s+/).filter(Boolean);
        // Every token from the query must match somewhere in the candidate
        return tokens.every((tok) => {
          if (!tok) return true;
          // direct substring match
          if (cand.includes(tok)) return true;
          // or token matches the start of any candidate word (prefix match)
          return candWords.some((w) => w.startsWith(tok));
        });
      })
      .slice(0, 8);

    // If no strict matches, try a fuzzy search with Fuse.js as a fallback
    if (filtered.length === 0 && source.length > 0 && q.length >= 2) {
      try {
        const fuse = new Fuse(source, {
          includeScore: true,
          threshold: 0.4,
          ignoreLocation: true,
          minMatchCharLength: 2,
        });
        const fuzzy = fuse.search(q).slice(0, 8).map(r => r.item);
        return fuzzy;
      } catch (e) {
        return source.slice(0, 8);
      }
    }

    return filtered;
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

  // Portal positioning: compute a fixed-positioned box below the input so dropdown
  // can escape parent overflow:hidden containers.
  const [portalStyle, setPortalStyle] = useState(null);
  useEffect(() => {
    if (!open || suggestions.length === 0) {
      setPortalStyle(null);
      return;
    }
    const compute = () => {
      const inp = inputRef.current;
      if (!inp) return setPortalStyle(null);
      const r = inp.getBoundingClientRect();
      const top = r.bottom + window.scrollY + 8; // 8px gap
      const left = r.left + window.scrollX;
      const width = r.width;
      setPortalStyle({ position: 'absolute', top: `${top}px`, left: `${left}px`, width: `${width}px`, zIndex: 9999, maxHeight: '280px', overflow: 'auto' });
    };
    compute();
    window.addEventListener('resize', compute);
    window.addEventListener('scroll', compute, true);
    return () => { window.removeEventListener('resize', compute); window.removeEventListener('scroll', compute, true); };
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
      {open && suggestions.length > 0 && portalStyle && createPortal(
        <ul className="ac-list" role="listbox" id={listId} style={portalStyle}>
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
        </ul>,
        document.body
      )}
      {open && pending && (
        <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>{"Recherche..."}</div>
      )}
    </div>
  );
}
