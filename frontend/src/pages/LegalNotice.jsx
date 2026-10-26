import { Link } from "react-router-dom";
import { usePageMeta } from "../lib/meta";
import { useI18n } from "../i18n/I18nProvider";

// Mentions légales (loi pour la confiance dans l'économie numérique, art. 6). Texte en français :
// c'est le droit français qui s'applique ; la version anglaise du site renvoie ici.
export default function LegalNotice() {
  const { t } = useI18n();
  usePageMeta(t("meta.legal.title"), t("meta.legal.description"));
  return (
    <main className="page fade-in">
      <section className="panel">
        <div className="panel-header"><span className="panel-title">{t("nav.legal")}</span></div>
        <div className="panel-body legal">
          <h3>Éditeur</h3>
          <p>
            LinkGuessr est un projet personnel et non commercial, édité par <strong>Elias Khallouk</strong>, particulier.
            {/* À vérifier : en tant que particulier, l'éditeur peut ne pas publier son adresse postale à condition de
                l'avoir communiquée à l'hébergeur (LCEN, art. 6-III-2). Aucune adresse n'est publiée ici. */}
          </p>
          <p>
            Contact : <a className="chemin-link" href="mailto:linkguessr@gmail.com">linkguessr@gmail.com</a>
            {" "}(voir aussi la page <Link className="chemin-link" to="/contact">Contact</Link>).
          </p>

          <h3>Directeur de la publication</h3>
          <p>Elias Khallouk.</p>

          <h3>Hébergement</h3>
          <p>
            <strong>Site web</strong> : Vercel Inc., 440 N Barranca Ave #4133, Covina, CA 91723, États-Unis
            {" "}(<a className="chemin-link" href="https://vercel.com" target="_blank" rel="noreferrer">vercel.com</a>).
          </p>
          <p>
            <strong>API et base de données</strong> : Oracle Cloud Infrastructure, serveur situé dans la région de Paris
            (eu-paris-1), fourni par Oracle Corporation, 2300 Oracle Way, Austin, TX 78741, États-Unis
            {" "}(<a className="chemin-link" href="https://www.oracle.com/cloud/" target="_blank" rel="noreferrer">oracle.com/cloud</a>).
            {/* À vérifier : adresse d'Oracle Corporation non confirmée (le site d'Oracle refuse la lecture automatique),
                et l'entité contractante du compte Oracle Cloud peut être une filiale européenne (Oracle France,
                Oracle EMEA…) : à relire dans le contrat du compte. La région eu-paris-1 est vérifiée sur la VM. */}
          </p>

          <h3>Données personnelles</h3>
          <p>
            Ce que le site enregistre, pourquoi et pour combien de temps : voir la{" "}
            <Link className="chemin-link" to="/politique-de-confidentialite">politique de confidentialité</Link>.
          </p>

          <h3>Crédits et licences</h3>
          <ul>
            <li>
              Textes et extraits : <a className="chemin-link" href="https://fr.wikipedia.org" target="_blank" rel="noreferrer">Wikipédia</a>,
              {" "}sous licence <a className="chemin-link" href="https://creativecommons.org/licenses/by-sa/4.0/deed.fr" target="_blank" rel="noreferrer">CC BY-SA 4.0</a> ;
              chaque extrait renvoie à son article.
            </li>
            <li>Données structurées : <a className="chemin-link" href="https://www.wikidata.org" target="_blank" rel="noreferrer">Wikidata</a> (CC0).</li>
            <li>
              Photos : <a className="chemin-link" href="https://commons.wikimedia.org" target="_blank" rel="noreferrer">Wikimedia Commons</a> ;
              l'auteur et la licence de chaque photo sont indiqués sur la fiche de la personne.
            </li>
            <li>Police de caractères : Inter, sous licence SIL Open Font License 1.1 (<a className="chemin-link" href="/fonts/OFL.txt">texte de la licence</a>).</li>
          </ul>
          <p>
            Sources détaillées : <Link className="chemin-link" to="/a-propos">À propos</Link>.
          </p>
        </div>
      </section>
    </main>
  );
}
