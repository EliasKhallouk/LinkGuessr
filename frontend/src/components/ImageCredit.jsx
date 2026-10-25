import { useEffect, useState } from "react";

// Auteur et licence d'une image Wikimedia Commons, lus en direct dans les métadonnées du fichier.
export default function ImageCredit({ file }) {
  const [credit, setCredit] = useState(null);

  useEffect(() => {
    setCredit(null);
    const url = new URL("https://commons.wikimedia.org/w/api.php");
    Object.entries({
      action: "query", titles: `File:${file}`, prop: "imageinfo", iiprop: "extmetadata",
      iiextmetadatafilter: "Artist|LicenseShortName|LicenseUrl", format: "json", origin: "*",
    }).forEach(([k, v]) => url.searchParams.set(k, v));
    fetch(url)
      .then((r) => r.json())
      .then((data) => {
        const meta = Object.values(data.query?.pages || {})[0]?.imageinfo?.[0]?.extmetadata || {};
        // Artist est du HTML : on n'en garde que le texte.
        const artist = new DOMParser().parseFromString(meta.Artist?.value || "", "text/html").body.textContent.trim();
        setCredit({ artist, license: meta.LicenseShortName?.value, licenseUrl: meta.LicenseUrl?.value });
      })
      .catch(() => {});
  }, [file]);

  const page = `https://commons.wikimedia.org/wiki/File:${encodeURIComponent(file)}`;
  return (
    <figcaption className="image-credit">
      <a href={page} target="_blank" rel="noreferrer">
        {credit?.artist ? `Photo : ${credit.artist}` : "Photo : Wikimedia Commons"}
      </a>
      {credit?.license && (
        <> · {credit.licenseUrl
          ? <a href={credit.licenseUrl} target="_blank" rel="noreferrer">{credit.license}</a>
          : credit.license}</>
      )}
    </figcaption>
  );
}
