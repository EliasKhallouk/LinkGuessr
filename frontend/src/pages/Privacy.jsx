export default function Privacy() {
  return (
    <main className="grid">
      <div className="col-main">
        <section className="panel fade-in">
          <div className="panel-header">
            <span className="panel-title">Politique de confidentialité</span>
          </div>
          <div className="panel-body">
            <p>
              Nous respectons votre vie privée. LinkGuessr ne collecte pas de données personnelles
              sensibles. Les préférences de langue et de thème peuvent être stockées localement dans
              votre navigateur (localStorage) afin d'améliorer votre expérience.
            </p>
            <p style={{ marginTop: 8 }}>
              Classement: si vous enregistrez un score, un pseudonyme est sauvegardé avec votre score
              et la durée de la partie. Ce pseudonyme est normalisé, limité en longueur, et destiné
              uniquement à l'affichage du classement.
            </p>
            <p style={{ marginTop: 8 }}>
              Cookies: le site utilise des technologies similaires (le cas échéant) pour des
              fonctionnalités essentielles et des mesures d'utilisation anonymisées. Aucune donnée
              n'est vendue à des tiers.
            </p>
            <p style={{ marginTop: 8 }}>
              Contact: pour toute question sur cette politique, vous pouvez nous écrire à
              <a className="chemin-link" href="mailto:linkguessr@gmail.com"> linkguessr@gmail.com</a>.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
