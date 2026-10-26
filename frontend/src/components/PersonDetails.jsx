import { useEffect, useState } from "react";
import { usePageMeta } from "../lib/meta";
import { Link } from "react-router-dom";
import { api, lifespan, wikiUrl } from "../api";
import CommonsImg from "./CommonsImg";
import ImageCredit from "./ImageCredit";
import { Snippet } from "./PathView";
import PersonChip from "./PersonChip";
import { ShowMoreButton, useShowMore } from "./ShowMore";
import { useI18n } from "../i18n/I18nProvider";
import { gamePath } from "../games";

// Propriétés Wikidata affichées dans la fiche, dans cet ordre.
const FACT_SECTIONS = [
  ["P39", "person.positions"], ["P102", "person.parties"], ["P54", "person.teams"], ["P69", "person.education"],
  ["P108", "person.employers"], ["P166", "person.awards"], ["P800", "person.works"], ["P463", "person.memberOf"],
];

function years(f) {
  if (!f.start_year && !f.end_year) return "";
  if (f.start_year === f.end_year) return ` (${f.start_year})`;
  return ` (${f.start_year ?? "?"}–${f.end_year ?? ""})`;
}

// Une rubrique Wikidata (fonctions, distinctions…) : 10 éléments, puis « Voir plus ».
function FactSection({ title, items, resetKey }) {
  const shown = useShowMore(items, resetKey);
  if (!items.length) return null;
  return (
    <section className="panel" style={{ marginTop: 12 }}>
      <div className="panel-header"><span className="panel-title">{title}</span></div>
      <div className="panel-body">
        <ul className="fact-list">
          {shown.visible.map((f, i) => <li key={`${f.value_qid}-${i}`}>{f.label}{years(f)}</li>)}
        </ul>
        <ShowMoreButton list={shown} />
      </div>
    </section>
  );
}

