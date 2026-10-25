// Relais /v1/* -> API de la VM (vercel.json réécrit /v1/:path* vers /api/proxy?path=:path*).
// Vercel met en cache les réponses de ses fonctions qui portent un s-maxage : les réponses
// identiques pour tous (défi du jour, fiches, recherche…) ne sollicitent la VM qu'une fois.
const VM = "https://linkguessr.duckdns.org";
const FORWARDED_REQUEST_HEADERS = ["content-type", "x-admin-token", "accept"];
const FORWARDED_RESPONSE_HEADERS = ["content-type", "cache-control", "retry-after"];

async function forward(request) {
  const url = new URL(request.url);
  const path = (url.searchParams.get("path") || "").replace(/^\/+/, "");
  url.searchParams.delete("path");
  const target = `${VM}/${path}${url.search}`;

  const headers = new Headers({ "User-Agent": "LinkGuessr-proxy" });
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  // IP du joueur, pour la limitation de débit côté VM.
  const ip = (request.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  if (ip) headers.set("x-vercel-forwarded-for", ip);

  const response = await fetch(target, {
    method: request.method,
    headers,
    body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.text(),
  });
  const out = new Headers();
  for (const name of FORWARDED_RESPONSE_HEADERS) {
    const value = response.headers.get(name);
    if (value) out.set(name, value);
  }
  return new Response(response.body, { status: response.status, headers: out });
}

export const GET = forward;
export const POST = forward;
