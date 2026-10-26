// Miniatures Wikimedia Commons en URL directe (upload.wikimedia.org/…/thumb/…), sans passer par
// Special:FilePath et ses deux redirections. L'URL se déduit du nom de fichier : dossier = MD5 du nom.

// Wikimedia ne sert plus que des largeurs standard : une autre largeur (80, 160…) répond 400.
const STEPS = [40, 60, 120, 250, 330, 500, 960];

export function thumbWidth(width) {
  return STEPS.find((s) => s >= width) ?? STEPS[STEPS.length - 1];
}

export function commonsDirect(file, width) {
  const name = file.replace(/ /g, "_");
  const hash = md5(name);
  const enc = encodeURIComponent(name);
  const w = thumbWidth(width);
  const ext = name.split(".").pop().toLowerCase();
  // Formats dont la miniature est convertie : SVG → PNG, TIFF → JPEG (page 1), PDF/DjVu → JPEG (page 1).
  const thumb = ext === "svg" ? `${w}px-${enc}.png`
    : ext === "tif" || ext === "tiff" ? `lossy-page1-${w}px-${enc}.jpg`
      : ext === "pdf" || ext === "djvu" ? `page1-${w}px-${enc}.jpg`
        : `${w}px-${enc}`;
  return `https://upload.wikimedia.org/wikipedia/commons/thumb/${hash[0]}/${hash.slice(0, 2)}/${enc}/${thumb}`;
}

// Repli si la miniature directe n'existe pas (image d'origine plus petite que la largeur demandée…).
export function commonsFilePath(file, width) {
  return `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(file)}?width=${thumbWidth(width)}`;
}

// MD5 (RFC 1321) sur les octets UTF-8 : seul usage, le dossier des fichiers Commons.
export function md5(text) {
  const bytes = new TextEncoder().encode(text);
  const n = (((bytes.length + 8) >> 6) + 1) * 16;
  const words = new Array(n).fill(0);
  for (let i = 0; i < bytes.length; i++) words[i >> 2] |= bytes[i] << ((i % 4) * 8);
  words[bytes.length >> 2] |= 0x80 << ((bytes.length % 4) * 8);
  words[n - 2] = bytes.length * 8;

  const S = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21];
  const K = Array.from({ length: 64 }, (_, i) => Math.floor(Math.abs(Math.sin(i + 1)) * 2 ** 32) | 0);
  let [a0, b0, c0, d0] = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476];
  for (let chunk = 0; chunk < n; chunk += 16) {
    let [a, b, c, d] = [a0, b0, c0, d0];
    for (let i = 0; i < 64; i++) {
      let f;
      let g;
      if (i < 16) { f = (b & c) | (~b & d); g = i; }
      else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) % 16; }
      else if (i < 48) { f = b ^ c ^ d; g = (3 * i + 5) % 16; }
      else { f = c ^ (b | ~d); g = (7 * i) % 16; }
      const tmp = d;
      d = c;
      c = b;
      const sum = (a + f + K[i] + words[chunk + g]) | 0;
      const s = S[(i >> 4) * 4 + (i % 4)];
      b = (b + ((sum << s) | (sum >>> (32 - s)))) | 0;
      a = tmp;
    }
    a0 = (a0 + a) | 0;
    b0 = (b0 + b) | 0;
    c0 = (c0 + c) | 0;
    d0 = (d0 + d) | 0;
  }
  return [a0, b0, c0, d0]
    .map((v) => Array.from({ length: 4 }, (_, i) => ((v >>> (i * 8)) & 0xff).toString(16).padStart(2, "0")).join(""))
    .join("");
}
