// Middleware Vercel : les robots d'aperçu (WhatsApp, Discord, X…) et les moteurs de recherche
// n'exécutent pas le JavaScript. Pour les pages partageables, on insère dans le HTML un titre,
// une description et une image d'aperçu propres à la page.
// Runtime Node.js : le runtime « edge » n'est plus accepté pour les middlewares par Vercel.
import { translations } from "./src/i18n/translations.js";
import { sharedPathQuery } from "./src/lib/share.js";

// Pages fixes : mêmes titres et descriptions que dans l'application (usePageMeta), en français.
const FR = translations.fr;
const STATIC = {
  "/": FR.meta.home,
  "/explorer": { title: FR.games.explore.title, description: FR.games.explore.pitch },
  "/qui-est-cache": { title: FR.games.guesswho.title, description: FR.games.guesswho.pitch },
  "/relier": { title: FR.games.relay.title, description: FR.games.relay.pitch },
  "/combien": { title: FR.games.count.title, description: FR.games.count.pitch },
  "/lab": FR.meta.lab,
  "/a-propos": FR.meta.about,
  "/contact": FR.meta.contact,
  "/politique-de-confidentialite": FR.meta.privacy,
  "/mentions-legales": FR.meta.legal,
};

export const config = {
  runtime: "nodejs",
  matcher: ["/jour/:number", "/defi", "/personne/:qid", "/", "/explorer", "/qui-est-cache", "/relier", "/combien",
    "/lab", "/a-propos", "/contact", "/politique-de-confidentialite", "/mentions-legales"],
};

const API = "https://linkguessr.duckdns.org";
const SITE = "https://linkguessr.com";
const OLD_HOST = "link-guessr.vercel.app";
const UA = `LinkGuessr/1.0 (${SITE})`;

const escape = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

async function api(path) {
  const r = await fetch(`${API}${path}`, { headers: { "User-Agent": UA } });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

// Chemin partagé depuis Explorer (/explorer?de=Q1&a=Q2) : les deux noms et le nombre de liens, pas les
// intermédiaires. Lu via /v1 (cache Vercel, même requête que la page) : un lien ouvert des centaines de fois
// ne sollicite la VM qu'une fois par jour.
async function explorerMeta(url) {
  const [de, a, mode] = ["de", "a", "mode"].map((k) => url.searchParams.get(k));
  const r = await fetch(`${url.origin}/v1${sharedPathQuery(de, a, mode)}`, { headers: { "User-Agent": UA } });
  if (!r.ok) throw new Error(String(r.status));
  const d = await r.json();
  if (d.length === null) throw new Error("aucun chemin");
  const n = `${d.length} ${d.length > 1 ? "liens" : "lien"}`;
  return { title: `${d.persons[de].name} et ${d.persons[a].name} : ${n}. Tu devines lesquels ? · LinkGuessr`,
    description: "Le plus court chemin entre deux personnalités de Wikipédia, lien par lien, avec les phrases qui les relient.",
    image: `/api/og?${new URLSearchParams({ type: "explorer", de, a, ...(mode && { mode }) })}` };
}

async function metaFor(url) {
  const pathname = url.pathname.replace(/\/$/, "") || "/";
  if (pathname === "/explorer" && url.searchParams.get("de") && url.searchParams.get("a")) {
    const shared = await explorerMeta(url).catch(() => null);  // lien périmé : aperçu de la page Explorer
    if (shared) return shared;
  }
  const page = STATIC[pathname];
  if (page) return { title: `${page.title} · LinkGuessr`, description: page.description, image: "/api/og" };
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts[0] === "jour") {
    const d = await api(`/daily/archive/${encodeURIComponent(parts[1])}`);
    const a = d.persons[d.path[0]].name;
    const b = d.persons[d.path[d.path.length - 1]].name;
    return { title: `Défi du jour #${d.number} : qui relie ${a} et ${b} ? · LinkGuessr`,
      description: "Le même défi pour tout le monde, une partie par jour. Devine la personne cachée sur le chemin.",
      image: `/api/og?type=jour&n=${d.number}` };
  }
  if (parts[0] === "defi") {
    const game = url.searchParams.get("jeu");
    const score = Number(url.searchParams.get("score")) || "?";
    if (game === "cache") {
      // Seulement les deux bouts du chemin : la personne cachée ne doit pas apparaître dans l'aperçu.
      const ends = (url.searchParams.get("chemin") || "").split("-");
      const [qa, qb] = [ends[0], ends[ends.length - 1]];
      const [ca, cb] = await Promise.all([api(`/person/${qa}/card`), api(`/person/${qb}/card`)]);
      const tries = Number(url.searchParams.get("essais")) || 0;
      const found = url.searchParams.get("trouve") === "1";
      return { title: `Qui est caché entre ${ca.person.name} et ${cb.person.name} ? · LinkGuessr`,
        description: found ? `Ton ami l'a trouvé en ${tries} ${tries > 1 ? "essais" : "essai"}. Et toi, tu trouves ?`
          : "Ton ami n'a pas trouvé. Tu vas faire mieux ?",
        image: `/api/og?type=cache&chemin=${ends.join("-")}&cache=${Number(url.searchParams.get("cache")) || 1}` };
    }
    if (game === "relais") {
      const [qa, qb] = (url.searchParams.get("paire") || "").split("-");
      const [ca, cb] = await Promise.all([api(`/person/${qa}/card`), api(`/person/${qb}/card`)]);
      return { title: `Défi : relier ${ca.person.name} à ${cb.person.name} en moins de ${score} coups · LinkGuessr`,
        description: `Quelqu'un l'a fait en ${score} ${score === 1 ? "coup" : "coups"}. Saute de personne en personne : tu fais mieux ?`,
        image: `/api/og?type=duel&paire=${qa}-${qb}&score=${score}` };
    }
    return { title: `Défi : bats ${score} points en 60 secondes · LinkGuessr`,
      description: "Estime le nombre de liens entre deux personnalités, le plus vite possible.",
      image: `/api/og?type=nombre&score=${score}` };
  }
  if (parts[0] === "personne") {
    const { person: p, closest } = await api(`/person/${encodeURIComponent(parts[1])}/card`);
    const near = closest.slice(0, 3).map((c) => c.name).join(", ");
    return { title: `${p.name} : ses liens avec ${near}… · LinkGuessr`,
      // Résumé lisible pour les robots qui n'exécutent pas le JavaScript (remplacé par l'application au chargement).
      body: `<main><h1>${escape(p.name)}</h1><p>${escape(p.description || "")}</p>`
        + `<p>${p.degree} liens dans le réseau des personnalités de Wikipédia en français : `
        + `${p.degree_rank}e personne la plus connectée sur ${p.total}.</p>`
        + `<h2>Personnes les plus proches</h2><ul>${closest.map((c) => `<li><a href="/personne/${c.qid}">${escape(c.name)}</a>`
          + `${c.description ? ` — ${escape(c.description)}` : ""}</li>`).join("")}</ul>`
        + "<p>Données : Wikipédia (CC BY-SA 4.0), Wikidata (CC0).</p></main>",
      description: `${p.description ? `${p.description}. ` : ""}${p.degree} liens dans le réseau des personnalités de Wikipédia en français `
        + `(${p.degree_rank}e plus connectée). Données Wikipédia et Wikidata.`,
      image: `/api/og?type=personne&qid=${p.qid}` };
  }
  return null;
}

