// Images d'aperçu (Open Graph) générées à la volée : /api/og?type=jour&n=12, duel, nombre, personne.
// Elles intriguent sans jamais révéler de réponse, et portent les crédits des sources.
import { ImageResponse } from "@vercel/og";

// Runtime Node.js (par défaut) : @vercel/og 1.x référence des modules refusés par le runtime « edge ».

const API = "https://linkguessr.duckdns.org";
const UA = "LinkGuessr/1.0 (https://link-guessr.vercel.app)";
const W = 1200;
const H = 630;

// Satori accepte des objets { type, props } : pas besoin de JSX ici.
const h = (type, style, ...children) => ({ type, props: { style, children: children.flat().filter((c) => c !== null && c !== false) } });

async function json(path) {
  const r = await fetch(`${API}${path}`, { headers: { "User-Agent": UA } });
  if (!r.ok) throw new Error(`${path} : ${r.status}`);
  return r.json();
}

// Photo Commons téléchargée ici (User-Agent identifiable, exigé par Wikimedia) puis intégrée en data URI.
async function photo(file, width = 240) {
  if (!file) return null;
  try {
    const r = await fetch(`https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(file)}?width=${width}`,
      { headers: { "User-Agent": UA } });
    if (!r.ok) return null;
    const bytes = new Uint8Array(await r.arrayBuffer());
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return `data:${r.headers.get("content-type") || "image/jpeg"};base64,${btoa(binary)}`;
  } catch {
    return null;
  }
}

function avatar(src, label, size = 200) {
  const circle = { width: size, height: size, borderRadius: size, border: "6px solid #00d9ff", display: "flex",
    alignItems: "center", justifyContent: "center", overflow: "hidden", background: "#1a1f35" };
  return h("div", { display: "flex", flexDirection: "column", alignItems: "center", width: size + 80 },
    src
      ? { type: "img", props: { src, width: size, height: size, style: { ...circle, objectFit: "cover" } } }
      : h("div", { ...circle, fontSize: size / 2, color: "#9ca8c5" }, label === "?" ? "?" : (label || "?").charAt(0)),
    label && label !== "?" ? h("div", { marginTop: 16, fontSize: 30, color: "#f0f4ff", textAlign: "center", maxWidth: size + 80 }, label) : null);
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
      h("div", { fontSize: 26, color: "#9ca8c5" }, "link-guessr.vercel.app")),
    h("div", { fontSize: 56, fontWeight: 800, marginTop: 24 }, title),
    subtitle ? h("div", { fontSize: 32, color: "#9ca8c5", marginTop: 8 }, subtitle) : null,
    h("div", { display: "flex", flex: 1, alignItems: "center", justifyContent: "center" }, body),
    h("div", { fontSize: 20, color: "#6b7694" }, "Données : Wikipédia (CC BY-SA 4.0), Wikidata (CC0) · Photos : Wikimedia Commons"));
}

async function render(params) {
  const type = params.get("type");
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
  if (type === "nombre") {
    const n = Number(params.get("score")) || 0;
    return frame("Combien de liens entre deux personnalités ?", "60 secondes pour estimer un maximum de distances",
      h("div", { display: "flex", flexDirection: "column", alignItems: "center" },
        h("div", { fontSize: 140, fontWeight: 800, color: "#00d9ff" }, `${n} pts`),
        h("div", { fontSize: 40 }, "Tu fais mieux ?")));
  }
  if (type === "personne") {
    const { person: p, closest } = await json(`/person/${encodeURIComponent(params.get("qid"))}/card`);
    const src = await photo(p.image, 320);
    return frame(p.name, p.description || "",
      h("div", { display: "flex", alignItems: "center", gap: 48, width: "100%" },
        avatar(src, null, 240),
        h("div", { display: "flex", flexDirection: "column", fontSize: 32, gap: 12 },
          h("div", {}, `${p.degree.toLocaleString("fr-FR")} liens · ${p.degree_rank.toLocaleString("fr-FR")}e personne la plus connectée`),
          h("div", { color: "#9ca8c5" }, `Proches : ${closest.slice(0, 3).map((c) => c.name).join(", ")}`))));
  }
  return frame("Combien de liens séparent deux personnalités ?", "Jeux et exploration du réseau de Wikipédia en français",
    h("div", { display: "flex", alignItems: "center", gap: 24 }, mystery(160), arrow, mystery(160), arrow, mystery(160)));
}

export async function GET(request) {
  const params = new URL(request.url).searchParams;
  let element;
  try {
    element = await render(params);
  } catch {
    params.delete("type");
    element = await render(params);  // image générique si la donnée est introuvable
  }
  return new ImageResponse(element, {
    width: W, height: H,
    headers: { "Cache-Control": "public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800" },
  });
}
