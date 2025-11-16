import {
    ArcElement,
    BarElement,
    CategoryScale,
    Chart as ChartJS,
    Legend,
    LinearScale,
    Title,
    Tooltip,
} from 'chart.js';
import { useEffect, useState } from "react";
import { Bar, Pie } from 'react-chartjs-2';
import { apiUrl } from "../config";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

export default function Stats() {
  const [degreeData, setDegreeData] = useState(null);
  const [categoryData, setCategoryData] = useState(null);
  const [keyStats, setKeyStats] = useState(null);
  const [domainHeatmap, setDomainHeatmap] = useState(null);
  const [heatmapMode, setHeatmapMode] = useState('counts');
  const [excludeUnknown, setExcludeUnknown] = useState(true);
  const [heatmapLoading, setHeatmapLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [dRes, cRes, kRes] = await Promise.all([
          fetch(apiUrl('/degree_distribution')),
          fetch(apiUrl('/category_counts')),
          fetch(apiUrl('/key_stats')),
        ]);
        if (!dRes.ok || !cRes.ok) throw new Error('api');
        const dJson = await dRes.json();
        const cJson = await cRes.json();
        const kJson = kRes && kRes.ok ? await kRes.json() : null;
        // fetch domain heatmap
        let hJson = null;
        try {
          const q = new URLSearchParams({ mode: heatmapMode, exclude_unknown: excludeUnknown ? '1' : '0' });
          setHeatmapLoading(true);
          const hRes = await fetch(apiUrl(`/domain_heatmap?${q.toString()}`));
          if (hRes.ok) hJson = await hRes.json();
        } catch (e) {
          hJson = null;
        } finally {
          setHeatmapLoading(false);
        }
        if (!mounted) return;
        const deg = Array.isArray(dJson.results) ? dJson.results : [];
        const cat = Array.isArray(cJson.results) ? cJson.results : [];
        setDegreeData({
          labels: deg.map(r => r.degree.toString()),
          datasets: [
            {
              label: 'Number of persons',
              data: deg.map(r => r.persons),
              backgroundColor: 'rgba(75, 192, 192, 0.6)'
            }
          ]
        });
        setCategoryData({
          labels: cat.map(r => r.category || 'unknown'),
          datasets: [
            {
              label: 'Persons per category',
              data: cat.map(r => r.persons),
              backgroundColor: cat.map((_, i) => `hsl(${(i*45)%360} 70% 50%)`)
            }
          ]
        });
        setKeyStats(kJson);
        setDomainHeatmap(hJson);
      } catch (e) {
        if (!mounted) return;
        setError('Impossible de charger les statistiques');
      } finally {
        if (!mounted) return;
        setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  // refetch heatmap when controls change
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        setHeatmapLoading(true);
        const q = new URLSearchParams({ mode: heatmapMode, exclude_unknown: excludeUnknown ? '1' : '0' });
        const hRes = await fetch(apiUrl(`/domain_heatmap?${q.toString()}`));
        if (!mounted) return;
        if (hRes.ok) {
          const hJson = await hRes.json();
          setDomainHeatmap(hJson);
        } else {
          setDomainHeatmap(null);
        }
      } catch (e) {
        if (!mounted) return;
        setDomainHeatmap(null);
      } finally {
        if (!mounted) return;
        setHeatmapLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [heatmapMode, excludeUnknown]);

  if (loading) return <div className="panel"><div className="panel-body">Chargement...</div></div>;
  if (error) return <div className="panel"><div className="panel-body">{error}</div></div>;

  return (
    <div style={{ display: 'grid', gap: 16, padding: '0 16px' }}>
      {keyStats && (
        <section className="panel fade-in">
          <div className="panel-header">
            <span className="panel-title">Chiffres clés</span>
          </div>
          <div className="panel-body" style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
            <div style={{ 
              padding: '16px', 
              background: 'var(--panel-bg)', 
              border: '2px solid var(--border-color)', 
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-sm)',
              transition: 'all 0.3s ease'
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Personnes</div>
              <div style={{ fontSize: 28, fontWeight: 800, marginTop: 8, background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                {keyStats.total_persons ?? '—'}
              </div>
            </div>
            <div style={{ 
              padding: '16px', 
              background: 'var(--panel-bg)', 
              border: '2px solid var(--border-color)', 
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-sm)',
              transition: 'all 0.3s ease'
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Relations</div>
              <div style={{ fontSize: 28, fontWeight: 800, marginTop: 8, background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                {keyStats.total_relations ?? '—'}
              </div>
            </div>
            <div style={{ 
              padding: '16px', 
              background: 'var(--panel-bg)', 
              border: '2px solid var(--border-color)', 
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-sm)',
              transition: 'all 0.3s ease'
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Degré moyen</div>
              <div style={{ fontSize: 28, fontWeight: 800, marginTop: 8, background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                {typeof keyStats.average_degree === 'number' ? keyStats.average_degree.toFixed(2) : '—'}
              </div>
            </div>
            <div style={{ 
              padding: '16px', 
              background: 'var(--panel-bg)', 
              border: '2px solid var(--border-color)', 
              borderRadius: 'var(--radius-md)',
              boxShadow: 'var(--shadow-sm)',
              transition: 'all 0.3s ease'
            }}>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Degré max</div>
              <div style={{ fontSize: 28, fontWeight: 800, marginTop: 8, background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
                {keyStats.max_degree ?? '—'}
              </div>
              {Array.isArray(keyStats.top_persons) && keyStats.top_persons.length > 0 && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, fontWeight: 500 }}>
                  {keyStats.top_persons.slice(0, 3).map(p => p.name.replace(/_/g, ' ')).join(', ')}
                  {keyStats.top_persons.length > 3 && ` +${keyStats.top_persons.length - 3}`}
                </div>
              )}
            </div>
          </div>
        </section>
      )}
      
  <div style={{ display: 'grid', gap: 16, gridTemplateColumns: '1fr 1fr' }}>
        <section className="panel fade-in">
          <div className="panel-header">
            <span className="panel-title">Distribution des degrés</span>
          </div>
          <div className="panel-body">
            <div style={{ height: 300, position: 'relative' }}>
              {degreeData && <Bar options={{ 
                responsive: true, 
                maintainAspectRatio: false,
                plugins: { 
                  legend: { display: false },
                  tooltip: { 
                    backgroundColor: 'rgba(0, 0, 0, 0.9)',
                    padding: 12,
                    titleFont: { size: 15, weight: 'bold' },
                    bodyFont: { size: 14 },
                    titleColor: '#fff',
                    bodyColor: '#fff'
                  }
                },
                scales: {
                  y: { 
                    beginAtZero: true,
                    grid: { color: 'rgba(124, 58, 237, 0.15)' },
                    ticks: { 
                      color: '#fff',
                      font: { size: 13, weight: '600' }
                    }
                  },
                  x: {
                    grid: { display: false },
                    ticks: { 
                      color: '#fff',
                      font: { size: 13, weight: '600' }
                    }
                  }
                }
              }} data={degreeData} />}
            </div>
          </div>
        </section>

        <section className="panel fade-in">
          <div className="panel-header">
            <span className="panel-title">Répartition par catégorie</span>
          </div>
          <div className="panel-body">
            <div style={{ height: 300, position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              {categoryData && <Pie options={{ 
                responsive: true, 
                maintainAspectRatio: false,
                plugins: {
                  legend: { 
                    position: 'right',
                    labels: {
                      color: '#fff',
                      font: { size: 13, weight: '700' },
                      padding: 10,
                      boxWidth: 15,
                      boxHeight: 15
                    }
                  },
                  tooltip: { 
                    backgroundColor: 'rgba(0, 0, 0, 0.9)',
                    padding: 12,
                    titleFont: { size: 15, weight: 'bold' },
                    bodyFont: { size: 14 },
                    titleColor: '#fff',
                    bodyColor: '#fff'
                  }
                }
              }} data={categoryData} />}
            </div>
          </div>
        </section>
      </div>
      { /* Heatmap controls */ }
      <section className="panel fade-in" style={{ alignSelf: 'start' }}>
        <div className="panel-header"><span className="panel-title">Options heatmap</span></div>
        <div className="panel-body" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ color: 'var(--text-secondary)', fontWeight: 700 }}>Mode</label>
          <select value={heatmapMode} onChange={e => setHeatmapMode(e.target.value)} style={{ padding: '6px 8px', borderRadius: 6 }}>
            <option value="counts">Counts</option>
            <option value="binary">Présence</option>
            <option value="density">Densité</option>
            <option value="pmi">PMI</option>
            <option value="ratio">Ratio</option>
          </select>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginLeft: 8 }}>
            <input type="checkbox" checked={excludeUnknown} onChange={e => setExcludeUnknown(e.target.checked)} />
            <span style={{ color: 'var(--text-secondary)' }}>Exclure 'unknown'</span>
          </label>
          {heatmapLoading && <div style={{ marginLeft: 'auto', color: 'var(--text-muted)' }}>Chargement...</div>}
        </div>
      </section>

      {domainHeatmap && Array.isArray(domainHeatmap.results) && (
        <section className="panel fade-in">
          <div className="panel-header"><span className="panel-title">Relations inter-domaines</span></div>
          <div className="panel-body">
            {/* Build matrix */}
            {(() => {
              const rows = domainHeatmap.results;
              const domainsSet = new Set();
              rows.forEach(r => { domainsSet.add(r.domain_a); domainsSet.add(r.domain_b); });
              const domains = Array.from(domainsSet).sort();
              const maxCount = rows.reduce((m, r) => Math.max(m, r.count || 0), 0) || 1;
              // build lookup
              const map = {};
              rows.forEach(r => { map[`${r.domain_a}::${r.domain_b}`] = r.count; });
              return (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 600 }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: 'left', padding: '8px 10px', color: 'var(--text-secondary)' }}>→ / ↓</th>
                        {domains.map(d => (
                          <th key={d} style={{ padding: '8px 10px', color: 'var(--text-secondary)' }}>{d}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {domains.map(rowD => (
                        <tr key={rowD}>
                          <td style={{ padding: '6px 10px', color: 'var(--text-secondary)', fontWeight: 700 }}>{rowD}</td>
                          {domains.map(colD => {
                            const a = rowD <= colD ? rowD : colD;
                            const b = rowD <= colD ? colD : rowD;
                            const key = `${a}::${b}`;
                            const cell = rows.find(r => (r.domain_a === a && r.domain_b === b) || (r.domain_a === b && r.domain_b === a)) || {};
                            const cnt = cell.count || 0;
                            // decide intensity and label based on mode
                            let intensity = 0;
                            let label = cnt;
                            if (heatmapMode === 'density' && typeof cell.density === 'number') {
                              intensity = Math.round(cell.density * 95) + 5; // small floor
                              label = (typeof cell.density_pct === 'number') ? `${(cell.density_pct*100).toFixed(1)}%` : `${(cell.density*100).toFixed(1)}%`;
                            } else if (heatmapMode === 'pmi' && typeof cell.pmi === 'number') {
                              // show PMI rounded
                              intensity = Math.round((Math.tanh(cell.pmi) + 1) / 2 * 90) + 5; // tanh to compress extremes
                              label = cell.pmi.toFixed(3);
                            } else if (heatmapMode === 'ratio' && typeof cell.ratio_internal === 'number') {
                              intensity = Math.round(cell.ratio_internal * 95) + 5;
                              label = `${(cell.ratio_internal * 100).toFixed(1)}%`;
                            } else if (heatmapMode === 'binary') {
                              intensity = cnt > 0 ? 90 : 8;
                              label = cnt > 0 ? '✔' : '';
                            } else {
                              intensity = Math.round((cnt / maxCount) * 95) + 5;
                              label = cnt;
                            }
                            const bg = `rgba(124,58,237, ${Math.min(Math.max(intensity, 6), 95)/100})`;
                            const title = `count: ${cnt}` +
                              (typeof cell.density === 'number' ? `\n density: ${(cell.density*100).toFixed(3)}%` : '') +
                              (typeof cell.pmi === 'number' ? `\n pmi: ${cell.pmi.toFixed(6)}` : '') +
                              (typeof cell.ratio_internal === 'number' ? `\n ratio_internal: ${(cell.ratio_internal*100).toFixed(3)}%` : '');
                            return (
                              <td key={colD} title={title} style={{ padding: '6px 10px', textAlign: 'center', background: bg, color: '#fff', fontWeight: 700 }}>
                                {label}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              );
            })()}
          </div>
        </section>
      )}
    </div>
  );
}
