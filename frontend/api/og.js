// Images d'aperçu (Open Graph) générées à la volée : /api/og?type=jour&n=12, duel, nombre, qui, cache, personne, explorer.
// Elles intriguent sans jamais révéler de réponse, et portent les crédits des sources.
import { ImageResponse } from "@vercel/og";
import { commonsDirect, commonsFilePath } from "../src/lib/commons.js";
import { sharedPathQuery } from "../src/lib/share.js";

// Runtime Node.js (par défaut) : @vercel/og 1.x référence des modules refusés par le runtime « edge ».

const API = "https://linkguessr.duckdns.org";
const UA = "LinkGuessr/1.0 (https://linkguessr.com)";
const W = 1200;
const H = 630;

// Satori accepte des objets { type, props } : pas besoin de JSX ici.
// Il exige display: flex sur les blocs à plusieurs enfants : c'est la valeur par défaut ici.
const h = (type, style, ...children) => ({
  type,
  props: { style: { display: "flex", ...style }, children: children.flat().filter((c) => c !== null && c !== false) },
});

// `base` : l'API directe, ou /v1 du site (cache Vercel) pour les requêtes partagées avec la page.
async function json(path, base = API) {
  const r = await fetch(`${base}${path}`, { headers: { "User-Agent": UA } });
  if (!r.ok) throw new Error(`${path} : ${r.status}`);
  return r.json();
}

// Photo Commons téléchargée ici (User-Agent identifiable, exigé par Wikimedia) puis intégrée en data URI.
// Miniature directe (une largeur standard : Wikimedia refuse les autres), Special:FilePath en repli.
async function photo(file, width = 250) {
  if (!file) return null;
  try {
    let r = await fetch(commonsDirect(file, width), { headers: { "User-Agent": UA } });
    if (!r.ok) r = await fetch(commonsFilePath(file, width), { headers: { "User-Agent": UA } });
    if (!r.ok) return null;
    const bytes = new Uint8Array(await r.arrayBuffer());
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return `data:${r.headers.get("content-type") || "image/jpeg"};base64,${btoa(binary)}`;
  } catch {
    return null;
  }
}

