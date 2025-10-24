export default function About() {
  return (
    <main className="grid">
      <div className="col-main">
        <section className="panel fade-in">
          <div className="panel-header">
            <span className="panel-title">À propos</span>
          </div>
          <div className="panel-body">
            <p>
              LinkGuessr est un jeu qui s'appuie sur les liens entre personnalités pour vous faire
              deviner des chemins et des nombres de relations. Les données proviennent de graphes
              construits à partir de sources publiques (par ex. Wikipédia).
            </p>
            <p style={{ marginTop: 8 }}>
              Objectif: proposer une expérience ludique et éducative. Deux modes sont disponibles:
              "Devine le chemin" (trouvez le plus court chemin) et "Devine le nombre" (estimez le
              nombre minimal de relations). Un classement permet de comparer vos scores.
            </p>
            <p style={{ marginTop: 8 }}>
              Ce projet évolue régulièrement: n'hésitez pas à partager vos suggestions !
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