// Contenu d'une fiche personne : affiché dans la page /personne/:qid et dans le panneau latéral des jeux.
export default function PersonDetails({ qid }) {
  const { t } = useI18n();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [card, setCard] = useState(null);
  const relationList = data ? [...new Map(data.relations.map((r) => [`${r.qid}-${r.relation}`, r])).values()] : [];
  const closest = useShowMore(card?.closest ?? [], qid);
  const relationsShown = useShowMore(relationList, qid);
  const citesShown = useShowMore(data?.cites ?? [], qid);
  const citedByShown = useShowMore(data?.cited_by ?? [], qid);

  useEffect(() => {
    setData(null);
    setCard(null);
    setError(null);
    api.person(qid).then(setData).catch((e) => setError(e.message));
    api.personCard(qid).then(setCard).catch(() => {});
  }, [qid]);

  // Titre d'onglet propre à la fiche (les robots reçoivent le même via le middleware Vercel).
  const name = data?.person.name;
  usePageMeta(name, name && [data.person.description, t("meta.person", { name })].filter(Boolean).join(". "));

  if (error) return <div className="error-box"><p style={{ margin: 0 }}>{error}</p></div>;
  if (!data) return <p className="muted">{t("guess.loadingPeople")}</p>;

  const { person: p, labels, facts, relations, cites, cited_by: citedBy } = data;
  const label = (q) => labels[q] || q;
  // Accord de « né à » / « née à » d'après Wikidata ; « né(e) » si le genre est inconnu.
  const genderSuffix = p.gender === "femme" ? "Female" : p.gender === "homme" ? "Male" : "";
  const place = (placeQid, countryQid) => [placeQid && label(placeQid), countryQid && countryQid !== placeQid && label(countryQid)]
    .filter(Boolean).join(", ");

  return (
    <div className="person-page fade-in">
      <section className="panel">
        <div className="panel-body person-header">
          {p.image && (
            <figure className="person-figure">
              <CommonsImg file={p.image} width={250} alt={p.name} className="person-portrait" />
              <ImageCredit file={p.image} />
            </figure>
          )}
          <div>
            <h2 style={{ margin: 0 }}>{p.name}</h2>
            {p.description && <p className="muted" style={{ marginTop: 4 }}>{p.description}</p>}
            <p style={{ marginTop: 8 }}>
              {lifespan(p)}
              {p.birth_place && <> · {t(`person.bornIn${genderSuffix}`)} {place(p.birth_place, p.birth_country)}</>}
              {p.death_place && <> · {t(`person.diedIn${genderSuffix}`)} {place(p.death_place, p.death_country)}</>}
            </p>
            {p.occupations?.length > 0 && <p className="muted">{p.occupations.slice(0, 6).map(label).join(" · ")}</p>}
            <div className="toolbar" style={{ marginTop: 8 }}>
              {p.domains?.map((d) => <span key={d} className="tag">{d}</span>)}
              <span className="kpi">{p.degree?.toLocaleString()} {t("who.links")}</span>
              {p.pageviews_12m != null && <span className="kpi">{p.pageviews_12m.toLocaleString()} {t("person.views")}</span>}
              <span className="kpi">{t("person.wikipedias", { n: p.sitelinks })}</span>
            </div>
            <div className="toolbar" style={{ marginTop: 8 }}>
              <a className="btn" href={wikiUrl(p.title)} target="_blank" rel="noreferrer">Wikipédia</a>
              <Link className="btn" to={`${gamePath("explore")}?from=${p.qid}`}>{t("person.findPath")}</Link>
            </div>
          </div>
        </div>
        {p.lead && <div className="panel-body"><Snippet text={p.lead} article={p} /></div>}
      </section>

      {card && (
        <section className="panel" style={{ marginTop: 12 }}>
          <div className="panel-header"><span className="panel-title">{t("person.network")}</span></div>
          <div className="panel-body">
            <p style={{ marginTop: 0 }}>
              {t("person.rank", { count: card.person.degree_rank, rank: card.person.degree_rank.toLocaleString(), total: card.person.total.toLocaleString(),
                links: card.person.degree.toLocaleString() })}
            </p>
            {card.closest.length > 0 && (
              <>
                <p className="muted">{t("person.closest")}</p>
                <ul className="fact-list">
                  {closest.visible.map((c) => <li key={c.qid}><PersonChip person={c} size={28} showDescription /></li>)}
                </ul>
                <ShowMoreButton list={closest} />
              </>
            )}
          </div>
        </section>
      )}

      {relations.length > 0 && (
        <section className="panel" style={{ marginTop: 12 }}>
          <div className="panel-header"><span className="panel-title">{t("person.relations")}</span></div>
          <div className="panel-body">
            <ul className="fact-list">
              {relationsShown.visible.map((r) => (
                <li key={`${r.qid}-${r.relation}`}>
                  <span className="muted">{r.relation}{r.context ? ` (${r.context})` : ""}</span>
                  <PersonChip person={r} size={28} />
                </li>
              ))}
            </ul>
            <ShowMoreButton list={relationsShown} />
          </div>
        </section>
      )}

      {FACT_SECTIONS.map(([prop, key]) => (
        <FactSection key={prop} title={t(key)} items={facts.filter((f) => f.prop === prop && f.label).slice(0, 30)} resetKey={qid} />
      ))}

      {cites.length > 0 && (
        <section className="panel" style={{ marginTop: 12 }}>
          <div className="panel-header"><span className="panel-title">{t("person.cites", { name: p.name })}</span></div>
          <div className="panel-body">
            <ul className="link-list">
              {citesShown.visible.map((c) => (
                <li key={c.qid}>
                  <PersonChip person={c} size={28} />
                  {c.snippet && <Snippet text={c.snippet} article={p} />}
                </li>
              ))}
            </ul>
            <ShowMoreButton list={citesShown} />
          </div>
        </section>
      )}

      {citedBy.length > 0 && (
        <section className="panel" style={{ marginTop: 12 }}>
          <div className="panel-header"><span className="panel-title">{t("person.citedBy", { name: p.name })}</span></div>
          <div className="panel-body">
            <ul className="link-list">
              {citedByShown.visible.map((c) => (
                <li key={c.qid}>
                  <PersonChip person={c} size={28} />
                  {c.snippet && <Snippet text={c.snippet} article={c} />}
                </li>
              ))}
            </ul>
            <ShowMoreButton list={citedByShown} />
          </div>
        </section>
      )}
    </div>
  );
}
