
/**
 * Composant de démonstration des effets ludiques
 * À utiliser pour tester et prévisualiser tous les effets disponibles
 */
export default function PlayfulDemo() {
  return (
    <div className="panel" style={{ maxWidth: '800px', margin: '20px auto' }}>
      <div className="panel-header">
        <h2 className="panel-title">🎮 Démo des Effets Ludiques</h2>
      </div>
      <div className="panel-body" style={{ display: 'grid', gap: '20px' }}>
        
        {/* Buttons */}
        <section>
          <h3 style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>Boutons</h3>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <button className="btn ripple">Ripple Effect</button>
            <button className="btn btn-bouncy">Bouncy</button>
            <button className="btn sparkle-on-hover">Sparkle</button>
          </div>
        </section>

        {/* Text Effects */}
        <section>
          <h3 style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>Effets de Texte</h3>
          <p className="rainbow-text" style={{ fontSize: '24px', fontWeight: 'bold' }}>
            Rainbow Text Effect
          </p>
          <p className="neon-glow" style={{ fontSize: '20px', fontWeight: 'bold' }}>
            Neon Glow Effect
          </p>
        </section>

        {/* Cards */}
        <section>
          <h3 style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>Cards & Panels</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div className="panel hover-lift" style={{ padding: '20px' }}>
              <h4>Hover Lift</h4>
              <p className="muted">Survole-moi!</p>
            </div>
            <div className="panel gradient-border" style={{ padding: '20px' }}>
              <h4>Gradient Border</h4>
              <p className="muted">Survole-moi!</p>
            </div>
          </div>
        </section>

        {/* Animations */}
        <section>
          <h3 style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>Animations</h3>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
            <div className="pulse" style={{ 
              width: '40px', 
              height: '40px', 
              borderRadius: '50%', 
              background: 'var(--gradient-primary)' 
            }} />
            <div style={{ padding: '10px 20px', background: 'var(--panel-bg)', borderRadius: 'var(--radius-sm)' }}>
              <span className="counter" style={{ fontSize: '32px', fontWeight: 'bold' }}>
                100
              </span>
            </div>
            <button className="btn" onClick={(e) => e.target.classList.add('wiggle')}>
              Wiggle Me
            </button>
          </div>
        </section>

        {/* Score Popup Demo */}
        <section>
          <h3 style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>Score Popup</h3>
          <div className="score-popup success-box">
            <strong>+100 points!</strong> Excellente réponse! 🎉
          </div>
        </section>

        {/* KPI Display */}
        <section>
          <h3 style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>KPI Style</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px' }}>
            <div className="kpi">
              Score: <strong>2,450</strong>
            </div>
            <div className="kpi">
              Temps: <strong>45s</strong>
            </div>
            <div className="kpi">
              Streak: <strong>8</strong> 🔥
            </div>
          </div>
        </section>

        {/* Links */}
        <section>
          <h3 style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>Liens Stylés</h3>
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <a href="#" className="chemin-link">Barack Obama</a>
            <span>→</span>
            <a href="#" className="chemin-link">Michelle Obama</a>
            <span>→</span>
            <a href="#" className="chemin-link">Joe Biden</a>
          </div>
        </section>

        {/* Messages */}
        <section>
          <h3 style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>Messages</h3>
          <div className="error-box shake-error" style={{ marginBottom: '12px' }}>
            ❌ Oups! Erreur de connexion
          </div>
          <div className="success-box">
            ✅ Bravo! Partie terminée avec succès
          </div>
        </section>

        {/* Spinner */}
        <section>
          <h3 style={{ marginBottom: '12px', color: 'var(--text-secondary)' }}>Loading</h3>
          <div className="spinner"></div>
        </section>

        {/* Info Box */}
        <section style={{ 
          padding: '16px', 
          background: 'var(--gradient-panel)', 
          borderRadius: 'var(--radius-md)',
          border: '2px solid var(--border-color)'
        }}>
          <h4 style={{ marginBottom: '8px' }}>💡 Comment utiliser</h4>
          <p className="muted" style={{ fontSize: '14px', lineHeight: '1.6' }}>
            Tous ces effets sont disponibles via des classes CSS. 
            Consultez <code style={{ 
              padding: '2px 6px', 
              background: 'var(--bg-base)', 
              borderRadius: '4px',
              color: 'var(--accent-primary)'
            }}>playful-effects.css</code> et <code style={{ 
              padding: '2px 6px', 
              background: 'var(--bg-base)', 
              borderRadius: '4px',
              color: 'var(--accent-primary)'
            }}>DESIGN_GUIDE.md</code> pour plus de détails.
          </p>
        </section>
      </div>
    </div>
  );
}