function avatar(src, label, size = 200, showLabel = true) {
  const circle = { width: size, height: size, borderRadius: size, border: "6px solid #00d9ff", display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden", background: "#1a1f35" };
  return h("div", { display: "flex", flexDirection: "column", alignItems: "center", width: size + 80 },
    src
      ? { type: "img", props: { src, width: size, height: size, style: { ...circle, objectFit: "cover" } } }
      : h("div", { ...circle, fontSize: size / 2, color: "#9ca8c5" }, label === "?" ? "?" : (label || "?").charAt(0)),
    showLabel && label && label !== "?" ? h("div", { marginTop: 16, fontSize: 30, color: "#f0f4ff", textAlign: "center", maxWidth: size + 80 }, label) : null);
}

const mystery = (size = 200) => h("div", { display: "flex", flexDirection: "column", alignItems: "center", width: size + 80 },
  h("div", { width: size, height: size, borderRadius: size, border: "6px dashed #f472b6", display: "flex",
    alignItems: "center", justifyContent: "center", fontSize: size / 1.6, color: "#f472b6", background: "#1a1f35" }, "?"));

const arrow = h("div", { fontSize: 56, color: "#7c3aed", marginTop: -40 }, "→");

function frame(title, subtitle, body) {
  return h("div", { width: W, height: H, display: "flex", flexDirection: "column", background: "linear-gradient(135deg, #0a0e1a 0%, #1a1f35 60%, #2a1650 100%)",
    padding: "44px 56px", fontFamily: "sans-serif", color: "#f0f4ff" },
    h("div", { display: "flex", justifyContent: "space-between", alignItems: "center" },
      h("div", { fontSize: 34, fontWeight: 700, color: "#00d9ff" }, "LinkGuessr"),
      h("div", { fontSize: 26, color: "#9ca8c5" }, "linkguessr.com")),
    h("div", { fontSize: 56, fontWeight: 800, marginTop: 24 }, title),
    subtitle ? h("div", { fontSize: 32, color: "#9ca8c5", marginTop: 8 }, subtitle) : null,
    h("div", { display: "flex", flex: 1, alignItems: "center", justifyContent: "center" }, body),
    h("div", { fontSize: 20, color: "#6b7694" }, "Données : Wikipédia (CC BY-SA 4.0), Wikidata (CC0) · Photos : Wikimedia Commons"));
}

async function render(params, origin) {
  const type = params.get("type");
  if (type === "explorer") {
    // Chemin partagé : les deux bouts et le nombre de liens, jamais les intermédiaires.
    const [de, a] = [params.get("de"), params.get("a")];
    const d = await json(sharedPathQuery(de, a, params.get("mode")), `${origin}/v1`);
    if (d.length === null) throw new Error("aucun chemin");
    const [ca, cb] = [d.persons[de], d.persons[a]];
    const [pa, pb] = await Promise.all([photo(ca.image), photo(cb.image)]);
    const dots = h("div", { fontSize: 56, color: "#9ca8c5", marginTop: -40 }, "· · ·");
    return frame(`${ca.name} et ${cb.name} : ${d.length} ${d.length > 1 ? "liens" : "lien"}`, "Tu devines lesquels ?",
      h("div", { display: "flex", alignItems: "center", gap: 24 }, avatar(pa, ca.name, 220, false), arrow, dots, arrow,
        avatar(pb, cb.name, 220, false)));
  }
  if (type === "jour") {
    const d = await json(`/daily/archive/${encodeURIComponent(params.get("n"))}`);
    const [a, b] = [d.persons[d.path[0]], d.persons[d.path[d.path.length - 1]]];
    const [pa, pb] = await Promise.all([photo(a.image), photo(b.image)]);
    return frame(`Défi du jour #${d.number}`, "Qui relie ces deux personnes ?",
      h("div", { display: "flex", alignItems: "center", gap: 24 }, avatar(pa, a.name), arrow, mystery(), arrow, avatar(pb, b.name)));
  }
  if (type === "duel") {
    const [qa, qb] = (params.get("paire") || "").split("-");
    const [ca, cb] = await Promise.all([json(`/person/${qa}/card`), json(`/person/${qb}/card`)]);
    const [pa, pb] = await Promise.all([photo(ca.person.image), photo(cb.person.image)]);
    const n = Number(params.get("score")) || "?";
    return frame("Défi : relie-les pas à pas", `Quelqu'un l'a fait en ${n} coup(s). Tu fais mieux ?`,
      h("div", { display: "flex", alignItems: "center", gap: 24 }, avatar(pa, ca.person.name), arrow,
        h("div", { fontSize: 64, color: "#f472b6" }, "· · ·"), arrow, avatar(pb, cb.person.name)));
  }
  if (type === "qui") {
    // Lien de duel chiffré : l'aperçu de l'API donne les deux bouts et la position cachée, rien d'autre.
    const d = await json(`/duel/preview?${new URLSearchParams({ t: params.get("t") || "" })}`, `${origin}/v1`);
    const [a, b] = d.ends;
    const [pa, pb] = await Promise.all([photo(a.image), photo(b.image)]);
    const dots = h("div", { fontSize: 56, color: "#9ca8c5", marginTop: -40 }, "· · ·");
    return frame("Qui est caché ?", "Une personne relie les deux. Tu trouves qui ?",
      h("div", { display: "flex", alignItems: "center", gap: 24 }, avatar(pa, a.name), arrow,
        d.cache > 1 ? [dots, arrow] : [], mystery(), arrow, d.cache < d.length - 2 ? [dots, arrow] : [],
        avatar(pb, b.name)));
  }
  if (type === "cache") {
    // Les deux bouts du chemin et la personne cachée ; « · · · » pour les personnes intermédiaires.
    const chain = (params.get("chemin") || "").split("-");
    const masked = Number(params.get("cache")) || 1;
    const [ca, cb] = await Promise.all([json(`/person/${chain[0]}/card`), json(`/person/${chain[chain.length - 1]}/card`)]);
    const [pa, pb] = await Promise.all([photo(ca.person.image), photo(cb.person.image)]);
    const dots = h("div", { fontSize: 56, color: "#9ca8c5", marginTop: -40 }, "· · ·");
    return frame("Qui est caché ?", "Une personne relie les deux. Tu trouves qui ?",
      h("div", { display: "flex", alignItems: "center", gap: 24 }, avatar(pa, ca.person.name), arrow,
        masked > 1 ? [dots, arrow] : [], mystery(), arrow, masked < chain.length - 2 ? [dots, arrow] : [],
        avatar(pb, cb.person.name)));
  }
  if (type === "nombre") {
    const n = Number(params.get("score")) || 0;
    return frame("Combien de liens entre deux personnalités ?", "60 secondes pour estimer un maximum de distances",
      h("div", { display: "flex", flexDirection: "column", alignItems: "center" },
        h("div", { fontSize: 140, fontWeight: 800, color: "#00d9ff" }, `${n} pts`),
        h("div", { fontSize: 40 }, "Tu fais mieux ?")));
  }
  if (type === "personne") {
    const { person: p, closest } = await json(`/person/${encodeURIComponent(params.get("qid"))}/card`);
    const src = await photo(p.image, 330);
    return frame(p.name, p.description || "",
      h("div", { display: "flex", alignItems: "center", gap: 48, width: "100%" },
        avatar(src, null, 240),
        h("div", { flexDirection: "column", fontSize: 32, gap: 12, flex: 1, maxWidth: 760 },
          h("div", {}, `${p.degree.toLocaleString("fr-FR")} liens · ${p.degree_rank.toLocaleString("fr-FR")}e personne la plus connectée`),
          h("div", { color: "#9ca8c5" }, `Proches : ${closest.slice(0, 3).map((c) => c.name).join(", ")}`))));
  }
  return frame("Combien de liens séparent deux personnalités ?", "Jeux et exploration du réseau de Wikipédia en français",
    h("div", { display: "flex", alignItems: "center", gap: 24 }, mystery(160), arrow, mystery(160), arrow, mystery(160)));
}

export async function GET(request) {
  const { searchParams: params, origin } = new URL(request.url);
  let element;
  try {
    element = await render(params, origin);
  } catch {
    params.delete("type");
    element = await render(params, origin);  // image générique si la donnée est introuvable
  }
  return new ImageResponse(element, {
    width: W, height: H,
    headers: { "Cache-Control": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800" },
  });
}
