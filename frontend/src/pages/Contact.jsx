export default function Contact() {
  return (
    <main className="grid">
      <div className="col-main">
        <section className="panel fade-in">
          <div className="panel-header">
            <span className="panel-title">Contact</span>
          </div>
          <div className="panel-body">
            <p>
              Une question, une suggestion, un partenariat ? Écrivez-nous.
            </p>
            <p style={{ marginTop: 8 }}>
              Email: <a className="chemin-link" href="mailto:linkguessr@gmail.com">linkguessr@gmail.com</a>
            </p>
            <p style={{ marginTop: 8 }}>
              Vous pouvez également nous suivre et envoyer un message sur nos réseaux (à venir).
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