export default async function middleware(request) {
  const url = new URL(request.url);
  // Ancienne adresse : même redirection que vercel.json (chemin et paramètres conservés), au cas où
  // le middleware passerait avant elle.
  if (url.hostname === OLD_HOST) return Response.redirect(`${SITE}${url.pathname}${url.search}`, 308);
  const page = await fetch(new URL("/index.html", url));
  let html = await page.text();
  try {
    const meta = await metaFor(url);
    if (meta) {
      const image = new URL(meta.image, url).toString();
      const tags = [
        `<meta property="og:title" content="${escape(meta.title)}" />`,
        `<meta property="og:description" content="${escape(meta.description)}" />`,
        `<meta property="og:image" content="${escape(image)}" />`,
        `<meta property="og:url" content="${escape(url.toString())}" />`,
        '<meta property="og:type" content="website" />',
        '<meta property="og:site_name" content="LinkGuessr" />',
        '<meta name="twitter:card" content="summary_large_image" />',
        `<link rel="canonical" href="${escape(url.origin + url.pathname)}" />`,
      ].join("\n    ");
      // index.html porte des balises d'aperçu par défaut (accueil) : on les retire, sinon les robots
      // gardent la première occurrence (titre de l'accueil) et affichent plusieurs images.
      html = html
        .replace(/\s*<meta (?:property="og:[^"]*"|name="twitter:[^"]*")[^>]*>/g, "")
        .replace(/<title>[^<]*<\/title>/, `<title>${escape(meta.title)}</title>`)
        .replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${escape(meta.description)}" />`)
        .replace("</head>", `    ${tags}\n  </head>`);
      if (meta.body) html = html.replace('<div id="root"></div>', `<div id="root">${meta.body}</div>`);
    }
  } catch {
    // Donnée introuvable : on sert la page telle quelle, l'application gère l'erreur.
  }
  return new Response(html, {
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "public, max-age=0, s-maxage=3600" },
  });
}
