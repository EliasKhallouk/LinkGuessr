import { useEffect, useMemo, useRef, useState } from "react";
import { apiUrl } from "../config";
import { useI18n } from "../i18n/I18nProvider";
import Autocomplete from "./Autocomplete";

export default function GuessWhoPath() {
  const { t } = useI18n();
  const [path, setPath] = useState([]); // array of labels
  const [maskedIndex, setMaskedIndex] = useState(null);
  const [answer, setAnswer] = useState(null); // correct DB label
  const [guess, setGuess] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null); // { correct: boolean }
  const [hints, setHints] = useState({ tries: 0, showLen: false, showFirstLen: false, showCategory: false, categories: [] });
  const inputRef = useRef(null);

  const formatNode = (label) =>
    (label || "")
      .toString()
      .replaceAll("_", " ");

  const maskedPath = useMemo(() => {
    if (!Array.isArray(path) || maskedIndex == null) return [];
    return path.map((node, idx) => (idx === maskedIndex ? "?" : formatNode(node)));
  }, [path, maskedIndex]);

  const fetchChallenge = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setGuess("");
    try {
      const res = await fetch(apiUrl("/random_path?min_edges=2"));
      const data = await res.json();
      if (!data || !Array.isArray(data.chemin) || data.chemin.length < 3 || data.masked_index == null) {
        throw new Error("bad-challenge");
      }
  setPath(data.chemin);
  setMaskedIndex(data.masked_index);
  setAnswer(data.answer);
  setHints({ tries: 0, showLen: false, showFirstLen: false, showCategory: false, categories: Array.isArray(data.categories) ? data.categories : [] });
      // Focus the input for quick typing
      requestAnimationFrame(() => inputRef.current?.focus());
    } catch (e) {
      setError(t("guess.errorLoadPeople"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchChallenge(); }, []);

  // Server-backed search for suggestions
  const queryPeople = async (q) => {
    const qs = (q || "").trim();
    if (!qs) return [];
    try {
      const res = await fetch(apiUrl(`/search_people?q=${encodeURIComponent(qs)}&limit=8`));
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data.results) ? data.results : [];
    } catch {
      return [];
    }
  };

  const handleValidate = () => {
    if (!answer) return;
    const ok = (guess || "").trim().toLowerCase() === answer.toLowerCase();
    setResult({ correct: ok });
    if (!ok) {
      setHints((h) => {
        const next = { ...h, tries: h.tries + 1 };
        if (next.tries >= 1) next.showLen = true;         // 1ère erreur: longueur du nom complet
        if (next.tries >= 2) next.showFirstLen = true;    // 2ème erreur: longueur du prénom
        if (next.tries >= 3) next.showCategory = true;    // 3ème erreur: catégorie générale
        return next;
      });
    }
  };

  return (
    <section className="panel fade-in">
      <div className="panel-header">
        <span className="panel-title">Devine la personne cachée</span>
        <div>
          <button className="btn" onClick={fetchChallenge} disabled={loading}>{t("guess.newChallenge")}</button>
        </div>
      </div>
      <div className="panel-body">
        {(!path || path.length === 0) ? (
          <p className="muted" style={{ margin: 0 }}>{t("guess.loadingPeople")}</p>
        ) : (
          <>
            <p className="muted" style={{ marginTop: 0 }}>{t("game.path")}</p>
            <p>
              {path.map((node, idx) => (
                <span key={`${node}-${idx}`} style={{ fontWeight: idx === maskedIndex ? 700 : 400 }}>
                  {idx === maskedIndex ? (
                    <span>?</span>
                  ) : (
                    <a
                      href={`https://fr.wikipedia.org/wiki/${encodeURIComponent(node)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="chemin-link"
                    >
                      {formatNode(node)}
                    </a>
                  )}
                  {idx < path.length - 1 ? " → " : ""}
                </span>
              ))}
            </p>

            <div className="row" style={{ alignItems: "end" }}>
              <div>
                <label htmlFor="guess-hidden" className="muted">Qui est la personne cachée ?</label>
                <Autocomplete
                  id="guess-hidden"
                  value={guess}
                  onChange={setGuess}
                  placeholder={t("game.typeName")}
                  options={[]}
                  onQuery={queryPeople}
                  useRawOnSelect
                />
              </div>
              <div>
                <button className="btn" onClick={handleValidate}>{t("guess.verify")}</button>
              </div>
            </div>

            {result && (
              <div className="panel" style={{ marginTop: 12, borderRadius: 12 }}>
                <div className="panel-body">
                  {result.correct ? (
                    <p style={{ margin: 0, fontWeight: 600, color: "var(--success)" }}>{t("guess.good")}</p>
                  ) : (
                    <p style={{ margin: 0, fontWeight: 600, color: "var(--danger)" }}>{t("guess.bad")}</p>
                  )}
                  {!result.correct && (
                    <div className="muted" style={{ marginTop: 8, lineHeight: 1.6 }}>
                      {hints.showLen && answer && (
                        <p style={{ margin: 0 }}>Indice: longueur du nom complet = <strong>{formatNode(answer).length}</strong> caractères</p>
                      )}
                      {hints.showFirstLen && answer && (
                        <p style={{ margin: 0 }}>Indice: longueur du prénom = <strong>{formatNode(answer).split(" ")[0]?.length || 0}</strong> caractères</p>
                      )}
                      {hints.showCategory && hints.categories && hints.categories.length > 0 && (
                        <p style={{ margin: 0 }}>Indice: catégorie = <strong>{hints.categories.join(", ")}</strong></p>
                      )}
                    </div>
                  )}
                  {!result.correct && answer && hints.tries >= 4 && (
                    <p className="muted" style={{ marginTop: 6 }}>
                      Réponse: <strong>{formatNode(answer)}</strong>
                    </p>
                  )}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
