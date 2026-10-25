import { wikiUrl } from "../api";
import PersonChip from "./PersonChip";

// Phrase extraite d'un article Wikipédia (CC BY-SA 4.0) : on renvoie toujours vers l'article d'origine.
export function Snippet({ text, article }) {
  return (
    <span className="snippet">
      <q className="hop-snippet">{text}</q>{" "}
      {article?.title && (
        <a className="snippet-source" href={wikiUrl(article.title)} target="_blank" rel="noreferrer">
          Wikipédia · {article.name}
        </a>
      )}
    </span>
  );
}

// Pourquoi deux personnes sont liées : relation Wikidata en priorité, sinon la phrase de l'article.
function HopExplanation({ hop, from, to }) {
  if (!hop) return null;
  const relations = [...new Map(hop.relations.map((r) => [`${r.label}-${r.context || ""}`, r])).values()];
  const text = [...hop.text].sort((a, b) => (b.in_lead - a.in_lead) || (b.mentions - a.mentions))[0];
  return (
    <div className="hop-explain">
      {relations.slice(0, 1).map((r) => {
        const source = r.source_id === from.id ? from : to;
        const target = source === from ? to : from;
        // « élève de », « influencé par » se lisent depuis la source ; « père », « successeur »… depuis la cible.
        const sourceFirst = / (de|par)$/.test(r.label);
        const context = r.context ? ` (${r.context}${r.start_year ? `, ${r.start_year}` : ""})` : "";
        return (
          <span key={`${r.label}-${r.context}`} className="hop-relation">
            {sourceFirst
              ? <>{source.name} est <strong>{r.label}</strong> {target.name}</>
              : <>{target.name} est <strong>{r.label}</strong> de {source.name}</>}
            {context}
          </span>
        );
      })}
      {text?.snippet && <Snippet text={text.snippet} article={text.source_id === from.id ? from : to} />}
    </div>
  );
}

// Un chemin (liste de QID) avec, entre chaque personne, l'explication du lien.
export default function PathView({ path, persons, hops, hiddenIndex = null }) {
  if (!path?.length) return null;
  return (
    <ol className="path-view">
      {path.map((qid, i) => {
        const person = persons[qid];
        const next = path[i + 1];
        const hopKey = next && (hops[`${qid}-${next}`] ? `${qid}-${next}` : `${next}-${qid}`);
        const showHop = next && i !== hiddenIndex && i + 1 !== hiddenIndex;
        return (
          <li key={`${qid}-${i}`}>
            <PersonChip person={person} hidden={i === hiddenIndex} showDescription />
            {next && (
              <div className="path-link">
                <span className="path-arrow">↓</span>
                {showHop && <HopExplanation hop={hops[hopKey]} from={person} to={persons[next]} />}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
