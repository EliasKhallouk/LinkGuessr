// Middleware Vercel : les robots d'aperçu (WhatsApp, Discord, X…) et les moteurs de recherche
// n'exécutent pas le JavaScript. Pour les pages partageables, on insère dans le HTML un titre,
// une description et une image d'aperçu propres à la page.
export const config = { matcher: ["/jour/:number", "/defi", "/personne/:qid"] };

const API = "https://linkguessr.duckdns.org";
const UA = "LinkGuessr/1.0 (https://link-guessr.vercel.app)";

const escape = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

async function api(path) {
  const r = await fetch(`${API}${path}`, { headers: { "User-Agent": UA } });
  if (!r.ok) throw new Error(String(r.status));
  return r.json();
}

async function metaFor(url) {
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts[0] === "jour") {
    const d = await api(`/daily/archive/${encodeURIComponent(parts[1])}`);
    const a = d.persons[d.path[0]].name;
    const b = d.persons[d.path[d.path.length - 1]].name;
    return { title: `Défi du jour #${d.number} : qui relie ${a} et ${b} ? · LinkGuessr`,
      description: "Le même défi pour tout le monde, une tentative par jour. Devine la personne cachée sur le chemin.",
      image: `/api/og?type=jour&n=${d.number}` };
  }
  if (parts[0] === "defi") {
    const game = url.searchParams.get("jeu");
    const score = Number(url.searchParams.get("score")) || "?";
    if (game === "relais") {
      const [qa, qb] = (url.searchParams.get("paire") || "").split("-");
      const [ca, cb] = await Promise.all([api(`/person/${qa}/card`), api(`/person/${qb}/card`)]);
      return { title: `Défi : relier ${ca.person.name} à ${cb.person.name} en moins de ${score} coups · LinkGuessr`,
        description: `Quelqu'un l'a fait en ${score} coup(s). Saute de personne en personne : tu fais mieux ?`,
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
      description: `${p.description ? `${p.description}. ` : ""}${p.degree} liens dans le réseau des personnalités de Wikipédia en français `
        + `(${p.degree_rank}e plus connectée). Données Wikipédia et Wikidata.`,
      image: `/api/og?type=personne&qid=${p.qid}` };
  }
  return null;
}

export default async function middleware(request) {
  const url = new URL(request.url);
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
      html = html
        .replace(/<title>[^<]*<\/title>/, `<title>${escape(meta.title)}</title>`)
        .replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${escape(meta.description)}" />`)
        .replace("</head>", `    ${tags}\n  </head>`);
    }
  } catch {
    // Donnée introuvable : on sert la page telle quelle, l'application gère l'erreur.
  }
  return new Response(html, {
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "public, max-age=0, s-maxage=3600" },
  });
}
