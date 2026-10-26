import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, lifespan } from "../api";
import CommonsImg from "./CommonsImg";

// Champ de recherche d'une personne. `value` est un objet personne (ou null) ;
// les suggestions affichent photo + description pour lever les homonymies.
export default function PersonPicker({ id, label, value, onChange, placeholder = "Tapez un nom…", autoFocus }) {
  const [text, setText] = useState(value?.name || "");
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [pending, setPending] = useState(false);
  const [position, setPosition] = useState(null);
  const wrapper = useRef(null);
  const input = useRef(null);
  const list = useRef(null);
  const requestId = useRef(0);

  useEffect(() => { setText(value?.name || ""); }, [value]);

  useEffect(() => {
    const q = text.trim();
    if (!open || q.length < 2 || q === value?.name) {
      setResults([]);
      return;
    }
    const current = ++requestId.current;
    setPending(true);
    const timer = setTimeout(async () => {
      try {
        const found = await api.search(q, 8);
        if (current === requestId.current) {
          setResults(found);
          setActive(0);
        }
      } catch {
        if (current === requestId.current) setResults([]);
      } finally {
        if (current === requestId.current) setPending(false);
      }
    }, 150);
    return () => clearTimeout(timer);
  }, [text, open, value]);

  const visible = open && (results.length > 0 || pending);

  // La liste est affichée au niveau de la page (portail) pour ne pas être coupée par le panneau
  // ni recouverte par les blocs suivants ; on la place sous le champ et on suit le défilement.
  useLayoutEffect(() => {
    if (!visible) return;
    const place = () => {
      const r = input.current?.getBoundingClientRect();
      if (r) setPosition({ top: r.bottom + 6, left: r.left, width: r.width });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [visible]);

  useEffect(() => {
    const close = (e) => {
      const inside = wrapper.current?.contains(e.target) || list.current?.contains(e.target);
      if (!inside) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const choose = (person) => {
    onChange(person);
    setText(person.name);
    setOpen(false);
  };

  const onKeyDown = (e) => {
    if (!results.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((i) => (i + 1) % results.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => (i - 1 + results.length) % results.length); }
    else if (e.key === "Enter" && open) { e.preventDefault(); choose(results[active]); }
    else if (e.key === "Escape") setOpen(false);
  };

  return (
    <div className="person-picker" ref={wrapper}>
      {label && <label className="muted" htmlFor={id}>{label}</label>}
      <input
        ref={input}
        id={id}
        type="text"
        autoComplete="off"
        autoFocus={autoFocus}
        value={text}
        placeholder={placeholder}
        onChange={(e) => { setText(e.target.value); setOpen(true); if (value) onChange(null); }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
      {visible && position && createPortal(
        <ul ref={list} className="ac-list picker-list" role="listbox"
          style={{ position: "fixed", top: position.top, left: position.left, width: position.width, zIndex: 9999 }}>
          {pending && !results.length && <li className="ac-item muted">Recherche…</li>}
          {results.map((p, i) => (
            <li
              key={p.qid}
              role="option"
              aria-selected={i === active}
              className={`ac-item picker-item ${i === active ? "active" : ""}`}
              onMouseDown={(e) => { e.preventDefault(); choose(p); }}
              onMouseEnter={() => setActive(i)}
            >
              {p.image ? <CommonsImg file={p.image} width={32} height={32} loading="lazy" />
                : <span className="person-avatar placeholder" style={{ width: 32, height: 32 }}>{p.name.charAt(0)}</span>}
              <span>
                <strong>{p.name}</strong>
                <span className="person-desc">{[p.description, lifespan(p)].filter(Boolean).join(" · ")}</span>
              </span>
            </li>
          ))}
        </ul>,
        document.body,
      )}
    </div>
  );
}
