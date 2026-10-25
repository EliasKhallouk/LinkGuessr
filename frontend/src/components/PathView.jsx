import { wikiUrl } from "../api";
import PersonChip from "./PersonChip";

// Phrase extraite d'un article Wikipédia (CC BY-SA 4.0) : on renvoie toujours vers l'article d'origine.
// Extrait coupé en pleine phrase : on le termine au dernier mot complet et on marque les coupures.
function tidy(text) {
  let out = text.trim();
  if (!/[.!?…»"')\]]$/.test(out)) out = `${out.replace(/\s+\S*$/, "")} …`;
  if (/^[a-zà-ÿ,;:.)]/.test(out)) out = `… ${out.replace(/^[,;:.)\s]+/, "")}`;
  return out;
}

export function Snippet({ text, article }) {
  return (
    <span className="snippet">
      <q className="hop-snippet">{tidy(text)}</q>{" "}
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

// Sens du lien entre la personne du haut et celle du bas, d'après qui cite qui dans son article.
function linkDirection(hop, upper, lower) {
  if (!hop || !upper || !lower) return { arrow: "—", title: "" };
  const upperCites = hop.text.some((r) => r.source_id === upper.id);
  const lowerCites = hop.text.some((r) => r.source_id === lower.id);
  if (upperCites && lowerCites) return { arrow: "↕", title: `${upper.name} et ${lower.name} se citent mutuellement` };
  if (upperCites) return { arrow: "↓", title: `${upper.name} cite ${lower.name}` };
  if (lowerCites) return { arrow: "↑", title: `${lower.name} cite ${upper.name}` };
  return { arrow: "—", title: "Relation Wikidata" };
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
        const direction = showHop ? linkDirection(hops[hopKey], person, persons[next]) : { arrow: "—", title: "" };
        return (
          <li key={`${qid}-${i}`}>
            <PersonChip person={person} hidden={i === hiddenIndex} showDescription />
            {next && (
              <div className="path-link">
                <span className="path-arrow" title={direction.title} aria-label={direction.title}>{direction.arrow}</span>
                {showHop && <HopExplanation hop={hops[hopKey]} from={person} to={persons[next]} />}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
